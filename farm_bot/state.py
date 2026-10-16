"""Maquina de estados de uma rodada: ancora o anel, trava digito/alvo/direcao
e acompanha o progresso do arco branco até a janela de disparo."""

import collections
import math

import numpy as np

from .config import START_ANGLE_DEG
from .digit_detection import digit_anchor, extract_digit, stable_digit_lock
from .geometry import directional_distance, progress_extent
from .ring import angular_profiles, fit_ring, locate_ring_center
from .target import detect_target_arc, estimate_speed, stable_target


def reset_round_state() -> dict:
    return {
        "center_samples": collections.deque(maxlen=15),
        "ring_fits": collections.deque(maxlen=9),
        "ring_scale": 1.0,
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


def update_round_state(
    roi: np.ndarray,
    expected_cx: float,
    expected_cy: float,
    scale: float,
    state: dict,
    args: object,
    now: float,
) -> dict:
    last_frame = state.get("last_frame_time")
    if last_frame is not None and 0.0 < now - last_frame < 0.5:
        previous_dt = state.get("frame_dt")
        state["frame_dt"] = (now - last_frame) if previous_dt is None else 0.8 * previous_dt + 0.2 * (now - last_frame)
    state["last_frame_time"] = now

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
                        # v10: ancora no digito e ajusta centro + escala do anel.
                        ax, ay = digit_anchor(probe_digit, scale)
                        fx, fy, fs, fscore = fit_ring(roi, ax, ay, scale)
                        state["ring_fits"].append((fx, fy, fs))
                        state["center"] = (fx, fy)
                        state["ring_scale"] = fs
            else:
                state["activation_streak"] = 0
                state["center_samples"].clear()
        else:
            state["activation_streak"] = 0
            state["center_samples"].clear()
    else:
        # v10: refinamento esparso (1 a cada 6 quadros) com busca local de
        # centro + escala. O Hough por quadro da v9 oscilava ate ~12 px.
        state["refine_counter"] = state.get("refine_counter", 0) + 1
        if state["refine_counter"] % 6 == 0 and len(state["ring_fits"]) < state["ring_fits"].maxlen:
            curx, cury = state["center"]
            fx, fy, fs, fscore = fit_ring(
                roi, curx, cury, scale, state["ring_scale"], span=2.0, scale_span=0.02
            )
            if math.hypot(fx - curx, fy - cury) <= 3.0 * scale:
                state["ring_fits"].append((fx, fy, fs))
                state["center"] = (
                    float(np.median([item[0] for item in state["ring_fits"]])),
                    float(np.median([item[1] for item in state["ring_fits"]])),
                )
                state["ring_scale"] = float(np.median([item[2] for item in state["ring_fits"]]))

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
        target_profile, progress_profile = angular_profiles(roi, cx, cy, scale * state["ring_scale"])

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
        # v10: sem fallback "caminho mais curto ate o alvo". Nas gravacoes do
        # jogo o arco vai tanto pelo caminho curto quanto pelo longo (ex.: 248
        # graus anti-horario), e o fallback travava a direcao errada. A direcao
        # vem so do crescimento observado e e corrigida se o outro lado crescer.
        if state["target"] is not None and progress_profile is not None:
            plus = progress_extent(progress_profile, +1, args.progress_threshold, 200.0)
            minus = progress_extent(progress_profile, -1, args.progress_threshold, 200.0)
            if state["direction"] is None:
                if max(plus, minus) >= 12.0 and abs(plus - minus) >= 6.0:
                    state["direction"] = +1 if plus > minus else -1
            elif not state.get("pressed", False):
                chosen, other = (plus, minus) if state["direction"] > 0 else (minus, plus)
                if other >= 20.0 and other >= chosen + 10.0:
                    state["direction"] = -state["direction"]
                    state["last_progress"] = None
                    state["last_progress_time"] = None
                    state["progress_samples"].clear()
                    state["speed"] = None
                    state["armed_for_hit"] = False
                    state["hit_streak"] = 0

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

            # v10: o limite de salto usa o dt real (a v9 limitava dt a 50 ms:
            # com quadros mais lentos, um passo normal era rejeitado e o
            # progresso ficava congelado ate o fim da rodada). Se varias
            # leituras seguidas rejeitadas concordam entre si, ressincroniza.
            accept = True
            if state["last_progress"] is not None and state["last_progress_time"] is not None:
                dt = max(1e-4, now - state["last_progress_time"])
                delta = raw_progress - state["last_progress"]
                max_step = args.max_progress_speed * min(dt, 0.30) + 4.0
                if delta < -4.0 or delta > max_step:
                    accept = False
                    pending = state.get("pending_progress")
                    if (
                        pending is not None
                        and 0.0 <= raw_progress - pending[1] <= args.max_progress_speed * min(now - pending[0], 0.30) + 4.0
                    ):
                        state["pending_count"] = state.get("pending_count", 0) + 1
                    else:
                        state["pending_count"] = 1
                    state["pending_progress"] = (now, raw_progress)
                    if state["pending_count"] >= 3:
                        state["last_progress"] = raw_progress
                        state["progress_samples"].clear()
                        accept = True
            if accept:
                state["pending_progress"] = None
                state["pending_count"] = 0

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

            # Mira na zona logica: [entrada + 2*cap, saida] em coordenadas da
            # ponta visual (ver DEFAULT_CAP_DEGREES).
            logical_width = max(2.0, target_width - 2.0 * args.cap_degrees)
            desired = target_entry + 2.0 * args.cap_degrees + args.target_fraction * logical_width
            desired = min(desired, target_entry + target_width - args.exit_margin - 1.0)

            if measured_progress is not None and measured_progress <= target_entry - 10.0:
                state["armed_for_hit"] = True

            gap = None if measured_progress is None else target_entry - measured_progress
            if gap is not None:
                if state.get("closest_gap") is None or abs(gap) < abs(state["closest_gap"]):
                    state["closest_gap"] = gap

            # v10: com a classificacao por pixel, a zona colorida vira branca
            # progressivamente quando a ponta passa por ela, entao a ponta
            # continua mensuravel DENTRO da zona. Disparamos no ponto
            # target_fraction da zona logica (padrao: centro), compensando a latencia de
            # entrada com a velocidade medida. O "salto de contato" da v9 foi
            # removido: era a zona sendo lida como arco branco, e causava
            # disparos antes da ponta chegar.
            target_exit = target_entry + target_width
            lead = 0.0
            if state.get("speed") is not None:
                lead = float(state["speed"]) * args.input_latency
            merge_contact = False
            # Disparo agendado: se o ponto de mira sera alcancado antes do
            # proximo quadro, espera o tempo exato em vez de apertar um quadro
            # (~8-10 graus) atrasado.
            frame_dt = state.get("frame_dt") or 0.012
            fire_delay = 0.0
            scheduled = False
            if (
                state.get("speed") is not None
                and measured_progress is not None
                and measured_progress + lead < desired
            ):
                time_to_desired = (desired - measured_progress) / float(state["speed"]) - args.input_latency
                if 0.0 < time_to_desired <= frame_dt * 1.2:
                    fire_delay = time_to_desired
                    scheduled = True
            state["fire_delay"] = fire_delay
            in_window = (
                state.get("armed_for_hit", False)
                and measured_progress is not None
                and (measured_progress + lead >= desired or scheduled)
                and measured_progress <= target_exit - args.exit_margin
            )

            if in_window:
                state["contact_mode"] = "aim"
                state["hit_window_started"] = True
                state["hit_streak"] += 1
            else:
                state["hit_streak"] = 0
                state["hit_window_started"] = False
                state["contact_mode"] = None

            overshoot = None if measured_progress is None else measured_progress - target_entry
            state["target_center_dist"] = target_center_dist
            state["target_entry"] = target_entry
            state["target_exit"] = target_exit
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

