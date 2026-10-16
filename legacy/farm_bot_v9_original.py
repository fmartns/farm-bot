#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automacao do minigame de coleta mostrado no video do usuario.

Como funciona:
- captura somente a regiao do circulo do minigame;
- reconhece o digito central por comparacao de forma;
- detecta a zona-alvo por geometria/cor, sem depender da matiz;
- acompanha a velocidade do arco de progresso;
- estima quando a ponta entra no miolo do alvo e so entao envia a tecla.

Hotkeys no modo ao vivo:
  F8  pausa/retoma
  F10 encerra

Use por sua conta e verifique as regras do servidor.
"""

from __future__ import annotations

import argparse
import base64
import collections
import ctypes
import math
import os
import sys
import time
from typing import Optional

import cv2
import numpy as np


# Calibrado a partir do video 1918x1078 enviado.
REFERENCE_HEIGHT = 1078.0
CENTER_X_RATIO = 0.5
CENTER_Y_RATIO = 0.8646

# Geometria do circulo, em pixels na altura de referencia.
RING_R_MIN = 57.0
RING_R_MAX = 90.0
ROI_PAD = 95.0

# O toque e considerado valido quando a menor distancia entre
# o arco branco e o alvo fica abaixo desse valor (escalado pela resolucao).
DEFAULT_HIT_DISTANCE = 1.25
DEFAULT_ARM_DISTANCE = 12.0
DEFAULT_HIT_STREAK = 2

# Templates normalizados 32x48. Incluem fontes sans-serif semelhantes
# e amostras reais extraidas do video para 1, 6, 8 e 9.
_TEMPLATE_PNGS_B64 = {0: ['iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAA4ElEQVQ4EYXBgW3DMBAEMN7+Q19VvWMZbQCT8SJexIt4ES/iqbY44lZHfMSl/ogtRv0Tv2KrL2KJrb6IJZY6UrcglvqIpS5BLDVi1CXEUiMuNUJQI241IqgRtxoR1BZHjQg14qgRoUYcNSLUiKNGhBrxUFuEGvFQW4Qa8VBbhBrxUFuEGvFQW4Qa8VBbhBpx1IhQI44aEWrEUSOC2uKoEUGNuNWIoEbcakQsNeJSI8RSI0ZdQiz1EUtdgljqSN2C2OqLWGKrL2KJUf/Er7jUH7HFrY74iBfxIl7Ei3gRL34A9Pk/MRvAuREAAAAASUVORK5CYII=',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAA2UlEQVQ4EYXBAVLkQAwEMPX/H92XrJ0AB1UjxUEcxEEcxEEcxHd1i2/iS73iEY/6IUaM+l98xKhf4hYf9Ye4xK0eoR5BXGrFR40gLjVi1ApxqRGrRghqxaoRglqxakVQIx61ItSKR60IteJVI0KteNWIUCteNSLUileNCLXiVSNCrXjViFArXjUi1IpXjQi14lErghrxqBVBrVi1IqgVq0aIS41YNUJcasSoFeJWKy61grjVI9QjiI/6Q1xi1C9xi1H/i4941A8x4ku94hEHcRAHcRAHcRAH/wBnXzsxHbKtNQAAAABJRU5ErkJggg==',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAA70lEQVQ4EYXBAW7bQBAEMM7/Hz2VtOd1kxgwGV/EF/FF/FC3eIu3WvESL/VDjDjqt7jFqD/iFo/6IC5xq4+CuNURlzqCuNWIR40gLjXiqBHiUiNe6hHiUo9YNSKoEatGBDVi1YigRqwaEdSIVSOCGrFqRKgjVo0IdcSqEaGOWDUi1BGrRoQ6YtWIUEesGhHqiFUjQh2xakSoI1aNCGrEqhFBjVg1IqgRq0YENWLViKBGrBoRl3rEqhFxqREv9QhxqRFHjRC3GvGoEcStjrjUEcStPgriUR/EJUb9Ebc46pd4xKr/xYi3WvESX8QX8cU/hOpHMY6ihCEAAAAASUVORK5CYII=',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAA3UlEQVQ4EYXBAVLkQAwEMPX/H92XePFwQKoixYt4ES/iRfyvRnyLb3XEilU/xEd81G8x4qP+iFuMehCXuNWjIG71KIhbPQriUiuoI8SlVlxqhaBWjFoR1IpRK4JaMWpFqCNGrQh1xKgVoY4YtSLUEaNWhDpi1IpQR4xaEeqIUStCHTFqRagjRq0IdcSoFaGOGLUi1BGjVoQ6YtSKoFaMWhHUilErgloxakVcasWlVohLraCOELd6FMStHgVxq0dBjHoQl/ioP+IWX+q3uMWqH+IjvtURK17Ei3gRL/4BZSE/Md7dz1kAAAAASUVORK5CYII='],
 1: ['iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAwUlEQVQ4EYXBMRLAQAjEMPv/j94UwA1UkeSH/JAWNhnSwiVFWrikSAuXFGnhkiItXFKkhUuKtHBJkRYuKXKEIUWOMKTIEYYUOcKQIkcYUuQIQ4ocYUiRIwwpcoQhRY4wpMgWHimyhUeKbOGRIlt4pMgWHimyhUeKbOGRIlt4pMgWHimyhUeKbOGRIlt4pMgWHimyhUeKbGFIky0MabKFIU22MKTJFoY02cKQJlsY0mQLQ5psYUiTLQxpsoUhTX7Ijw9U1SwxA//kkAAAAABJRU5ErkJggg==',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAwUlEQVQ4EYXBwQ0CQRAEsar8g27Uy5wQs4+z5YW8kFs4pOQWDim5hUNKLuFLSi7hS0qW8JCSJTyk5E/4kZKf8EdKjnCTkiPcpOQINyk5wk1KjnCTkiU8pGQLQ0q2MKRkC0NKtjCkZAtDSrYwpGQLQ0q2MKRkC0NKtjCkZAtDSrYwpGQLQ0q2MKRkC0NKtjCkZAtDSrYwpGQLQ0q2MKRkC0NKtjCkZAtDSrYwpGQLQ0q2MKRkC0NKtjCkZAtDSl7Iiw+8+SwxK8enHQAAAABJRU5ErkJggg==',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAArUlEQVQ4EYXBAWocARDEQOn/j+4YDiUTH8tWyQt5IS/khfw1/pHIx/iPRH6M3yTC+CYRxjeJML5JhPFNIoxvEmF8yIhEGPIxIpFjRCLHiESOEYkcIxI5RiRyjEjkGJHIMSKRY0Qix4hEjhGJHCMSOUYkcoxI5BiRyDEikWNEIseIRI4RiRwjEjlGJHKMSOQYkQjjmQjjmQjjmQjjmQjjmQjjmQjjmcgLeSEv5MUfl0kqMfiXOK8AAAAASUVORK5CYII=',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAwUlEQVQ4EYXBAU4jARADwe7/P9pHMDHDSatUyQfygXwgVygZOcIPGfkV3mTkLfySkQqXjHwLf8jIS/hLRiD8T0YIb4aSEUIJoWSE8CJfQskI4Yu8hJIRAsi3UDJyhZKRK5SMXKFk5AolI1coGblCycgVSkauUDJyhZKRK5SMXKFk5AolI1coGblCycgVSkauUDJyhZKRK5SMXKFk5AolI1coGblCycgVSkYIz0QIz0QIz0QIz0QIz0QIz0Q+kA/kg3/lsC8xAl3uhgAAAABJRU5ErkJggg==',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAvklEQVQ4EYXBgVEbAAwAMf3+Q7ukAQxuepHyRt7INb6FHGOFHGOF/DZ+CPlp/BLyw/gtZI0j5Nu4Qj6Nf4U8jRdCnsYLIQ/jpZAP47UQxn+EfBivhTyML40V8td4ylghT+Mhxgp5Gh/CWCGfRh7GCvkyeRgr5Bgr5Bgr5Bgr5Bgr5Bgr5Bgr5Bgr5Bgr5Bgr5Bgr5Bgr5Bgr5Bgr5Bgr5Bgr5Bgr5Bgr5Bgr5Bgr5Bgr5Bgr5Bgr5Bgr5I288QflfjIxDP6XdQAAAABJRU5ErkJggg=='],
 2: ['iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAvUlEQVQ4EYXBgXHCQBAAMW3/RV8C/g8Q7LGUG7mRG7mRN+OQl2zjXZYs41MOeRgn8pCHcSa/wrgQYlwJYVwIeRhPOYwl8jTINpbIMnkZh8iZcYicGYfIibFETowlcmIcQk6MQ8i3sYR8GUt+5ctY8iv/jCVP+TS2POXD2HLIu7FlybuxZcnL2PInf8aWl2xjybssY8u7HMaWD3kYW/7Jw9jyTxiXEuNaYlxLjGuJcS0xriXGteRGbuRGbuTGD/SGKjHFXjJkAAAAAElFTkSuQmCC',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAtElEQVQ4EYXBAZKiUBQAsfT9D/2WdeCLCkWSB3mQB3mQB3kbf3KSP+NTdjEu5SXGtfwX406IcSfEuBUxdtmMk4ixyTLeEoOcjCW5MA7JhXFILoxDcmEckgvjkPwah8ivcYj8GEvk21hCvowlm3wah7zkw1jykrNxyC4nY8kuy1iyZBlLluzGkpPsxiFneRlLPmQz3vIpm7HkS4x7iXEvMe4lxr3EuJcY9xLjXvIgD/IgD/LgH3wWKTF9PU9FAAAAAElFTkSuQmCC',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAx0lEQVQ4EYXBCXKDQBAAMfX/Hz2xDWx8QCHlRm7kRt6NTZYs40122Y0vecnLOJGHPI1TIU/jVMjDuBB5GIc8jEOEccjLOCSMTZaxSRibLGOTPIyXLGOTnBqb5NTYJGfGLjkzdsmJsYv8GruQX2MX8mMcQr6MJQ/5NJY85cNY8pJ3Y8kmb8aSXZaxZMlhLPmX3VjyJptxyIdsxi6f8jIO+ZSnscu3PI1dvoVxyI8wdvkV41piXEuMa4lxLTGuJca15EZu5EZu/AHrXS4xvGo5YAAAAABJRU5ErkJggg==',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAvklEQVQ4EYXBAZKiUBQAsfT9D/0WVD64DkWSB3mQB3mQq/GSU5ZxyiEf41ve8jJ+ZZfd+Es22Yy/hTBuhDDuRDbjRmQzDmGckt14yW6ckpdBPsaSvI0cxpL8GofIr3GI/BhL5Mc4hPxvLCH/GaeQb+OUTb6MU3a5Gqe85GKc8paLseQjp7HkkGUsWXIYS075GEsu8jaWXOVlLPmS3VjyLZtxJ2HcSox7iXEvMe4lxr3EuJcY95IHeZAHeZAH/wDdcCsxOL5JQgAAAABJRU5ErkJggg=='],
 3: ['iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAxklEQVQ4EYXBgXHCQBAAMW3/RV9s3sGEPIOUL/JFvsiLcclTnsarLLmMN3nIaWyFnMZWyGHshRgfRRgfJaex5DSekodxyK9xSS4jt7EkW2NJtsaS7IxLsjEukf/GJeSf8SvkNv7IKbfxKg+5jVsuuY0/cspt/JVDbuNNyJvxIvLfeEq2xpJsjSXZGkuyNZZkayzJ1liSZchtLMnDOORpLMlhXHIaT4nxWWJ8ljA+CDmMvZDT2Mkhy3iXh/war3LJF/kiX+SLHzQTLzGEi+EUAAAAAElFTkSuQmCC',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAt0lEQVQ4EYXBgXGDQBAAMW3/RV+Ih7dj8gxSHuRBHuRBHuRtLPnIy7jIKYexk185jK0cchh7IYdxI3IYNyKHIW/jIzlM/hpvycZYko2xJBtjSTbGKbIxTpF/xlvkYnyELOMiv7KMb3nJMr7lJcu4yiHL+CdkGf9FLsYfkY2xJBtjSXbGKdkZp2RnnJKdcUo2xpIY8mUsiXHI2/hIjFsR41bEuBNi3MghxlZechhXWfIgD/IgD/LgB/cJKjGj+AoUAAAAAElFTkSuQmCC',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAA0UlEQVQ4EYXBAZLbIAAEMO3/H73FBufIhI6leBEv4kW8iF3d4k981CaWeNSXmGKqH3GJWx3EEJc6CuJSR0EM9YihliCGmmKpKQS1xFJTCGqKR00hbjXEo6YQJzWFOKkpxEndgjioKYhftQSxqV1cYlO7uMSmPmKJTT3iEZvaxC029SWG2NS3IA5qCXFSU4ijmiKOaoo4qilCTfGnpgi1xEdNEdQSSy0R1BJLLRFDPWKoR4ih/iPEpY6CuNRREFP9iiEe9S1u8VGbWOJFvIgX8eIfQJQyMS5pXLIAAAAASUVORK5CYII=',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAvklEQVQ4EYXBAZKCQBAAsfT/Hz0npwsqWCS5kRu5kRs5jJcc8jI+5CVP40ue8jCuZBPjhzyE8UPIw7gWshnXIptxLfJvkKexi/wb8jJ2kbOxRM7GS8jJWEJOxhLyaeyyyTK+ZJNlfMhTlvEuL1nGmyxZxoc8ZRlfsskyTkKWcRLybRwiJ+OQnI1dcjZ2ydnYJWdjlxjyZhwSgxzGITF+ihg/RYxfQoxfQoxr2cS4lk0YF/KUf+NTltzIjdzIjT99JCwxQJU5YgAAAABJRU5ErkJggg=='],
 4: ['iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAyElEQVQ4EYXBiRHCQBDEQCn/oAdm/QDGruuWBVmQBVmQBVmQBfkXhpT8C0NKrsJOSq7CTkouwkFKLsJBSn6Fk5T8CB9S8iN8SMmX8E1KvoRhKCn5CENCSckpDCGUlJzCEEJJySEMgVBSsgsbgVBSsglDKpSUjLCRCiUlIwwZoaSkwpBNKCl5CxvZhJKStzBkF0pKIAw5hJISwjMRwjMRwjMRwjMRwjMRwjORG6Gk5EYoKbkRSkpuhJKSG6GkZEEWZEEWZEEWZOEFSY4vMZLtAqEAAAAASUVORK5CYII=',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAx0lEQVQ4EYXBAQ6DMBDEQPv/j96y9FogEsqMbMiGbMiGbMiGbMgi/EjJU/iTkqfwJyUP4SIlD+EiJTfhTkpuwp2UXMKDlFzCwTCk5CecDENKfkJJGFIywknCkJIRSghDSr5CCYQhJV+hBMKQklMoOYQhJRVKKgwpOYSSUxhScgglpzCkBELJVxhSQigZYUgJoWSEISWEdyKEdyKEdyKEdyKEdyKEdyKrMKRkFYaUrMKQklUYUrIKQ0pWYUjJhmzIhmzIhmzIxgeGqzAxqsVT9wAAAABJRU5ErkJggg==',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAA0UlEQVQ4EYXBgRGDQBADsd3+i3bwhUCAYV6SBVmQBVmQBVmQu7CTkruwk5Kb8CMlN+FHSq7CQUquwkFKLsJJSi7CSUr+hDIMKfkTyjCk5BRKwpCSUygJQ0oOoYQwpOQQSghDSn5CCYQhJbtQsglDSnahZBOGlHyFkgpDSkYoGWFISYWSrzCkpELJVxhSsgkluzCkZBNKdmFICaHkEIaUEN6JEN6JEN6JEN6JEN6JPIUhJU9hSMlTGFLyFIaUPIUhJU9hSMlTGFKyIAuyIAuyIAsfFKE0MVxlC4cAAAAASUVORK5CYII=',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAw0lEQVQ4EYXBAW7DMBAEsZn/P3rrrc5JLMAQKQdyIAdyIAdyILswpGQXhpRswk1KNuEmJU/hQ0oewpeUPIQvKfkRfknJj/BLSr7Cg5R8hQcp+QhPUnILGykZYTEMKRlhMQwpWcIiYUjJv7AIYUjJv7AIYUhJhUUgDCm5hEUuYUjJJSxyCUNKICxS4SYXIbwTIbwTIbwTIbwTIbwTIbwTIbwT2YUhJbswpGQXhpTswpCSXRhSsgtDSg7kQA7kQA7kQA7+AFXELDFHCtGpAAAAAElFTkSuQmCC'],
 5: ['iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAvklEQVQ4EYXBAU4kMRAAMdf/H91HEhahm6Cx8yIv8iIv8iLHuAg5xkXIMS5CjnERcoyLkGNchGzjJmQbWx6yjS0P2caWh2xjy0O2seQpy9jylGVsjSM/soynbFnGRZYs4ypkGVchy7iLLOMusowt2/iRXI0juRpHcjWO5G5syd3YkruxJVfjSL5NfhlHcoz8Mo5kGUu+jY/kyziyjY+I8ZcQxh9ClnGTL1nGRZYc4z858jF+yUde5EVe5EVe/AODOSwxIz6QXgAAAABJRU5ErkJggg==',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAuUlEQVQ4EYXBgY3bQBAAMU7/RW/OeuvhJGuIzIM8yIM8yIMcYxdyjF3IMXYhx9iFHGMXcoxdyDF2IcfYhRzjkkWOcckix7hkkWNcssgxLlnkGP/KLcf4X37kGJu85BirHDnGLuQYX0SO8ZKX8SFyTD6NX8li3JLFuCWLcUs24y3ZjLdkM96SzXhLFuOWGPnbuCUG+TB+JcaPvIwPEeOriPFNiPFFjhi7vMRY5ZLL+FtueZAHeZAHefAHKNcrMXPpmX4AAAAASUVORK5CYII=',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAy0lEQVQ4EYXBgXHcMBAAMWz/RV8oSu8k8/QIyIu8yIu8yGUchVzGUchlHIVcxlHIZRyFXMZRyDJu+ZZl3PIty7jlW5Zxy7cs45ZvWcaWgyxjy0GWseUgy9jC2PKRZWyNf2TLMk5yyTKOsoTxixDGbyKMH1nGj4TxkW18JIxHHuORHI1bcjRuydnYkrOxJWdjS87GlpyNLTFu+WvcEuOWH+ORGI98jEfC+MhlfEQYv4lcxlHIZZxkyTa+5ZLH+F9u+TH+kUde5EVe5MUf5O4xMR0DUqwAAAAASUVORK5CYII=',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAt0lEQVQ4EYXBAXKcQBAAMfX/Hz1ZHMO5jqWQ8iIv8iKHsRVyGFshh7EVsoy9kGXshSxjL2QZeyHL2AtZxl7IMvZClnHKtyzjlG9ZxinfsoxfuQnjlJswbnIKYyc/wtjKIYy9LGE8CGE8CGE8iTAeJYfxILkZH8nN+EjuxiW5G5dkY5ySu3FJ7sYluRuXxFhyGR+J8V8O46/EeJYYjyLGkxDjSYjxIEuMvRzCuMuvHMaXnPIiL/LiHyh6LDHIgpZZAAAAAElFTkSuQmCC'],
 6: ['iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAA20lEQVQ4EYXBgXGDQBAEMG3/RW+A+3ecGA9SPIgH8SAexLsa8RK/6lcssdUfMWKp/+IUoz7FIS51Iw5xqTtBnGoLtQVxqhGXWkIcasRSI8ShRiw1QlBLfApqxI2gRtwI6hJ3Qo041BIj1Aj1Jk6hRtQfcQj1TRDqmyDUVyHUm6BeItRLXGqLUFsstURQS2w1IqglthoR1IiXGhHUEluNiEON2GpEHGrEViPiUCOWWiJONWLUEnGqLaiXiEvdCnGpO0Fc6k4QS32IQ2z1T5zipd7FiAfxIB7Eg3jwAx6gOjGQjoVvAAAAAElFTkSuQmCC',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAA2ElEQVQ4EYXBAZKCQBAEsPT/H93HOqt4BRZJPIgH8SAexD+1xRZf6lsscar/4hBvdRViq6sgRt0I4qVuxCGWeouXIpZYaoutxBJLjfhovMShRlzFoUZcBbXFVVAjbgQ1Qr3FCGqkvsUS6l4soX4JQv0ShPophPoS6iOEeouttgg14qO2CDXiVCNCjTjViFBbnOolQm1xqpcIasSpXiKoER81Iqgt3mpEHGrEVlvEobYYtUUstcVSW4ilbgWx1K0gRl3FIUZdxBJv9U+MONUptngQD+JBPIgHf5hsOTFXQ88GAAAAAElFTkSuQmCC',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAzklEQVQ4EYXBgXHCQBAAMW3/RV8M/yYkhrGUG7mRG7mRG/lrbFnybrzLIS/jInIaV5FtfBBZxieRp/FR5GmcchoiD+OUXxNyGFsuchhLrnIYS67C2HIVxpZxyhLG1viVpxhf5BDjixxifBUxvooYb8J4SYyXLGNLjJcsY0uMlyxjS4xTTmNJGFtOY0kYW05jSRhbTmNJDmPJaSzJYWxZxpYcxpZlbMnD2PIwtsjT+CjyND6KLOMqh2zjvzzkNP7KU96Ml2y5kRu5kRu5kRs//q41MaBNrkoAAAAASUVORK5CYII=',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAA40lEQVQ4EYXBgXGDQBAEMG3/RW+Ae7+dmAxSPIgH8SB+qVO8xYfaYomtPsWIpf6KUyz1JQ4x6kYQl7oTxKle4lAjiFONGDVCnGrEqBHiUCNeKkYc6hI3ghpxI6hL3AnqEneCusSdUCOolxihRqi3uIQaqd/iEOo/Qaj/BKE+hNpCqC0utYRQW1zqJUItsdWIUEtsNSLUEluNCDXiQ10iqBFvdYmgRmw1IqgRW42IQ414qRFxqBFLLRGnGjFqiTjVEqdaQpzqVhCXuhPEqG9xiKX+ilNs9SlGvNVbLPEgHsSDePADWlU+MVpsxNsAAAAASUVORK5CYII=',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAzElEQVQ4EYXBAZKCQBAAsfT/Hz0nnAsqWiS5kRu5kRu5GEvIu/Ei5NV4E3IaH0KWcRHyNK5C/o0vQnbjm5Dd+CZkM055k81Y8iEPY8mnPIynXISx5CKMJRdhPMVYsgvjKeOUTYyl8SbE+CXE+Cli/JYYvyXGixinxDhlM5bEOGQ3lsQ4ZDeWxDhkN5bEOGQ3lsQ4ZDeWhLFkN5aEcchmLAnjkM1YkofxS7IZPySb8V1kN74J+Teu8pCn8SmbHMar/MtpnPKUG7mRG7nxB2IJNTF/n0tVAAAAAElFTkSuQmCC'],
 7: ['iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAuElEQVQ4EYXBgRHDIBAEsd3+i77EPMQ4hkGSAzmQAzmQAyHsiRD2RAh7IoQ9EcKeCGFPhLAnshQaQZZCI8hKaARkIRQBWQhFQBZCI1/yFop8yVto5CIvochFXkKRi7yERhr5Fxop8icUKfIUOinyFDop8hSKdPIUGhnkIRQZZBY6GWQWOhlkFor8yCQUuckkFLnJLXRyk1soMpFbKDKRn1BkJkPoZCZD6GQmQyjyIAdyIAdyIAdy8AHj8CUxYvvzGwAAAABJRU5ErkJggg==',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAtElEQVQ4EYXBAZLDIBAEse7/P3ouZ+/GYEIhyYEcyIEcyIEQ9kQIeyKEPRHCnghhT4SwJ0LYEyHsifwQiiA/hCLIKjRBFqEJyCI0AVmEIh+yCEU+5C0U+ScvochFXkKRi8xCk4vMQpOLzEKRm8zCTYpMQpEio1CkySgUaTIITZoMQpMmj9DkSx6hyEMeochDvkKRgbTQZCAtFBlJC0VGUkKTkZRQZCIl3GQmB3IgB3IgB3LwBxzFJTHddCdbAAAAAElFTkSuQmCC',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAwElEQVQ4EYXBCXKEMADEQOn/j55sGAw2R9EtH+SDfBDCOxHCOxHCOxHCOxHCOxHCOxHCO5FHoUQehRJ5EkqQJ2EjIA9CCchdKPmRu1DyIzeh5J9chZKNXIWSjVyEnWzkImxkJ6tQspNV2Mggi1AyyCKUDLIIJYPMQslBJqHkJJNQcpJTKJnIKZRM5BRKJnIKJRM5hJ1M5BBKZnIIJTMZwk5mMoSdzGQIJQsZQslChlCykCGULGQIJQv5IB/kg3z4A7ORKTGpjB/cAAAAAElFTkSuQmCC',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAtklEQVQ4EYXBARaaQBBAsfz7H3pai7uglkeSB3mQB3kQ415i3EuMe4lxLzHuJca9xLiXGPcS417yH+Mt8msskR9jCfkxlpAfYwn5NraQb2PJX/kylrzky1jykk9jy0s+jS0v+TC2/JMPY8khV2PLIVdjyyFXY8lbLsaWt5zGliWnsWXJaWxZchpLtmxjy5ZlbDllGVtOWcaWU97Glou8jSVXOYwtVzmMLVc5jC1XeZAHeZAHefAHltMnMbO8ACYAAAAASUVORK5CYII='],
 8: ['iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAA00lEQVQ4EYXBgXHcMBAEMGz/RW/E50kf25ohEAdxEAdxEAdxEAfxQxH/i6/6ihG3+iG22OqPWOKjXsQllnoVxFLvQiz1LsSlbrHULeJSI7YaEZfaYtSIuNQWo0bEpbYYNSIutcWoLcRSHzFqC7HUiKW2IJYacakRxEe9CWLUb7HEqF/iIz7qRVxiqVdBXOor9QjiUiOWuoWgRowaEdSIUSNCjXjUFqFGPGqLUCMetUWoEY/aItQtRo0IasSoEUE9YqlbBPUV6hHiIA7iIA7iIA7i4B//qDcxyj0VEQAAAABJRU5ErkJggg==',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAA30lEQVQ4EYXBiVHDQAAEMG3/RS/3xSTEjKV4EA/iQTyIB/GulvgVl3oTR7zUh9hiqy8xxVI3YoipbgUx1a0ghtriqC3EUEtcagkx1BKXWkIMtcSllhBDLXGpJcRQS1xqCTHVFkttQUx1xFBHEEt9iym2+hJTvNSH2OKl3sURW/0VSyz1LaaY6k4MMdUWUx1BDHXEUkcIaotLbRHUFpfaItQRl9oi1BZvaolQW7ypJUIdcaktgtriUlsEdcRRR8RQ/wgx1D9CTHUriKVuxBBH/RFLvNSH2OJBPIgH8SAe/ADsSDgxTxVUnwAAAABJRU5ErkJggg==',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAA1ElEQVQ4EYXBgW3DMBAEMN7+Q19l+1UEiAORcRAHcRAHcRAfasS/+FcfYsSjvsQlbvUilrjUqyCW+iHEUj+EWGrErUYIaotbjRDUiFGPENSIUY8Q1IhRjxBLPWLUI8RSI241QlxqC7UFcasXscSjvsQltvoUIx71JS5xqxexxFLvglhqxK1GCGrEo0YIasSoEaG2GDUi1IitRoQasdWIUCO2GhFqi1EjQm3xqC2C2uJWW8RSP4RY6ocQl3oVxK1exBKP+hKX+FcfYsRBHMRBHMRBHPwBnSg3MS1aAMsAAAAASUVORK5CYII=',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAA6UlEQVQ4EYXBgY2kQBAEMFf+QdfD9MDyJyTs+BAf4kM81RI/cauH2GKrP2KJpV7EIU71KohTvQriUFuc6hLiUFsstYWgtthqhKBGXGqLoEZcaougRlxqi6BGXGqLoEZcaoQ41IitRohDjRg1gjjVFtQliKVexCG2+iOWuNVDbHGp/8SIpV7EIU71KohTjTjVFgS1xVYjBDXiViNCjfipEaFGPNQSoUY81BKhRjzUEqFGPNQSoUb81IhQW9xqRKgtbjUiqEssdYmgLnGqS4hTvQriVK+CWOpFHGKrP2KJWz3EFh/iQ3yID/8AzvBBMbJiWMcAAAAASUVORK5CYII=',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAA2ElEQVQ4EYXBCXKEMAADMPn/j3ZDSNij7CDFg3gQD+JBvKspXuJSb2KJrT7FFKf6L4Y41K0gDnUriKF+CDHUDyGGuoS6hKC2mGqLoLaYaosYaomplhBDLTHVEmKoS6hLiENtobYgDnUriKluxBCn+icOsdSXmGKrd7HEUp/iFKf6FlMc6k4McahbQQx1iXoJQb2EuoRQl5hqi1CXmGqLUFsstUSoLZZaItQWSy0R6hJTbRHqTaiXCPVbBPVLiKF+CHGoW0FMdSOGONW3mGKrD3GKB/EgHsSDPxi/ODFEKA0AAAAAAElFTkSuQmCC'],
 9: ['iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAA10lEQVQ4EYXBCZKCQAAEsPT/H90Lc4iuWCTxIB7Eg3gQH+oQb+KlLrHFVu9iian+iyGG+hanONWdOMSh7gVxqHtBUFucagmC2mKoKQi1xFZTCLXEVlMItcRWUwg1xaWmCLXES00R1BRbLRHUElNtEdQSU20R1CXUJeJQv0Sc6oeIU/0QMdSHqCFiqUuoIWKpS6gh4l4NEfdqiLhXQ8S9GiIuFVsNEaeaYqkhxKmmmGoKcaotqCWIoe4EMdSdIKb6FodY6ksc4qU+xBCXehNTPIgH8SAexIM/idE5MZcUWRQAAAAASUVORK5CYII=',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAA10lEQVQ4EYXBAXKcQBAAMfX/Hz052MVcyriQ8iIv8iIv8mUsueXHuOWSy/iWLcv4JYecxm855DAehRzGo5CPseUwthDGlmVsEcaWbSwRxpLL2BJjy4+xJMaS21gSY8ltLImx5TZOibHlNk4JY8ltnBLGlstYEsYly9iSj/GX5DD+kBzGH5LTeJZs40tjSS7jR8aSfBmHMJbkydiSJ2NLnowl8mQskWVyG0vIMnIZW8gyyGlcQg7jST5yGA9yyMd4kFM+xm9Zchr/yyXL+JYfeZEXeZEXefEPDA45MdYk0s4AAAAASUVORK5CYII=',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAAzUlEQVQ4EYXBgXECMRAEMG3/RW8wvieEPGMpDuIgDuIgDuIg3tUSb+KlfsUlRv0VW2z1KZ5iqRuxxFJ34iEe6hLUJYiHGrHUCIIasdUIQW0xaoSgthg1QqgRo0YINWLUJUKNGHWJUCNGXSKoEVtdIqgRW10iqEss9RLxUN9EPNQ3EUt9EfFU9yK2epfaIl5qhNoi7tQW4k5tIW7UCHGjtiD+qxHEUnGplyCWuhFLLHUjlljqv3iKpT7FiKU+xCWe6l38ioM4iIM4iIM4+AHeAjMxTk3/WAAAAABJRU5ErkJggg==',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAA4UlEQVQ4EYXBAXKDQBADMPn/j3aBPSCdkEGKF/EiXsSnOsQtLnWLUyz1TyxxqC9xiF09iF3s6kHsYlPPgtjUEps6BUEtMWoEQY1YagShljjVCKFGXGqEUCNuNSLUiFuNCDXiViNCjbjViFAjbjUi1BKnWiKoJUadIqglRp0iqFPs6hKxqV8idvVDxK5+iBj1KeoQsdQt1CHiUofY1Ih4VCPiUY2IR3UI8aRGiKXiVCMIasRSIwhqxFIjiE0tsalTEJt6FJvY1YPYxa6+xSEO9SUOsdQ/scSpbnGJF/EiXsSLP9HKPjEDi/NuAAAAAElFTkSuQmCC',
     'iVBORw0KGgoAAAANSUhEUgAAACAAAAAwCAAAAABVxyezAAAA1ElEQVQ4EYXBgXGDQBAAMW3/RV8A88SxySDlQR7kQR7kzTjkTS7jV5acxl95ycv4lEMO41t22Y072WQz7oVsxr2QzbjEuEQYlzAuEcaSw1gSxpLDWBLGksNYEsYpL2NJGEsOY0kYSw5jSRhLDmNJGJdsxiVhvGm8STbjP8lm/CfZjP8ku/FH45QcxrvGKXkZvzJOyWksMU7JjXGK3BinyLdxCvk2TiGfxiXkw/gVshs3sstu3Mguu/Eth+zGl7xkNz5kyW58yJLdeJN3eZAHeZAHefADa2A2MQsLJoAAAAAASUVORK5CYII=']}


def decode_templates():
    result = {}
    for digit, encoded_list in _TEMPLATE_PNGS_B64.items():
        result[int(digit)] = []
        for encoded in encoded_list:
            raw = base64.b64decode(encoded)
            img = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            _, img = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
            result[int(digit)].append(img)
    return result


TEMPLATES = decode_templates()


def normalize_digit(binary: np.ndarray, width: int = 32, height: int = 48, pad: int = 2) -> Optional[np.ndarray]:
    ys, xs = np.nonzero(binary)
    if len(xs) == 0:
        return None

    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    glyph = binary[y0:y1, x0:x1]

    scale = min((width - 2 * pad) / glyph.shape[1], (height - 2 * pad) / glyph.shape[0])
    new_w = max(1, int(round(glyph.shape[1] * scale)))
    new_h = max(1, int(round(glyph.shape[0] * scale)))

    resized = cv2.resize(glyph, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
    canvas = np.zeros((height, width), dtype=np.uint8)

    ox = (width - new_w) // 2
    oy = (height - new_h) // 2
    canvas[oy:oy + new_h, ox:ox + new_w] = resized
    return canvas


def iou_with_small_shifts(a: np.ndarray, b: np.ndarray) -> float:
    aa = a > 0
    bb = b > 0
    best = 0.0

    for dy in range(-2, 3):
        for dx in range(-2, 3):
            shifted = np.roll(np.roll(bb, dy, axis=0), dx, axis=1)
            inter = np.logical_and(aa, shifted).sum()
            union = np.logical_or(aa, shifted).sum()
            if union:
                best = max(best, float(inter) / float(union))

    return best


def classify_digit(binary: np.ndarray):
    normalized = normalize_digit(binary)
    if normalized is None:
        return None

    scores = {}
    for digit, candidates in TEMPLATES.items():
        scores[digit] = max(iou_with_small_shifts(normalized, t) for t in candidates)

    ranking = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    digit, confidence = ranking[0]
    second = ranking[1][1]
    return digit, confidence, confidence - second, normalized


def largest_component(mask: np.ndarray, min_area: int):
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)
    best_index = None
    best_area = 0

    for i in range(1, count):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area >= min_area and area > best_area:
            best_index = i
            best_area = area

    if best_index is None:
        return None, 0

    component = (labels == best_index).astype(np.uint8) * 255
    return component, best_area


def extract_digit(roi: np.ndarray, cx: int, cy: int, scale: float):
    """Extrai o digito central sem confundir o arco branco com o numero.

    A versao anterior escolhia o maior componente branco da regiao. Dependendo
    da posicao do arco de progresso, um pedaco do arco podia ser maior que o
    digito e acabava sendo classificado como 0/4/etc. Aqui avaliamos todos os
    componentes plausiveis e escolhemos o que realmente se parece com um digito
    e fica perto do centro do circulo.
    """
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # Regiao um pouco maior, mas com filtros geometricos fortes abaixo.
    x0 = max(0, int(round(cx - 46 * scale)))
    x1 = min(roi.shape[1], int(round(cx + 46 * scale)))
    y0 = max(0, int(round(cy - 43 * scale)))
    y1 = min(roi.shape[0], int(round(cy + 43 * scale)))

    sub = hsv[y0:y1, x0:x1]

    # Branco/cinza claro do numero. Saturacao <= 50 evita que fundos ciano/azulados
    # moderadamente saturados sejam unidos ao glifo; valor alto preserva antialiasing.
    mask = ((sub[:, :, 1] <= 50) & (sub[:, :, 2] >= 175)).astype(np.uint8) * 255

    # Remove pontinhos soltos sem deformar o glifo.
    kernel = np.ones((2, 2), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)

    target_x = (x1 - x0) / 2.0
    target_y = (y1 - y0) / 2.0

    min_h = max(24, int(round(30 * scale)))
    max_h = int(round(72 * scale))
    min_w = max(7, int(round(8 * scale)))
    max_w = int(round(58 * scale))
    min_area = max(55, int(round(90 * scale * scale)))
    max_area = int(round(2300 * scale * scale))

    ranked = []

    for i in range(1, count):
        x, y, w, h, area = map(int, stats[i])

        if not (min_h <= h <= max_h):
            continue
        if not (min_w <= w <= max_w):
            continue
        if not (min_area <= area <= max_area):
            continue

        center_x = x + w / 2.0
        center_y = y + h / 2.0
        dx = abs(center_x - target_x)
        dy = abs(center_y - target_y)

        # O numero fica no miolo. Esse filtro elimina sobretudo o arco branco
        # superior/lateral, que causava as leituras falsas de baixa confianca.
        if dx > 25 * scale or dy > 27 * scale:
            continue

        component = (labels == i).astype(np.uint8) * 255
        glyph = component[y:y + h, x:x + w]
        classified = classify_digit(glyph)
        if classified is None:
            continue

        digit, confidence, margin, normalized = classified

        # Priorizamos semelhanca com um numero real e usamos posicao apenas como
        # desempate. Um arco costuma ter conf ~0.55-0.65; numeros reais do video
        # ficam em ~0.85-0.98.
        pos_penalty = 0.0020 * (dx / max(scale, 1e-6)) + 0.0012 * (dy / max(scale, 1e-6))
        rank_score = confidence + 0.35 * margin - pos_penalty

        ranked.append((
            rank_score,
            confidence,
            margin,
            digit,
            (x0 + x, y0 + y, w, h),
            normalized,
        ))

    if not ranked:
        return None

    ranked.sort(reverse=True, key=lambda item: item[0])
    _, confidence, margin, digit, bbox, normalized = ranked[0]

    return {
        "digit": int(digit),
        "confidence": float(confidence),
        "margin": float(margin),
        "bbox": bbox,
        "normalized": normalized,
    }


def detect_target_mask(hsv: np.ndarray, annulus: np.ndarray, scale: float):
    """Detecta o arco colorido que marca a zona de acerto.

    A zona e detectada apenas enquanto ainda esta livre. Depois que o arco
    branco se aproxima, a mascara fica travada para a rodada inteira. O intervalo
    de matiz cobre os alvos amarelo/laranja/verde observados e exclui o fundo
    ciano/azulado do jogo, que na v3 podia ser confundido com o alvo.
    """
    target_raw = (
        annulus
        & (hsv[:, :, 0] >= 10)
        & (hsv[:, :, 0] <= 85)
        & (hsv[:, :, 1] >= 40)
        & (hsv[:, :, 2] >= 130)
    ).astype(np.uint8) * 255

    min_target_area = max(120, int(round(150 * scale * scale)))
    return largest_component(target_raw, min_target_area)


def detect_progress_mask(hsv: np.ndarray, annulus: np.ndarray, scale: float):
    """Detecta somente o arco branco que avanca pelo circulo."""
    progress_raw = (
        annulus
        & (hsv[:, :, 1] <= 32)
        & (hsv[:, :, 2] >= 188)
    ).astype(np.uint8) * 255

    min_progress_area = max(45, int(round(60 * scale * scale)))
    return largest_component(progress_raw, min_progress_area)


def distance_between_masks(progress: np.ndarray, target: np.ndarray) -> Optional[float]:
    if progress is None or target is None:
        return None

    target_inverse = (target == 0).astype(np.uint8)
    distance_map = cv2.distanceTransform(target_inverse, cv2.DIST_L2, 5)
    progress_distances = distance_map[progress > 0]

    if progress_distances.size == 0:
        return None

    return float(progress_distances.min())


def analyze_roi(
    roi: np.ndarray,
    cx: int,
    cy: int,
    scale: float,
    locked_target: Optional[np.ndarray] = None,
):
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    r_min = int(round(RING_R_MIN * scale))
    r_max = int(round(RING_R_MAX * scale))

    yy, xx = np.indices(roi.shape[:2])
    radius = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    annulus = (radius >= r_min) & (radius <= r_max)

    target_candidate = None
    target_area = 0
    if locked_target is None:
        target_candidate, target_area = detect_target_mask(hsv, annulus, scale)

    progress, progress_area = detect_progress_mask(hsv, annulus, scale)

    # O digito pode ser reconhecido mesmo antes do arco de progresso aparecer.
    # A distancia fica None ate haver progresso; o disparo continua bloqueado.
    digit_info = extract_digit(roi, cx, cy, scale)
    if digit_info is None:
        return None

    reference_target = locked_target if locked_target is not None else target_candidate
    min_distance = distance_between_masks(progress, reference_target)

    return {
        **digit_info,
        "distance": min_distance,
        "target_area": target_area,
        "progress_area": progress_area,
        "target_mask": reference_target,
        "target_candidate": target_candidate,
        "progress_mask": progress,
    }


def stable_digit(history: collections.deque):
    if len(history) < 3:
        return None

    counts = collections.Counter(history)
    digit, count = counts.most_common(1)[0]

    # Pelo menos 3 votos e maioria simples.
    if count >= 3 and count >= math.ceil(len(history) / 2):
        return digit
    return None


def key_edge(vk_code: int, previous: bool):
    current = bool(ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000)
    return current and not previous, current


def draw_debug(roi: np.ndarray, detection, cx: int, cy: int, scale: float, paused: bool, pressed: bool, armed: bool = False):
    debug = roi.copy()

    if detection is not None:
        target = detection.get("target_mask")
        progress = detection.get("progress_mask")

        if target is not None:
            target_contours, _ = cv2.findContours(target, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(debug, target_contours, -1, (0, 255, 0), 2)

        if progress is not None:
            progress_contours, _ = cv2.findContours(progress, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(debug, progress_contours, -1, (255, 255, 255), 2)

        x, y, w, h = detection["bbox"]
        cv2.rectangle(debug, (x, y), (x + w, y + h), (0, 255, 255), 1)

        distance = detection.get("distance")
        dist_text = "--" if distance is None else f"{distance:.1f}"
        msg = (
            f'digit={detection["digit"]} '
            f'conf={detection["confidence"]:.2f} '
            f'margin={detection["margin"]:.2f} '
            f'dist={dist_text}'
        )
        cv2.putText(debug, msg, (5, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

    if paused:
        status = "PAUSADO"
    elif pressed:
        status = "JA APERTOU"
    elif armed:
        status = "ARMADO - ESPERANDO ALVO"
    else:
        status = "AGUARDANDO MOVIMENTO"

    cv2.putText(debug, status, (5, debug.shape[0] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    return debug


# ---------------------------------------------------------------------------
# v6: deteccao conservadora por geometria do anel. A cor do alvo pode mudar;
# usamos brilho e saturacao apenas para separar alvo colorido e arco branco.
# O disparo nao extrapola a ponta no tempo: ele exige contato visual medido ou
# a fusao visual dos dois arcos quando a ponta ja esta imediatamente antes do alvo.
# ---------------------------------------------------------------------------
START_ANGLE_DEG = 270.0
POLAR_R_MIN = 60.0
POLAR_R_MAX = 76.0
DEFAULT_TARGET_FRACTION = 0.06
# v6 trabalha com scores normalizados (0..1):
# - progresso = brilho * (1 - saturacao)
# - alvo = brilho * saturacao
DEFAULT_PROGRESS_THRESHOLD = 0.44
DEFAULT_TARGET_THRESHOLD = 0.095
DEFAULT_MAX_HIT_OVERSHOOT = 18.0
DEFAULT_MERGE_PRECONTACT = 12.0
DEFAULT_COOLDOWN_SECONDS = 70.0
DEFAULT_E_RETRY_WAIT = 20.0
DEFAULT_MAX_PROGRESS_SPEED = 220.0
DEFAULT_MIN_PROGRESS_SPEED = 18.0


def circular_delta(a: float, b: float) -> float:
    """Menor diferenca assinada a-b em graus, no intervalo [-180, 180)."""
    return (a - b + 180.0) % 360.0 - 180.0


def circular_distance(a: float, b: float) -> float:
    return abs(circular_delta(a, b))


def circular_mean_deg(values):
    if not values:
        return None
    radians = np.deg2rad(np.asarray(values, dtype=np.float64))
    s = float(np.sin(radians).mean())
    c = float(np.cos(radians).mean())
    if abs(s) < 1e-9 and abs(c) < 1e-9:
        return float(values[-1]) % 360.0
    return math.degrees(math.atan2(s, c)) % 360.0


def circular_smooth(profile: np.ndarray, kernel_size: int = 9) -> np.ndarray:
    kernel_size = max(3, int(kernel_size) | 1)
    pad = kernel_size // 2
    ext = np.concatenate([profile[-pad:], profile, profile[:pad]])
    kernel = np.ones(kernel_size, dtype=np.float32) / float(kernel_size)
    smoothed = np.convolve(ext, kernel, mode="same")[pad:-pad]
    return smoothed.astype(np.float32)


def circular_runs(mask: np.ndarray):
    """Retorna runs True como (inicio, fim_unwrapped)."""
    mask = np.asarray(mask, dtype=bool)
    indices = np.flatnonzero(mask)
    if indices.size == 0:
        return []

    runs = []
    start = prev = int(indices[0])
    for raw in indices[1:]:
        value = int(raw)
        if value == prev + 1:
            prev = value
        else:
            runs.append((start, prev))
            start = prev = value
    runs.append((start, prev))

    if len(runs) > 1 and runs[0][0] == 0 and runs[-1][1] == 359:
        merged = (runs[-1][0], runs[0][1] + 360)
        runs = [merged] + runs[1:-1]
    return runs


def locate_ring_center(roi: np.ndarray, expected_cx: int, expected_cy: int, scale: float):
    """Localiza o centro real do circulo.

    O HUD do video se desloca alguns pixels entre rodadas. A v4 assumia o centro
    fixo, o que atrapalhava tanto o numero quanto a geometria do arco.
    """
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 1.2)

    min_r = max(42, int(round(50 * scale)))
    max_r = max(min_r + 5, int(round(88 * scale)))
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.15,
        minDist=max(24, int(round(28 * scale))),
        param1=100,
        param2=27,
        minRadius=min_r,
        maxRadius=max_r,
    )
    if circles is None:
        return None

    best = None
    for x, y, radius in circles[0]:
        dx = float(x) - float(expected_cx)
        dy = float(y) - float(expected_cy)
        center_distance = math.hypot(dx, dy)
        if center_distance > 32 * scale:
            continue
        # O raio pode variar dependendo de qual borda o Hough pegou; centro pesa mais.
        radius_penalty = abs(float(radius) - 72.0 * scale) * 0.12
        score = center_distance + radius_penalty
        if best is None or score < best[0]:
            best = (score, float(x), float(y), float(radius))

    if best is None:
        return None
    return best[1], best[2], best[3]


def angular_profiles(roi: np.ndarray, cx: float, cy: float, scale: float):
    """Perfis hue-independent do anel.

    A v5 usava limites absolutos de saturacao/brilho. Isso podia enxergar o
    cenario atraves do HUD como se fosse a zona de acerto. Na v6 amostramos
    apenas o miolo radial do anel e calculamos dois scores continuos:

      target_score   = brilho * saturacao
      progress_score = brilho * (1 - saturacao)

    Assim a cor do alvo pode mudar sem precisar conhecer o hue, enquanto o
    arco branco continua separado do alvo colorido.
    """
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    yy, xx = np.indices(roi.shape[:2])
    radius = np.hypot(xx - cx, yy - cy)
    angles = (np.degrees(np.arctan2(yy - cy, xx - cx)) + 360.0) % 360.0

    r_min = POLAR_R_MIN * scale
    r_max = POLAR_R_MAX * scale
    annulus = (radius >= r_min) & (radius <= r_max)
    angle_bins = np.floor(angles).astype(np.int16) % 360

    counts = np.bincount(angle_bins[annulus].ravel(), minlength=360).astype(np.float32)
    counts = np.maximum(counts, 1.0)

    sat = hsv[:, :, 1].astype(np.float32) / 255.0
    val = hsv[:, :, 2].astype(np.float32) / 255.0

    target_pixel_score = val * sat
    progress_pixel_score = val * (1.0 - sat)

    target_profile = (
        np.bincount(
            angle_bins[annulus].ravel(),
            weights=target_pixel_score[annulus].ravel(),
            minlength=360,
        ).astype(np.float32)
        / counts
    )
    progress_profile = (
        np.bincount(
            angle_bins[annulus].ravel(),
            weights=progress_pixel_score[annulus].ravel(),
            minlength=360,
        ).astype(np.float32)
        / counts
    )

    return circular_smooth(target_profile, 7), circular_smooth(progress_profile, 7)

def detect_target_arc(target_profile: np.ndarray, threshold: float = DEFAULT_TARGET_THRESHOLD):
    # O limiar e adaptativo, mas nunca cai abaixo do valor configurado. Isso
    # evita que um fundo muito colorido gere um alvo falso.
    median = float(np.median(target_profile))
    p90 = float(np.percentile(target_profile, 90))
    dynamic_threshold = max(float(threshold), median + 0.30 * max(0.0, p90 - median))

    runs = circular_runs(target_profile >= dynamic_threshold)
    candidates = []

    for start, end in runs:
        width = end - start + 1
        if width < 10 or width > 96:
            continue

        unwrapped = np.arange(start, end + 1, dtype=np.float64)
        indices = (unwrapped.astype(np.int32) % 360)
        weights = target_profile[indices].astype(np.float64) + 1e-4
        center_unwrapped = float(np.average(unwrapped, weights=weights))
        center = center_unwrapped % 360.0

        # O progresso nasce no topo. A zona de acerto real nunca deve ser
        # confundida com esse trecho inicial.
        dist_from_start = circular_distance(center, START_ANGLE_DEG)
        if dist_from_start < 38.0:
            continue

        mean_score = float(target_profile[indices].mean())
        peak_score = float(target_profile[indices].max())
        if mean_score < dynamic_threshold * 1.01:
            continue

        score = (0.75 * mean_score + 0.25 * peak_score) * math.sqrt(width)
        candidates.append({
            "center": center,
            "width": float(width),
            "start": float(start % 360),
            "end": float(end % 360),
            "score": score,
            "mean": mean_score,
            "threshold": dynamic_threshold,
        })

    if not candidates:
        return None
    return max(candidates, key=lambda item: item["score"])

def stable_target(history: collections.deque, min_width: float = 12.0, min_votes: int = 6):
    """Estima os limites reais da zona por voto angular entre varios frames.

    Cada frame fornece um intervalo candidato. Em vez de confiar no centro e na
    largura de um unico frame, contamos quantas vezes cada grau do circulo fez
    parte do alvo. O trecho presente em pelo menos ~55% das observacoes vira a
    zona estavel. Isso elimina tanto os segmentos espurios estreitos quanto os
    frames em que o fundo amplia artificialmente a zona.
    """
    usable = list(history)[-48:]
    if len(usable) < min_votes:
        return None

    counts = np.zeros(360, dtype=np.float32)
    quality = np.zeros(360, dtype=np.float32)
    for item in usable:
        width = int(round(float(item.get("width", 0.0))))
        if width < 8 or width > 96:
            continue
        start = int(round(float(item.get("start", 0.0)))) % 360
        idx = (start + np.arange(width, dtype=np.int32)) % 360
        counts[idx] += 1.0
        quality[idx] += max(0.05, float(item.get("score", 0.05)))

    valid_observations = max(1, len(usable))
    vote_threshold = max(float(min_votes) * 0.60, valid_observations * 0.55)
    runs = circular_runs(counts >= vote_threshold)
    candidates = []
    for start, end in runs:
        width = end - start + 1
        if width < min_width or width > 90:
            continue
        unwrapped = np.arange(start, end + 1, dtype=np.float64)
        idx = unwrapped.astype(np.int32) % 360
        # Centro geometrico do intervalo votado. Para o ponto de entrada, os
        # limites sao mais importantes que o pico de cor.
        center = float((start + end) / 2.0) % 360.0
        support_min = float(counts[idx].min())
        support_mean = float(counts[idx].mean())
        qmean = float(quality[idx].mean())
        score = support_mean + 0.05 * qmean
        candidates.append({
            "center": center,
            "width": float(width),
            "start": float(start % 360),
            "end": float(end % 360),
            "score": score,
            "support": support_mean,
            "support_min": support_min,
            "observations": valid_observations,
            "threshold": float(np.median([float(i.get("threshold", DEFAULT_TARGET_THRESHOLD)) for i in usable])),
        })

    if not candidates:
        return None
    return max(candidates, key=lambda item: item["score"])


def directional_distance(start: float, angle: float, direction: int) -> float:
    if direction >= 0:
        return (angle - start) % 360.0
    return (start - angle) % 360.0


def progress_extent(
    progress_profile: np.ndarray,
    direction: int,
    threshold: float,
    max_distance: float = 220.0,
    gap_allow: int = 3,
):
    """Comprimento do arco claro contiguo a partir do topo, numa direcao."""
    max_steps = int(max(1, math.ceil(max_distance)))
    started = False
    gap = 0
    last_bright = 0

    for distance in range(max_steps + 1):
        angle = int(round((START_ANGLE_DEG + direction * distance) % 360.0)) % 360
        value = float(progress_profile[angle])

        if value >= threshold:
            started = True
            last_bright = distance
            gap = 0
        elif started:
            gap += 1
            if gap > gap_allow:
                break
        elif distance > 18:
            break

    return float(last_bright)


def stable_digit_lock(observations: collections.deque, min_votes: int):
    if len(observations) < min_votes:
        return None

    recent = list(observations)[-max(min_votes + 4, 11):]
    counts = collections.Counter(item[0] for item in recent)
    digit, votes = counts.most_common(1)[0]
    required = max(min_votes, math.ceil(len(recent) * 0.68))
    if votes < required:
        return None

    matching = [item for item in recent if item[0] == digit]
    median_conf = float(np.median([item[1] for item in matching]))
    median_margin = float(np.median([item[2] for item in matching]))
    if median_conf < 0.80 or median_margin < 0.045:
        return None

    return int(digit), median_conf, median_margin, votes, len(recent)


def estimate_speed(samples: collections.deque, now: float):
    """Regressao robusta simples dos ultimos ~0.75 s do endpoint angular."""
    usable = [(t, p) for t, p in samples if now - t <= 0.45]
    if len(usable) < 5:
        return None

    times = np.asarray([item[0] for item in usable], dtype=np.float64)
    positions = np.asarray([item[1] for item in usable], dtype=np.float64)
    times = times - times[0]
    if times[-1] < 0.14 or positions[-1] - positions[0] < 8.0:
        return None

    slope = float(np.polyfit(times, positions, 1)[0])
    if not (DEFAULT_MIN_PROGRESS_SPEED <= slope <= DEFAULT_MAX_PROGRESS_SPEED):
        return None
    return slope


def reset_round_state():
    return {
        "center_samples": collections.deque(maxlen=5),
        "activation_streak": 0,
        "center": None,
        "radius": None,
        "target_history": collections.deque(maxlen=40),
        "target": None,
        "target_frozen": False,
        "target_lock_started": False,
        "direction": None,
        "digit_obs": collections.deque(maxlen=17),
        "locked_digit": None,
        "progress_samples": collections.deque(maxlen=120),
        "last_progress": None,
        "last_progress_time": None,
        "speed": None,
        "hit_streak": 0,
        "hit_window_started": False,
        "contact_mode": None,
        "armed_for_hit": False,
        "closest_gap": None,
        "ever_had_target": False,
        "pressed": False,
        "announced": False,
        "inactive_since": None,
    }


def update_round_state(roi, expected_cx, expected_cy, scale, state, args, now):
    # 1) Ativacao v7: localizamos primeiro o circulo e so depois validamos o
    # digito no centro REAL dele. Isso corrige rodadas em que a animacao nasce
    # 10-20 px deslocada do centro-base; nessas situacoes a v6 podia nao
    # reconhecer nada ou ler um numero usando o centro errado.
    if state["center"] is None:
        ring = locate_ring_center(roi, expected_cx, expected_cy, scale)
        if ring is not None:
            x, y, r = ring
            probe_digit = extract_digit(roi, int(round(x)), int(round(y)), scale)
            probe_valid = (
                probe_digit is not None
                and probe_digit["confidence"] >= args.min_confidence
                and probe_digit["margin"] >= args.min_margin
            )
            if probe_valid:
                state["activation_streak"] += 1
                state["center_samples"].append((x, y, r))
                if len(state["center_samples"]) >= 3:
                    xs = [item[0] for item in state["center_samples"]]
                    ys = [item[1] for item in state["center_samples"]]
                    rs = [item[2] for item in state["center_samples"]]
                    if (
                        max(xs) - min(xs) <= 14 * scale
                        and max(ys) - min(ys) <= 14 * scale
                        and state["activation_streak"] >= 3
                    ):
                        state["center"] = (float(np.median(xs)), float(np.median(ys)))
                        state["radius"] = float(np.median(rs))
                        state["digit_obs"].clear()
            else:
                state["activation_streak"] = 0
                state["center_samples"].clear()
        else:
            state["activation_streak"] = 0
            state["center_samples"].clear()
    else:
        # O centro do HUD oscila alguns pixels durante a animacao. A v8/v9
        # inicial congelava o primeiro centro encontrado; 1-2 px de erro ja
        # deslocavam os limites angulares do alvo em varios graus. Refinamos o
        # centro continuamente com uma mediana curta e rejeitamos saltos grandes.
        ring_now = locate_ring_center(roi, expected_cx, expected_cy, scale)
        if ring_now is not None:
            rx, ry, rr = ring_now
            curx, cury = state["center"]
            if math.hypot(rx - curx, ry - cury) <= 12.0 * scale:
                state["center_samples"].append((rx, ry, rr))
                xs = [item[0] for item in state["center_samples"]]
                ys = [item[1] for item in state["center_samples"]]
                rs = [item[2] for item in state["center_samples"]]
                state["center"] = (float(np.median(xs)), float(np.median(ys)))
                state["radius"] = float(np.median(rs))

    cx, cy = state["center"] if state["center"] is not None else (expected_cx, expected_cy)

    # 2) Numero: apenas depois do centro estar confirmado.
    digit_info = extract_digit(roi, int(round(cx)), int(round(cy)), scale)
    digit_valid = (
        state["center"] is not None
        and digit_info is not None
        and digit_info["confidence"] >= args.min_confidence
        and digit_info["margin"] >= args.min_margin
    )
    if digit_valid and state["locked_digit"] is None:
        state["digit_obs"].append((
            int(digit_info["digit"]),
            float(digit_info["confidence"]),
            float(digit_info["margin"]),
        ))
        locked = stable_digit_lock(state["digit_obs"], args.digit_lock_votes)
        if locked is not None:
            state["locked_digit"] = locked

    # 3) Perfis angulares: alvo e progresso.
    target_profile = progress_profile = None
    target_candidate = None
    if state["center"] is not None:
        target_profile, progress_profile = angular_profiles(roi, cx, cy, scale)

        # v9: varios frames votam nos limites angulares do alvo. Coletamos
        # desde que o circulo aparece, mas so usamos uma zona quando existe
        # consenso temporal suficiente.
        if not state.get("target_frozen", False):
            target_candidate = detect_target_arc(target_profile, args.target_threshold)
            if target_candidate is not None and 8.0 <= float(target_candidate.get("width", 0.0)) <= 96.0:
                state["target_history"].append(target_candidate)
                locked_target = stable_target(
                    state["target_history"],
                    min_width=args.min_target_width,
                    min_votes=args.target_lock_votes,
                )
                if locked_target is not None:
                    state["target"] = locked_target
                    state["ever_had_target"] = True

        # 4) Direcao real observada. Isso resolve o caso de alvo exatamente oposto.
        if state["target"] is not None and state["direction"] is None:
            plus = progress_extent(progress_profile, +1, args.progress_threshold, 120.0)
            minus = progress_extent(progress_profile, -1, args.progress_threshold, 120.0)
            if max(plus, minus) >= 12.0 and abs(plus - minus) >= 6.0:
                state["direction"] = +1 if plus > minus else -1
            elif circular_distance(state["target"]["center"], START_ANGLE_DEG) < 170.0:
                # fallback apenas quando nao ha ambiguidade de 180 graus
                delta = circular_delta(state["target"]["center"], START_ANGLE_DEG)
                state["direction"] = +1 if delta > 0 else -1

        # 5) v6: acompanha a ponta BRANCA real. Nao ha mais extrapolacao de
        # velocidade para decidir o disparo. Isso elimina o caso em que uma
        # estimativa fazia o bot apertar antes de a ponta chegar visualmente ao alvo.
        if state["target"] is not None and state["direction"] is not None:
            target_center_dist = directional_distance(
                START_ANGLE_DEG, state["target"]["center"], state["direction"]
            )
            target_width = min(82.0, max(args.min_target_width, float(state["target"]["width"])))
            target_entry = max(8.0, target_center_dist - target_width / 2.0)

            raw_progress = progress_extent(
                progress_profile,
                state["direction"],
                args.progress_threshold,
                max_distance=min(275.0, target_center_dist + target_width + 24.0),
                gap_allow=2,
            )

            previous_progress = state["last_progress"]
            accept = True
            if state["last_progress"] is not None and state["last_progress_time"] is not None:
                dt = max(1e-4, now - state["last_progress_time"])
                delta = raw_progress - state["last_progress"]
                max_step = args.max_progress_speed * min(dt, 0.05) + 3.0
                if delta < -4.0 or delta > max_step:
                    accept = False

            if accept:
                if state["last_progress"] is None:
                    state["last_progress"] = raw_progress
                else:
                    state["last_progress"] = max(state["last_progress"], raw_progress)
                state["last_progress_time"] = now
                state["progress_samples"].append((now, state["last_progress"]))
                estimated = estimate_speed(state["progress_samples"], now)
                if estimated is not None:
                    state["speed"] = estimated

            measured_progress = state["last_progress"]

            # Enquanto a ponta ainda esta longe, seguimos refinando o alvo. Ao
            # entrar nos 32 graus anteriores, congelamos a geometria para que o
            # proprio arco branco nao deforme a leitura da zona colorida.
            if measured_progress is not None and target_entry - measured_progress <= args.target_freeze_gap:
                state["target_frozen"] = True

            inside_degrees = max(1.5, target_width * args.target_fraction)
            desired = target_entry + inside_degrees

            if measured_progress is not None and measured_progress <= target_entry - 10.0:
                state["armed_for_hit"] = True

            gap = None if measured_progress is None else target_entry - measured_progress
            if gap is not None:
                if state.get("closest_gap") is None or abs(gap) < abs(state["closest_gap"]):
                    state["closest_gap"] = gap

            # Disparo principal: a ponta branca realmente alcancou a ENTRADA da
            # zona. Nao esperamos 30-40% do alvo, porque ao tocar o segmento
            # colorido ele passa a ser renderizado como branco e o endpoint pode
            # deixar de ser mensuravel.
            visual_contact = (
                state.get("armed_for_hit", False)
                and measured_progress is not None
                and measured_progress >= target_entry - args.entry_tolerance
                and measured_progress <= target_entry + args.max_hit_overshoot
            )

            # Quando o branco toca o alvo, o detector pode saltar diretamente
            # para o fim do segmento colorido. Esse salto e um excelente sinal
            # de contato, mas so e aceito se a ultima ponta valida estava muito
            # perto da entrada calculada.
            raw_anomaly = (
                not accept
                and previous_progress is not None
                and raw_progress >= previous_progress + 8.0
            )
            merge_contact = (
                state.get("armed_for_hit", False)
                and previous_progress is not None
                and target_entry - args.merge_precontact <= previous_progress <= target_entry + 2.0
                and raw_anomaly
                and raw_progress >= target_entry
            )

            if visual_contact:
                state["contact_mode"] = "entry"
                state["hit_window_started"] = True
                state["hit_streak"] += 1
            elif merge_contact:
                state["contact_mode"] = "touch-jump"
                state["hit_window_started"] = True
                state["hit_streak"] += 1
            else:
                near_target = gap is not None and -args.max_hit_overshoot <= gap <= 12.0
                if not near_target:
                    state["hit_streak"] = 0
                    state["hit_window_started"] = False
                    state["contact_mode"] = None

            overshoot = None if measured_progress is None else measured_progress - target_entry
            state["target_center_dist"] = target_center_dist
            state["target_entry"] = target_entry
            state["target_width"] = target_width
            state["desired_progress"] = desired
            state["raw_progress"] = raw_progress
            state["merge_contact"] = merge_contact
            state["overshoot"] = overshoot
            state["predicted_progress"] = measured_progress

    active = digit_valid or state["locked_digit"] is not None or state["target"] is not None
    return {
        "active": active,
        "digit_info": digit_info,
        "digit_valid": digit_valid,
        "target_candidate": target_candidate,
        "target_profile": target_profile,
        "progress_profile": progress_profile,
        "center": (cx, cy),
    }


def draw_debug_v6(roi, state, info, paused=False):
    debug = roi.copy()
    cx, cy = info.get("center", (debug.shape[1] / 2, debug.shape[0] / 2))
    cv2.drawMarker(debug, (int(round(cx)), int(round(cy))), (0, 255, 255), cv2.MARKER_CROSS, 12, 1)

    digit = info.get("digit_info")
    if digit is not None:
        x, y, w, h = digit["bbox"]
        cv2.rectangle(debug, (x, y), (x + w, y + h), (0, 255, 255), 1)

    target = state.get("target")
    if target is not None:
        radius = int(round(72))
        start_angle = target["center"] - target["width"] / 2.0
        end_angle = target["center"] + target["width"] / 2.0
        cv2.ellipse(
            debug,
            (int(round(cx)), int(round(cy))),
            (radius, radius),
            0,
            float(start_angle),
            float(end_angle),
            (0, 255, 0),
            2,
        )

    locked = state.get("locked_digit")
    digit_text = "--" if locked is None else str(locked[0])
    direction = state.get("direction")
    dir_text = "?" if direction is None else ("CW" if direction > 0 else "CCW")
    speed = state.get("speed")
    speed_text = "--" if speed is None else f"{speed:.1f}d/s"
    pred = state.get("predicted_progress")
    desired = state.get("desired_progress")
    pred_text = "--" if pred is None else f"{pred:.1f}"
    desired_text = "--" if desired is None else f"{desired:.1f}"

    lines = [
        f"digit={digit_text} dir={dir_text} speed={speed_text}",
        f"progress={pred_text} target={desired_text}",
    ]
    if paused:
        lines.append("PAUSADO")
    elif state.get("pressed"):
        lines.append("JA APERTOU")
    elif speed is None:
        lines.append("CALIBRANDO")
    else:
        lines.append("RASTREANDO")

    for i, line in enumerate(lines):
        cv2.putText(debug, line, (5, 18 + 18 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (255, 255, 255), 1, cv2.LINE_AA)
    return debug



def detect_e_prompt(roi: np.ndarray) -> bool:
    """Detecta o quadrado luminoso do prompt "E FARM DE MUNICAO".

    O prompt fica na parte inferior do mesmo ROI do minigame. A deteccao usa
    geometria + saturacao/brilho, sem OCR, para continuar leve em 120 Hz.
    """
    if roi is None or roi.size == 0:
        return False

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    h, w = hsv.shape[:2]
    y0 = int(round(h * 0.68))
    x1 = int(round(w * 0.72))
    sub = hsv[y0:h, 0:x1]
    if sub.size == 0:
        return False

    sat = sub[:, :, 1]
    val = sub[:, :, 2]
    # O botao E e um bloco verde/lima bem saturado e claro.
    mask = ((sat >= 95) & (val >= 145)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    for i in range(1, count):
        x, y, cw, ch, area = stats[i]
        if area < 260:
            continue
        if not (16 <= cw <= 55 and 16 <= ch <= 55):
            continue
        aspect = cw / max(1.0, float(ch))
        fill = area / max(1.0, float(cw * ch))
        if 0.55 <= aspect <= 1.55 and fill >= 0.45:
            return True
    return False


def detect_cooldown_notification(bgr: np.ndarray) -> bool:
    """Detecta o grande aviso vermelho do bloqueio do minigame."""
    if bgr is None or bgr.size == 0:
        return False

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0]
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    red = (
        (sat >= 80)
        & (val >= 75)
        & ((hue <= 14) | (hue >= 150))
    ).astype(np.uint8) * 255
    red = cv2.morphologyEx(red, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))

    count, labels, stats, _ = cv2.connectedComponentsWithStats(red)
    for i in range(1, count):
        x, y, cw, ch, area = stats[i]
        if area >= 7000 and cw >= 220 and ch >= 55:
            return True
    return False


def run_live(args):
    if os.name != "nt":
        raise SystemExit("O modo ao vivo foi feito para Windows.")

    try:
        import mss
    except ImportError:
        raise SystemExit("Falta o pacote mss. Rode: pip install mss")

    try:
        import pydirectinput
    except ImportError:
        raise SystemExit("Falta o pacote pydirectinput. Rode: pip install pydirectinput")

    pydirectinput.PAUSE = 0
    pydirectinput.FAILSAFE = False

    VK_F8 = 0x77
    VK_F10 = 0x79
    f8_prev = False
    f10_prev = False
    paused = False
    state = reset_round_state()
    retry_needed = False
    e_prompt_streak = 0
    waiting_after_e = False
    last_e_press = None
    cooldown_until = None
    last_cooldown_report = None
    failure_count = 0
    failure_registered = False
    round_end_time = None
    e_prompt_cleared_after_press = True

    with mss.MSS() as sct:
        if args.monitor <= 0 or args.monitor >= len(sct.monitors):
            print("Monitores encontrados:")
            for i, monitor in enumerate(sct.monitors[1:], start=1):
                print(f"  {i}: {monitor['width']}x{monitor['height']} @ ({monitor['left']}, {monitor['top']})")
            raise SystemExit(f"Monitor {args.monitor} invalido.")

        monitor = sct.monitors[args.monitor]
        screen_w = int(monitor["width"])
        screen_h = int(monitor["height"])
        scale = screen_h / REFERENCE_HEIGHT

        center_x = int(round(screen_w * CENTER_X_RATIO)) + args.x_offset
        center_y = int(round(screen_h * CENTER_Y_RATIO)) + args.y_offset
        pad = int(round((ROI_PAD + 18) * scale))

        grab_box = {
            "left": int(monitor["left"] + center_x - pad),
            "top": int(monitor["top"] + center_y - pad),
            "width": int(2 * pad + 1),
            "height": int(2 * pad + 1),
        }
        local_cx = pad
        local_cy = pad

        print("Farm bot v9")
        print(f"Tela: {screen_w}x{screen_h} | monitor {args.monitor}")
        print(f"Centro base: x={center_x}, y={center_y} | escala={scale:.3f}")
        print("Timing v9: alvo estabilizado + contato real na entrada da zona")
        print(f"Ponto de disparo: entrada real da zona (+{args.entry_tolerance:.1f}deg tol), {args.hit_streak} confirmacoes")
        print(f"Consenso do numero: {args.digit_lock_votes} votos minimos")
        print(f"Alvo: >= {args.min_target_width:.0f}deg, {args.target_lock_votes} observacoes consistentes")
        print(f"Retry: E automatico apos falha | bloqueio local: {args.cooldown_seconds:.0f}s")
        print("F8 pausa/retoma | F10 encerra")
        if args.dry_run:
            print("DRY-RUN: nenhuma tecla sera enviada.")

        interval = 1.0 / max(20.0, args.poll_hz)

        while True:
            loop_start = time.perf_counter()
            f8_edge, f8_prev = key_edge(VK_F8, f8_prev)
            f10_edge, f10_prev = key_edge(VK_F10, f10_prev)

            if f10_edge:
                print("Encerrando.")
                break
            if f8_edge:
                paused = not paused
                print("PAUSADO" if paused else "RETOMADO")
                time.sleep(0.08)

            shot = np.asarray(sct.grab(grab_box), dtype=np.uint8)
            roi = shot[:, :, :3].copy()
            now = time.perf_counter()

            if paused:
                info = {"center": state.get("center") or (local_cx, local_cy), "digit_info": None}
            else:
                info = update_round_state(roi, local_cx, local_cy, scale, state, args, now)

                if state["locked_digit"] is not None and not state["announced"]:
                    digit, conf, margin, votes, total = state["locked_digit"]
                    target = state.get("target")
                    target_text = "--" if target is None else f"{target['center']:.0f}deg/{target['width']:.0f}deg"
                    print(
                        f"Minigame: digito {digit} travado "
                        f"(conf={conf:.2f}, votos={votes}/{total}, alvo={target_text})"
                    )
                    state["announced"] = True
                    if args.save_captures:
                        os.makedirs("debug_captures", exist_ok=True)
                        stamp = int(time.time() * 1000)
                        cv2.imwrite(
                            os.path.join("debug_captures", f"round_{stamp}_digit_{digit}.png"),
                            roi,
                        )

                can_press = (
                    not state["pressed"]
                    and state["locked_digit"] is not None
                    and state.get("target") is not None
                    and state.get("direction") is not None
                    and state.get("predicted_progress") is not None
                    and state.get("desired_progress") is not None
                    and state.get("hit_streak", 0) >= args.hit_streak
                )

                if can_press:
                    digit = state["locked_digit"][0]
                    speed = state.get("speed")
                    speed_text = "--" if speed is None else f"{speed:.1f}"
                    if args.dry_run:
                        print(
                            f"[DRY-RUN] Apertaria {digit} agora "
                            f"(medido={state['predicted_progress']:.1f}/{state['desired_progress']:.1f}, "
                            f"vel={speed_text}deg/s, modo={state.get('contact_mode') or '--'})"
                        )
                    else:
                        pydirectinput.keyDown(str(digit))
                        time.sleep(args.key_hold)
                        pydirectinput.keyUp(str(digit))
                        print(
                            f"Apertou {digit} "
                            f"(medido={state['predicted_progress']:.1f}/{state['desired_progress']:.1f}, "
                            f"vel={speed_text}deg/s, modo={state.get('contact_mode') or '--'})"
                        )
                    state["pressed"] = True

                active_now = bool(info.get("digit_valid"))
                if active_now:
                    state["inactive_since"] = None
                    # Se uma rodada apareceu depois do E, o retry foi aceito.
                    if waiting_after_e:
                        waiting_after_e = False
                        last_e_press = None
                        e_prompt_cleared_after_press = True
                    retry_needed = False
                    e_prompt_streak = 0
                    failure_registered = False
                    round_end_time = None
                else:
                    if state["inactive_since"] is None:
                        state["inactive_since"] = now
                    if now - state["inactive_since"] >= args.reset_after:
                        if state["announced"] or state["pressed"] or state["target"] is not None:
                            if not state.get("pressed"):
                                if state.get("target") is None:
                                    miss_reason = "alvo nao foi travado"
                                elif state.get("direction") is None:
                                    miss_reason = "direcao do arco nao foi travada"
                                elif not state.get("armed_for_hit"):
                                    miss_reason = "arco nao foi armado antes da zona"
                                else:
                                    cg = state.get("closest_gap")
                                    miss_reason = "janela de contato nao confirmada" if cg is None else f"janela nao confirmada (gap mais proximo={cg:.1f}deg)"
                                print(f"Rodada terminou SEM apertar: {miss_reason}.")
                            else:
                                print("Rodada terminou apos disparo; verificando resultado.")
                            retry_needed = not args.no_auto_retry
                            e_prompt_streak = 0
                            failure_registered = False
                            round_end_time = now
                            state = reset_round_state()

                # Depois de apertar E existe uma barra de coleta antes do
                # proximo minigame. A v8 liberava outro E em 2.5s e acabava
                # spamando a tecla dezenas de vezes. Na v9 nunca repetimos E
                # enquanto o mesmo prompt continua na tela. Uma nova tentativa
                # so e permitida apos o prompt ter sumido e o tempo de espera ter
                # terminado.
                prompt_now_for_rearm = detect_e_prompt(roi) if waiting_after_e else False
                if waiting_after_e and not prompt_now_for_rearm:
                    e_prompt_cleared_after_press = True
                if (
                    not args.no_auto_retry
                    and waiting_after_e
                    and last_e_press is not None
                    and e_prompt_cleared_after_press
                    and now - last_e_press > args.e_retry_wait
                ):
                    waiting_after_e = False
                    retry_needed = True
                    e_prompt_streak = 0

                if cooldown_until is not None:
                    remaining = cooldown_until - now
                    if remaining <= 0:
                        cooldown_until = None
                        retry_needed = True
                        e_prompt_streak = 0
                        last_cooldown_report = None
                        failure_count = 0
                        # O prompt E que ja esta na tela depois do cooldown serve
                        # apenas para reiniciar; ele nao representa uma nova falha.
                        failure_registered = True
                        round_end_time = None
                        e_prompt_cleared_after_press = True
                        print("Bloqueio encerrado; aguardando o prompt E para reiniciar o minigame.")
                    else:
                        report_bucket = int(math.ceil(remaining / 10.0) * 10)
                        if report_bucket != last_cooldown_report:
                            last_cooldown_report = report_bucket
                            print(f"Bloqueio: ~{int(math.ceil(remaining))}s restantes.")

                # Pressiona E somente quando: uma rodada acabou, nao ha bloqueio,
                # nao estamos esperando resposta de um E anterior e o prompt foi
                # visto em varios frames consecutivos.
                can_retry_e = (
                    not args.no_auto_retry
                    and retry_needed
                    and cooldown_until is None
                    and not waiting_after_e
                    and state.get("center") is None
                )
                if can_retry_e:
                    if detect_e_prompt(roi):
                        e_prompt_streak += 1
                    else:
                        e_prompt_streak = 0

                    if e_prompt_streak >= args.e_prompt_frames:
                        # O prompt E reaparecendo logo depois de uma rodada e o
                        # sinal visual de falha. Contamos falhas consecutivas
                        # localmente para nao enviar o segundo E durante o
                        # bloqueio de 70 s do servidor.
                        if not failure_registered:
                            failure_count += 1
                            failure_registered = True
                            print(f"Falha detectada: {failure_count}/2 consecutivas.")

                        if failure_count >= 2:
                            cooldown_until = now + args.cooldown_seconds
                            retry_needed = True
                            waiting_after_e = False
                            e_prompt_streak = 0
                            last_cooldown_report = None
                            round_end_time = None
                            print(
                                f"Duas falhas seguidas: bloqueio local de "
                                f"{args.cooldown_seconds:.0f}s iniciado."
                            )
                        else:
                            if args.dry_run:
                                print("[DRY-RUN] Apertaria E para retomar o farm.")
                            else:
                                pydirectinput.keyDown("e")
                                time.sleep(args.key_hold)
                                pydirectinput.keyUp("e")
                                print("Apertou E para retomar o farm.")
                            retry_needed = False
                            waiting_after_e = True
                            last_e_press = now
                            e_prompt_cleared_after_press = False
                            e_prompt_streak = 0

                # Se a rodada sumiu mas o prompt E nao reapareceu, tratamos
                # como sucesso e zeramos a sequencia de falhas. Isso evita que
                # uma falha antiga seja carregada para sempre.
                if (
                    not args.no_auto_retry
                    and retry_needed
                    and not failure_registered
                    and round_end_time is not None
                    and cooldown_until is None
                    and now - round_end_time >= args.failure_prompt_timeout
                    and e_prompt_streak == 0
                ):
                    retry_needed = False
                    failure_count = 0
                    round_end_time = None
                    print("Sem prompt E apos a rodada; considerada concluida com sucesso.")

            if args.show:
                debug = draw_debug_v6(roi, state, info, paused)
                cv2.imshow("farm_bot v9 debug", debug)
                if cv2.waitKey(1) & 0xFF == 27:
                    break

            elapsed = time.perf_counter() - loop_start
            if elapsed < interval:
                time.sleep(interval - elapsed)

    if args.show:
        cv2.destroyAllWindows()


def run_video(args):
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise SystemExit(f"Nao consegui abrir: {args.video}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    screen_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    screen_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    scale = screen_h / REFERENCE_HEIGHT

    center_x = int(round(screen_w * CENTER_X_RATIO)) + args.x_offset
    center_y = int(round(screen_h * CENTER_Y_RATIO)) + args.y_offset
    pad = int(round((ROI_PAD + 18) * scale))

    state = reset_round_state()
    frame_index = 0
    hits = []

    print(f"Testando video v9 {screen_w}x{screen_h} @ {fps:.1f} fps")

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        y0 = max(0, center_y - pad)
        y1 = min(screen_h, center_y + pad + 1)
        x0 = max(0, center_x - pad)
        x1 = min(screen_w, center_x + pad + 1)
        roi = frame[y0:y1, x0:x1]
        local_cx = center_x - x0
        local_cy = center_y - y0
        now = frame_index / fps

        info = update_round_state(roi, local_cx, local_cy, scale, state, args, now)

        if state["locked_digit"] is not None and not state["announced"]:
            digit, conf, margin, votes, total = state["locked_digit"]
            target = state.get("target")
            target_text = "--" if target is None else f"{target['center']:.0f}deg"
            print(
                f"{now:7.3f}s rodada: digito {digit} "
                f"(conf={conf:.2f}, votos={votes}/{total}, alvo={target_text})"
            )
            state["announced"] = True

        can_press = (
            not state["pressed"]
            and state["locked_digit"] is not None
            and state.get("target") is not None
            and state.get("direction") is not None
            and state.get("predicted_progress") is not None
            and state.get("desired_progress") is not None
            and state.get("hit_streak", 0) >= args.hit_streak
        )

        if can_press:
            digit = state["locked_digit"][0]
            hits.append((now, digit, state["predicted_progress"], state["desired_progress"], state["speed"]))
            speed = state.get("speed")
            speed_text = "--" if speed is None else f"{speed:.1f}"
            print(
                f"{now:7.3f}s -> apertaria {digit} "
                f"(medido={state['predicted_progress']:.1f}/{state['desired_progress']:.1f}, "
                f"vel={speed_text}deg/s, modo={state.get('contact_mode') or '--'})"
            )
            state["pressed"] = True

        if info.get("digit_valid"):
            state["inactive_since"] = None
        else:
            if state["inactive_since"] is None:
                state["inactive_since"] = now
            if now - state["inactive_since"] >= args.reset_after:
                if state["announced"] or state["pressed"] or state["target"] is not None:
                    state = reset_round_state()

        if args.show:
            debug = draw_debug_v6(roi, state, info, False)
            cv2.imshow("farm_bot v8 video", debug)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break

        frame_index += 1

    cap.release()
    if args.show:
        cv2.destroyAllWindows()

    print(f"Total de acionamentos detectados: {len(hits)}")
    return hits

def build_parser():
    parser = argparse.ArgumentParser(description="Automacao visual v9 do minigame de coleta.")

    parser.add_argument(
        "--video",
        help="Testa em um video gravado e NAO envia teclas.",
    )
    parser.add_argument(
        "--monitor",
        type=int,
        default=1,
        help="Monitor usado pelo jogo no modo ao vivo. Padrao: 1.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Detecta normalmente, mas nao envia tecla.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Abre uma janela pequena mostrando a deteccao.",
    )
    parser.add_argument(
        "--poll-hz",
        type=float,
        default=120.0,
        help="Frequencia de captura no modo ao vivo. Padrao: 120.",
    )
    parser.add_argument(
        "--hit-distance",
        type=float,
        default=DEFAULT_HIT_DISTANCE,
        help=f"Distancia para apertar, na escala 1078p. Padrao: {DEFAULT_HIT_DISTANCE}.",
    )
    parser.add_argument(
        "--arm-distance",
        type=float,
        default=DEFAULT_ARM_DISTANCE,
        help=f"Distancia minima que deve ser observada antes de armar. Padrao: {DEFAULT_ARM_DISTANCE}.",
    )
    parser.add_argument(
        "--hit-streak",
        type=int,
        default=DEFAULT_HIT_STREAK,
        help=f"Leituras consecutivas dentro do alvo antes de apertar. Padrao: {DEFAULT_HIT_STREAK}.",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.80,
        help="Confianca minima do reconhecimento do digito. Padrao: 0.80.",
    )
    parser.add_argument(
        "--min-margin",
        type=float,
        default=0.060,
        help="Diferenca minima entre o melhor e o segundo digito. Padrao: 0.060.",
    )
    parser.add_argument(
        "--save-captures",
        action="store_true",
        help="Salva o recorte de cada rodada em debug_captures para diagnosticar numero errado.",
    )
    parser.add_argument(
        "--min-target-width",
        type=float,
        default=12.0,
        help="Largura angular minima da zona-alvo final. Padrao: 12 graus.",
    )
    parser.add_argument(
        "--target-lock-votes",
        type=int,
        default=6,
        help="Quantidade minima de observacoes para formar o voto angular da zona. Padrao: 6.",
    )
    parser.add_argument(
        "--target-freeze-gap",
        type=float,
        default=32.0,
        help="Congela a geometria do alvo quando a ponta fica a esta distancia da entrada. Padrao: 32 graus.",
    )
    parser.add_argument(
        "--entry-tolerance",
        type=float,
        default=1.5,
        help="Tolerancia antes da entrada visual da zona para considerar contato. Padrao: 1.5 grau.",
    )
    parser.add_argument(
        "--merge-precontact",
        type=float,
        default=12.0,
        help="Distancia maxima antes da entrada para aceitar o salto visual de contato. Padrao: 12 graus.",
    )
    parser.add_argument(
        "--target-fraction",
        type=float,
        default=DEFAULT_TARGET_FRACTION,
        help=f"Quanto entrar na zona antes de apertar (0-1). Padrao: {DEFAULT_TARGET_FRACTION}.",
    )
    parser.add_argument(
        "--max-hit-overshoot",
        type=float,
        default=DEFAULT_MAX_HIT_OVERSHOOT,
        help=f"Quanto a ponta pode passar do ponto de disparo sem ser rejeitada. Padrao: {DEFAULT_MAX_HIT_OVERSHOOT} graus.",
    )
    parser.add_argument(
        "--progress-threshold",
        type=float,
        default=DEFAULT_PROGRESS_THRESHOLD,
        help=f"Limiar visual do arco de progresso. Padrao: {DEFAULT_PROGRESS_THRESHOLD}.",
    )
    parser.add_argument(
        "--target-threshold",
        type=float,
        default=DEFAULT_TARGET_THRESHOLD,
        help=f"Limiar visual da zona-alvo. Padrao: {DEFAULT_TARGET_THRESHOLD}.",
    )
    parser.add_argument(
        "--max-progress-speed",
        type=float,
        default=DEFAULT_MAX_PROGRESS_SPEED,
        help=f"Velocidade angular maxima aceita. Padrao: {DEFAULT_MAX_PROGRESS_SPEED} deg/s.",
    )
    parser.add_argument(
        "--digit-lock-votes",
        type=int,
        default=11,
        help="Quantidade minima de leituras concordantes para travar o numero. Padrao: 11.",
    )
    parser.add_argument(
        "--reset-after",
        type=float,
        default=0.35,
        help="Tempo sem minigame para liberar a proxima rodada. Padrao: 0.35s.",
    )
    parser.add_argument(
        "--key-hold",
        type=float,
        default=0.025,
        help="Tempo que a tecla fica pressionada. Padrao: 0.025s.",
    )
    parser.add_argument(
        "--no-auto-retry",
        action="store_true",
        help="Desativa o E automatico depois que uma rodada termina/falha.",
    )
    parser.add_argument(
        "--cooldown-seconds",
        type=float,
        default=DEFAULT_COOLDOWN_SECONDS,
        help=f"Espera local apos detectar o aviso vermelho de bloqueio. Padrao: {DEFAULT_COOLDOWN_SECONDS:.0f}s.",
    )
    parser.add_argument(
        "--e-retry-wait",
        type=float,
        default=DEFAULT_E_RETRY_WAIT,
        help=f"Tempo para esperar a resposta depois de apertar E. Padrao: {DEFAULT_E_RETRY_WAIT:.1f}s.",
    )
    parser.add_argument(
        "--e-prompt-frames",
        type=int,
        default=4,
        help="Frames consecutivos do prompt E antes de apertar. Padrao: 4.",
    )
    parser.add_argument(
        "--failure-prompt-timeout",
        type=float,
        default=1.5,
        help="Sem prompt E apos esse tempo, a rodada e considerada sucesso. Padrao: 1.5s.",
    )
    parser.add_argument(
        "--x-offset",
        type=int,
        default=0,
        help="Ajuste fino horizontal do centro, em pixels.",
    )
    parser.add_argument(
        "--y-offset",
        type=int,
        default=0,
        help="Ajuste fino vertical do centro, em pixels.",
    )

    return parser


def main():
    args = build_parser().parse_args()

    if args.video:
        run_video(args)
    else:
        run_live(args)


if __name__ == "__main__":
    main()
