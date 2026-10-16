"""Janela simples para escolher as opcoes mais usadas e iniciar o bot.

Usada como ponto de entrada padrao quando o programa e aberto sem argumentos
(ex.: dando duplo-clique no .exe). Quem preferir a linha de comando continua
usando `python -m farm_bot.cli --monitor 1 --show` normalmente.

A janela mostra, por padrao, so o essencial (monitor + iniciar/parar) ja
pronto para rodar de verdade. O botao "Avancado" revela as opcoes menos
usadas (modo video, janela de depuracao, gravacao de diagnostico, etc.).
"""

import queue
import sys
import threading
import tkinter as tk
import traceback
from tkinter import BooleanVar, StringVar, Tk, filedialog, messagebox, ttk
from typing import Optional

from .cli import build_parser
from .runner import run_live, run_video


def build_args_from_selection(selection: dict):
    """Converte as opcoes escolhidas na tela no mesmo objeto `args` que a CLI usa.

    Mantido como funcao pura (sem Tkinter) para poder ser testado sem uma
    tela/display disponivel.
    """
    argv = []

    if selection.get("mode") == "video":
        video = (selection.get("video") or "").strip()
        if not video:
            raise ValueError("Selecione um arquivo de video para testar.")
        argv += ["--video", video]
    else:
        monitor = selection.get("monitor", 1)
        try:
            monitor = int(monitor)
        except (TypeError, ValueError):
            raise ValueError("Monitor deve ser um numero inteiro.") from None
        argv += ["--monitor", str(monitor)]

    if selection.get("dry_run"):
        argv.append("--dry-run")
    if selection.get("show"):
        argv.append("--show")
    if selection.get("save_captures"):
        argv.append("--save-captures")
    if selection.get("no_auto_retry"):
        argv.append("--no-auto-retry")
    if not selection.get("overlay", True):
        argv.append("--no-overlay")

    record_rounds = (selection.get("record_rounds") or "").strip()
    if record_rounds:
        argv += ["--record-rounds", record_rounds]

    for flag, key in (("--x-offset", "x_offset"), ("--y-offset", "y_offset")):
        raw = selection.get(key, 0) or 0
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise ValueError("Os ajustes de posicao (x/y) devem ser numeros inteiros.") from None
        if value:
            argv += [flag, str(value)]

    return build_parser().parse_args(argv)


class _QueueWriter:
    """Substitui sys.stdout durante a execucao para levar os `print()` do bot
    para a caixa de log da janela, em vez do console."""

    def __init__(self, line_queue: queue.Queue):
        self._queue = line_queue

    def write(self, text: str) -> None:
        if text:
            self._queue.put(text)

    def flush(self) -> None:
        pass


class FarmBotApp:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("FARM BOT")
        self.root.minsize(460, 340)

        self._log_queue: queue.Queue = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._advanced_visible = False

        # Valores ja pre-configurados para rodar de verdade com um clique:
        # monitor 1, sem dry-run, sem janela de depuracao, com o aviso de
        # status na tela. Quem quiser ajustar mais usa o "Avancado".
        self.mode_var = StringVar(value="live")
        self.monitor_var = StringVar(value="1")
        self.video_var = StringVar(value="")
        self.dry_run_var = BooleanVar(value=False)
        self.show_var = BooleanVar(value=False)
        self.save_captures_var = BooleanVar(value=False)
        self.no_auto_retry_var = BooleanVar(value=False)
        self.overlay_var = BooleanVar(value=True)
        self.record_rounds_var = StringVar(value="")
        self.x_offset_var = StringVar(value="0")
        self.y_offset_var = StringVar(value="0")

        self._build_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._drain_log_queue)

    # -- construcao da interface -------------------------------------------------
    def _build_widgets(self) -> None:
        pad = {"padx": 8, "pady": 4}

        simple_frame = ttk.LabelFrame(self.root, text="Iniciar")
        simple_frame.pack(fill="x", **pad)

        monitor_row = ttk.Frame(simple_frame)
        monitor_row.pack(fill="x", pady=(2, 4))
        ttk.Label(monitor_row, text="Monitor (numero mostrado ao iniciar):").pack(side="left")
        ttk.Entry(monitor_row, textvariable=self.monitor_var, width=6).pack(side="left", padx=6)

        ttk.Checkbutton(
            simple_frame,
            text="Modo teste (detecta mas NAO aperta tecla)",
            variable=self.dry_run_var,
        ).pack(anchor="w")

        buttons_row = ttk.Frame(self.root)
        buttons_row.pack(fill="x", **pad)
        self.start_button = ttk.Button(buttons_row, text="Iniciar", command=self._start)
        self.start_button.pack(side="left")
        ttk.Button(buttons_row, text="Parar (envia F10)", command=self._simulate_stop_key).pack(
            side="left", padx=6
        )
        self.advanced_button = ttk.Button(buttons_row, text="Avancado ▸", command=self._toggle_advanced)
        self.advanced_button.pack(side="left", padx=6)

        ttk.Label(
            self.root,
            text="F12 pausa/retoma e F10 encerra tambem funcionam direto no teclado.",
        ).pack(anchor="w", padx=8)

        # -- secao avancada (criada, mas so aparece ao clicar em "Avancado") --
        self.advanced_frame = ttk.Frame(self.root)

        mode_frame = ttk.LabelFrame(self.advanced_frame, text="Modo")
        mode_frame.pack(fill="x", **pad)
        ttk.Radiobutton(
            mode_frame, text="Ao vivo (joga de verdade)", variable=self.mode_var, value="live",
            command=self._refresh_mode,
        ).pack(anchor="w")
        ttk.Radiobutton(
            mode_frame, text="Testar com um video gravado", variable=self.mode_var, value="video",
            command=self._refresh_mode,
        ).pack(anchor="w")

        self.video_frame = ttk.LabelFrame(self.advanced_frame, text="Arquivo de video")
        self.video_frame.pack(fill="x", **pad)
        video_row = ttk.Frame(self.video_frame)
        video_row.pack(fill="x")
        ttk.Entry(video_row, textvariable=self.video_var).pack(side="left", fill="x", expand=True)
        ttk.Button(video_row, text="Procurar...", command=self._pick_video).pack(side="left", padx=4)

        options_frame = ttk.LabelFrame(self.advanced_frame, text="Opcoes")
        options_frame.pack(fill="x", **pad)
        ttk.Checkbutton(
            options_frame, text="Mostrar janela de depuracao (--show)", variable=self.show_var,
        ).pack(anchor="w")
        ttk.Checkbutton(
            options_frame, text="Salvar capturas de diagnostico", variable=self.save_captures_var,
        ).pack(anchor="w")
        ttk.Checkbutton(
            options_frame, text="Desativar retry automatico do E", variable=self.no_auto_retry_var,
        ).pack(anchor="w")
        ttk.Checkbutton(
            options_frame,
            text="Mostrar aviso na tela (canto superior direito) se o bot esta ligado/pausado",
            variable=self.overlay_var,
        ).pack(anchor="w")

        record_row = ttk.Frame(options_frame)
        record_row.pack(fill="x", pady=(4, 0))
        ttk.Label(record_row, text="Gravar rodadas em:").pack(side="left")
        ttk.Entry(record_row, textvariable=self.record_rounds_var).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(record_row, text="Procurar...", command=self._pick_record_dir).pack(side="left")

        offset_row = ttk.Frame(options_frame)
        offset_row.pack(fill="x", pady=(4, 0))
        ttk.Label(offset_row, text="Ajuste X:").pack(side="left")
        ttk.Entry(offset_row, textvariable=self.x_offset_var, width=6).pack(side="left", padx=(2, 10))
        ttk.Label(offset_row, text="Ajuste Y:").pack(side="left")
        ttk.Entry(offset_row, textvariable=self.y_offset_var, width=6).pack(side="left", padx=2)

        log_frame = ttk.LabelFrame(self.root, text="Saida")
        log_frame.pack(fill="both", expand=True, **pad)

        self.log_text = tk.Text(log_frame, height=14, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True)

        self._refresh_mode()

    def _toggle_advanced(self) -> None:
        if self._advanced_visible:
            self.advanced_frame.pack_forget()
            self.advanced_button.configure(text="Avancado ▸")
        else:
            # Insere antes da caixa de saida, para o log continuar por ultimo.
            self.advanced_frame.pack(fill="x", before=self.log_text.master)
            self.advanced_button.configure(text="Avancado ▾ (ocultar)")
        self._advanced_visible = not self._advanced_visible

    def _refresh_mode(self) -> None:
        is_video = self.mode_var.get() == "video"
        state_video = "normal" if is_video else "disabled"
        for child in self.video_frame.winfo_children():
            self._set_state_recursive(child, state_video)

    @staticmethod
    def _set_state_recursive(widget, state: str) -> None:
        try:
            widget.configure(state=state)
        except Exception:
            pass
        for child in widget.winfo_children():
            FarmBotApp._set_state_recursive(child, state)

    def _pick_video(self) -> None:
        path = filedialog.askopenfilename(
            title="Escolha um video",
            filetypes=[("Videos", "*.mp4 *.avi *.mkv *.mov"), ("Todos os arquivos", "*.*")],
        )
        if path:
            self.video_var.set(path)

    def _pick_record_dir(self) -> None:
        path = filedialog.askdirectory(title="Pasta para gravar as rodadas")
        if path:
            self.record_rounds_var.set(path)

    # -- execucao do bot -----------------------------------------------------
    def _read_selection(self) -> dict:
        return {
            "mode": self.mode_var.get(),
            "monitor": self.monitor_var.get(),
            "video": self.video_var.get(),
            "dry_run": self.dry_run_var.get(),
            "show": self.show_var.get(),
            "save_captures": self.save_captures_var.get(),
            "no_auto_retry": self.no_auto_retry_var.get(),
            "overlay": self.overlay_var.get(),
            "record_rounds": self.record_rounds_var.get(),
            "x_offset": self.x_offset_var.get(),
            "y_offset": self.y_offset_var.get(),
        }

    def _start(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            messagebox.showinfo("FARM BOT", "O bot ja esta em execucao.")
            return
        try:
            args = build_args_from_selection(self._read_selection())
        except ValueError as exc:
            messagebox.showerror("FARM BOT", str(exc))
            return

        self._append_log(
            f"Iniciando (modo={'video' if args.video else 'ao vivo'}, "
            f"monitor={getattr(args, 'monitor', '--')}, dry_run={args.dry_run}, show={args.show})\n"
        )
        self.start_button.configure(state="disabled")
        self._worker = threading.Thread(target=self._run_worker, args=(args,), daemon=True)
        self._worker.start()

    def _run_worker(self, args) -> None:
        writer = _QueueWriter(self._log_queue)
        old_stdout = sys.stdout
        sys.stdout = writer
        try:
            if args.video:
                run_video(args)
            else:
                run_live(args)
        except SystemExit as exc:
            self._log_queue.put(f"\nEncerrado: {exc}\n")
        except Exception:
            self._log_queue.put("\n" + traceback.format_exc())
        finally:
            sys.stdout = old_stdout
            self._log_queue.put("__DONE__")

    def _simulate_stop_key(self) -> None:
        try:
            import pydirectinput

            pydirectinput.press("f10")
            self._append_log("Enviado F10 para encerrar.\n")
        except Exception as exc:
            self._append_log(f"Nao foi possivel simular F10 ({exc}). Aperte F10 no teclado.\n")

    def _drain_log_queue(self) -> None:
        try:
            while True:
                item = self._log_queue.get_nowait()
                if item == "__DONE__":
                    self.start_button.configure(state="normal")
                else:
                    self._append_log(item)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_log_queue)

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _on_close(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            if not messagebox.askyesno(
                "FARM BOT",
                "O bot ainda esta em execucao. Fechar a janela encerra o programa "
                "imediatamente. Prefere apertar F10 para encerrar com seguranca antes?",
            ):
                return
        self.root.destroy()


def main() -> None:
    root = Tk()
    try:
        FarmBotApp(root)
        root.mainloop()
    except Exception:
        try:
            messagebox.showerror("FARM BOT - erro ao iniciar", traceback.format_exc())
        except Exception:
            raise
