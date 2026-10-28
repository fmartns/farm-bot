"""Loop principal (modo ao vivo contra a tela) e modo de replay de video."""

import math
import os
import time

import cv2
import numpy as np

from .config import CENTER_X_RATIO, CENTER_Y_RATIO, REFERENCE_HEIGHT, ROI_PAD
from .debug_view import draw_debug_v6
from .input_control import game_has_focus, key_edge
from .overlay import COLOR_ON, COLOR_PAUSED, create_overlay
from .prompts import detect_e_prompt
from .recorder import RoundRecorder
from .state import reset_round_state, update_round_state


def run_live(args) -> None:
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

    VK_F12 = 0x7B
    VK_F10 = 0x79
    f12_prev = False
    f10_prev = False
    paused = False
    overlay = create_overlay() if not getattr(args, "no_overlay", False) else None
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
    last_focus_warning = None
    e_sends_without_round = 0
    last_afk_move = time.perf_counter()
    last_idle_signal = time.perf_counter()
    recorder = RoundRecorder(args.record_rounds) if args.record_rounds else None

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

        print("Farm bot v10")
        print(f"Tela: {screen_w}x{screen_h} | monitor {args.monitor}")
        print(f"Centro base: x={center_x}, y={center_y} | escala={scale:.3f}")
        print(f"Timing v10: dispara a {args.target_fraction*100:.0f}% da zona logica (pontas {args.cap_degrees:.0f}deg, latencia comp. {args.input_latency*1000:.0f} ms)")
        print(f"Confirmacoes antes de apertar: {args.hit_streak} | margem do fim da zona: {args.exit_margin:.0f}deg")
        print(f"Consenso do numero: {args.digit_lock_votes} votos minimos")
        print(f"Alvo: >= {args.min_target_width:.0f}deg, {args.target_lock_votes} observacoes consistentes")
        print(f"Retry: E automatico apos falha | bloqueio local: {args.cooldown_seconds:.0f}s")
        print("F12 pausa/retoma | F10 encerra")
        if args.dry_run:
            print("DRY-RUN: nenhuma tecla sera enviada.")
        elif not game_has_focus():
            print("AVISO: o jogo nao esta em foco. Clique na janela do jogo; as teclas so sao enviadas para ele.")

        interval = 1.0 / max(20.0, args.poll_hz)

        while True:
            loop_start = time.perf_counter()
            f12_edge, f12_prev = key_edge(VK_F12, f12_prev)
            f10_edge, f10_prev = key_edge(VK_F10, f10_prev)

            if f10_edge:
                print("Encerrando.")
                break
            if f12_edge:
                paused = not paused
                print("PAUSADO" if paused else "RETOMADO")
                if overlay is not None:
                    if paused:
                        overlay.set_status("BOT DESLIGADO", COLOR_PAUSED)
                    else:
                        overlay.set_status("BOT LIGADO", COLOR_ON)
                time.sleep(0.08)

            now = time.perf_counter()
            if (
                args.anti_afk_seconds > 0.0
                and not args.dry_run
                and now - last_afk_move >= args.anti_afk_seconds
                and game_has_focus()
            ):
                pydirectinput.moveRel(1, 0, relative=True)
                pydirectinput.moveRel(-1, 0, relative=True)
                last_afk_move = now

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
                        state["pressed"] = True
                    elif not game_has_focus():
                        print(f"AVISO: jogo sem foco; {digit} NAO enviado. Clique na janela do jogo.")
                    else:
                        if state.get("fire_delay", 0.0) > 0.0:
                            time.sleep(state["fire_delay"])
                        pydirectinput.keyDown(str(digit))
                        time.sleep(args.key_hold)
                        pydirectinput.keyUp(str(digit))
                        print(
                            f"Apertou {digit} "
                            f"(medido={state['predicted_progress']:.1f}/{state['desired_progress']:.1f}, "
                            f"vel={speed_text}deg/s, modo={state.get('contact_mode') or '--'})"
                        )
                        state["pressed"] = True

                if recorder is not None:
                    recorder.frame(now, roi, state, info, "press" if can_press else None)

                active_now = bool(info.get("digit_valid"))
                if state.get("center") is not None:
                    last_idle_signal = now
                if active_now:
                    state["inactive_since"] = None
                    # Se uma rodada apareceu depois do E, o retry foi aceito.
                    if waiting_after_e:
                        waiting_after_e = False
                        last_e_press = None
                        e_prompt_cleared_after_press = True
                    retry_needed = False
                    e_prompt_streak = 0
                    e_sends_without_round = 0
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
                                    extents = state.get("progress_extents")
                                    if extents is None:
                                        miss_reason = "direcao do arco nao foi travada"
                                    else:
                                        miss_reason = (
                                            "direcao do arco nao foi travada "
                                            f"(+{extents[0]:.0f}/-{extents[1]:.0f}deg)"
                                        )
                                elif not state.get("armed_for_hit"):
                                    miss_reason = "arco nao foi armado antes da zona"
                                else:
                                    cg = state.get("closest_gap")
                                    miss_reason = "janela de contato nao confirmada" if cg is None else f"janela nao confirmada (gap mais proximo={cg:.1f}deg)"
                                print(f"Rodada terminou SEM apertar: {miss_reason}.")
                            else:
                                miss_reason = None
                                print("Rodada terminou apos disparo; verificando resultado.")
                            if recorder is not None:
                                recorder.end_round(f"sem apertar: {miss_reason}" if miss_reason else "apertou")
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
                # v10: se o prompt E continua na tela depois da espera, o E nao
                # foi aceito (ex.: jogo sem foco). A v9 esperava o prompt sumir
                # para sempre e o bot ficava parado.
                e_not_accepted = (
                    waiting_after_e
                    and not e_prompt_cleared_after_press
                    and prompt_now_for_rearm
                )
                if (
                    not args.no_auto_retry
                    and waiting_after_e
                    and last_e_press is not None
                    and (e_prompt_cleared_after_press or e_not_accepted)
                    and now - last_e_press > args.e_retry_wait
                ):
                    if e_not_accepted:
                        print("Prompt E ainda na tela; o E anterior nao foi aceito. Tentando de novo.")
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

                        # v10: se o E ja foi enviado varias vezes sem que
                        # nenhuma rodada nova aparecesse (o prompt so pisca e
                        # volta), spamar E para sempre nao ajuda e pode so
                        # alimentar um bloqueio do proprio jogo. Tratamos como
                        # uma falha e entramos no bloqueio local.
                        e_spam_stuck = e_sends_without_round >= 3

                        if failure_count >= 2 or e_spam_stuck:
                            cooldown_until = now + args.cooldown_seconds
                            retry_needed = True
                            waiting_after_e = False
                            e_prompt_streak = 0
                            last_cooldown_report = None
                            round_end_time = None
                            e_sends_without_round = 0
                            if e_spam_stuck and failure_count < 2:
                                print(
                                    f"E enviado repetidas vezes sem reiniciar o minigame: "
                                    f"bloqueio local de {args.cooldown_seconds:.0f}s iniciado."
                                )
                            else:
                                print(
                                    f"Duas falhas seguidas: bloqueio local de "
                                    f"{args.cooldown_seconds:.0f}s iniciado."
                                )
                        elif not args.dry_run and not game_has_focus():
                            if last_focus_warning is None or now - last_focus_warning > 10.0:
                                last_focus_warning = now
                                print("AVISO: jogo sem foco; E NAO enviado. Clique na janela do jogo.")
                        else:
                            if args.dry_run:
                                print("[DRY-RUN] Apertaria E para retomar o farm.")
                            else:
                                pydirectinput.keyDown("e")
                                time.sleep(args.key_hold)
                                pydirectinput.keyUp("e")
                                print("Apertou E para retomar o farm.")
                            e_sends_without_round += 1
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

                # v10: watchdog de ultimo recurso. Se nenhum arco/rodada
                # aparecer por muito tempo (ex.: o jogo travou numa tela que
                # nenhuma outra logica reconhece), isso garante que o bot
                # nunca fique parado para sempre: aperta E e reconta o prazo.
                if (
                    args.idle_recover_seconds > 0.0
                    and state.get("center") is None
                    and cooldown_until is None
                    and now - last_idle_signal >= args.idle_recover_seconds
                ):
                    if args.dry_run:
                        print(
                            f"[DRY-RUN] {args.idle_recover_seconds:.0f}s sem rodada: "
                            f"apertaria E (watchdog)."
                        )
                        last_idle_signal = now
                    elif not game_has_focus():
                        if last_focus_warning is None or now - last_focus_warning > 10.0:
                            last_focus_warning = now
                            print("AVISO: jogo sem foco; E do watchdog NAO enviado. Clique na janela do jogo.")
                    else:
                        pydirectinput.keyDown("e")
                        time.sleep(args.key_hold)
                        pydirectinput.keyUp("e")
                        print(
                            f"{args.idle_recover_seconds:.0f}s sem nenhuma rodada: "
                            f"apertou E (watchdog) para garantir que o farm continue."
                        )
                        last_idle_signal = now
                        waiting_after_e = True
                        last_e_press = now
                        e_prompt_cleared_after_press = False
                        e_prompt_streak = 0
                        retry_needed = False

            if args.show:
                debug = draw_debug_v6(roi, state, info, paused)
                cv2.imshow("farm_bot v9 debug", debug)
                if cv2.waitKey(1) & 0xFF == 27:
                    break

            elapsed = time.perf_counter() - loop_start
            if elapsed < interval:
                time.sleep(interval - elapsed)

    if recorder is not None:
        recorder.close()
    if args.show:
        cv2.destroyAllWindows()
    if overlay is not None:
        overlay.close()


def run_video(args) -> list:
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
