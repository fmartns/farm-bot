FARM BOT v10

Mudancas v10 (analisado em ~40 rodadas gravadas do jogo, 1920x1080):
- loop ~4 ms/quadro (antes ~90 ms): classificacao de digito vetorizada;
- centro E escala do anel ajustados pelas duas bordas do trilho, ancorados no
  digito; o anel muda de tamanho entre rodadas (escala ~0.94-1.12) e o raio fixo
  da v9 causava "alvo nao foi travado";
- arco branco (cinza exato 204) x zona colorida separados por pixel, incluindo
  zonas palidas em degrade;
- mira no centro da zona LOGICA (--target-fraction 0.5), descontando as pontas
  arredondadas de ~6 graus (--cap-degrees); disparo agendado entre quadros com
  compensacao de latencia (--input-latency);
- filtro de progresso que nao congela mais apos um salto;
- direcao do arco so pelo movimento observado;
- templates de digito na fonte do HUD (Poppins);
- diagnostico: --record-rounds PASTA salva quadros + estado de cada rodada;
- original preservado em farm_bot_v9_original.py.

Mudancas v9:
- o centro do circulo nao fica mais congelado no primeiro frame; ele e refinado continuamente por mediana curta;
- a zona-alvo agora e estimada por voto angular entre varios frames, em vez de confiar em um unico arco detectado;
- isso corrige o erro em que o alvo era travado alguns graus deslocado e a tecla era apertada antes da zona real;
- o disparo principal acontece na entrada real da zona, com duas confirmacoes;
- quando a ponta branca se funde com a zona colorida, um salto visual so vale se a ultima ponta estava muito perto da entrada;
- reconhecimento do numero continua usando 11 leituras concordantes;
- o E automatico nao e mais repetido a cada poucos segundos: depois de um retry ele aguarda ate 20 s e exige que o prompt tenha desaparecido antes de permitir outro E;
- apos duas falhas consecutivas, o bloqueio local de 70 s continua ativo.

Validacao nos videos enviados:
- video original: 6, 9 e 8 detectados e com disparo;
- video de 16:00: 9 e 7 detectados e com disparo;
- video de 18:20 (ultimo): a rodada do 3, que terminou antes de o arco realmente entrar na zona, NAO gera disparo na v9; a rodada seguinte do 6 gera disparo no contato (~25.67 s no video).

Instalacao:
  py -3.14 -m pip install -r requirements_farm_bot.txt

Teste sem enviar teclas:
  py -3.14 farm_bot.py --monitor 3 --dry-run --show

Rodar de verdade:
  py -3.14 farm_bot.py --monitor 3 --show

Sem janela de debug:
  py -3.14 farm_bot.py --monitor 3

Teclas:
  F8  pausa/retoma
  F10 encerra

Diagnostico:
  py -3.14 farm_bot.py --monitor 3 --dry-run --show --save-captures

Opcoes uteis:
  --entry-tolerance 1.5       tolerancia visual na entrada da zona
  --target-lock-votes 6       observacoes minimas para estabilizar a zona
  --target-freeze-gap 32      distancia em graus para congelar a geometria do alvo
  --merge-precontact 12       proximidade maxima para aceitar o salto de contato
  --e-retry-wait 20           espera minima antes de permitir novo E
  --cooldown-seconds 70       bloqueio apos duas falhas consecutivas
  --no-auto-retry             desativa o E automatico
