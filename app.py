"""Interface Windows para transcrição privada com whisper.cpp."""
from __future__ import annotations

import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from queue import Empty, Queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from engine import MODELS, Cancelled, ModelManager, Transcriber, export_transcript

DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "TranscreveLocal"
RUNTIME = (Path(sys._MEIPASS) / "runtime" if getattr(sys, "frozen", False)
           else Path(__file__).resolve().parent / "vendor" / "runtime")
MODEL_CHOICES = {"Turbo · recomendado": "turbo", "Máxima qualidade · mais lento": "quality"}
LANGUAGES = {"Português": "pt", "Detectar automaticamente": "auto", "Inglês": "en", "Espanhol": "es"}
MEDIA_EXTENSIONS = ('.mp4', '.mkv', '.mov', '.avi', '.webm', '.m4v', '.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac', '.wma', '.opus', '.mpeg', '.mpg', '.aiff', '.aif', '.mpga', '.3gp', '.m2ts', '.mts', '.ts', '.caf')


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.models = ModelManager(DATA / "models")
        self.queue = Queue()
        self.cancel = threading.Event()
        self.worker = None
        self.closing = False
        self.transcript = None
        self.transcript_source = None
        self.pending_source = None
        self.last_output = None
        self.saved_text = None
        self.source = tk.StringVar()
        self.model = tk.StringVar(value=next(iter(MODEL_CHOICES)))
        self.language = tk.StringVar(value="Português")
        self.model_status = tk.StringVar()
        self.status = tk.StringVar(value="Selecione um vídeo ou áudio para começar.")
        self.setup_ui()
        self.file_drop = None
        if os.name == 'nt':
            from windows_drop import WindowsFileDrop
            try:
                self.file_drop = WindowsFileDrop(root, lambda files: self.queue.put(('files', files)))
            except OSError:
                logging.exception('Arrastar e soltar indisponível; seleção pelo botão continua disponível')
        self.refresh_model()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self.poll)

    def setup_ui(self):
        root = self.root
        root.title("Lume — Transcrição Local")
        self.assets = (Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent) / "assets"
        if (self.assets / "transcreve.ico").is_file():
            root.iconbitmap(str(self.assets / "transcreve.ico"))
        root.geometry("1160x800")
        root.minsize(640, 640)
        cream, ink, muted, coral, line = "#faf9f5", "#141413", "#6c6a64", "#a9583e", "#e6dfd8"
        root.configure(bg=cream)
        self.style = style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background=cream)
        style.configure("Card.TFrame", background="white")
        style.configure("White.TFrame", background="white")
        style.configure("SoftCard.TFrame", background="#f5f0e8")
        style.configure("Soft.TFrame", background="#f5f0e8")
        style.configure("TLabel", background=cream, foreground=ink, font=("Segoe UI", -13))
        for name, bg in (("Soft", "#f5f0e8"), ("Card", "white")):
            style.configure(name + ".TLabel", background=bg, foreground=ink, font=("Segoe UI", -13))
            style.configure(name + "Muted.TLabel", background=bg, foreground=muted, font=("Segoe UI", -11))
        style.configure("Muted.TLabel", foreground=muted, font=("Segoe UI", -11))
        style.configure("TButton", font=("Segoe UI", -12), padding=(10, 7), foreground=ink, background=cream, bordercolor=line, lightcolor=line, darkcolor=line, borderwidth=1, relief="flat", focuscolor=ink)
        style.map("TButton", foreground=[("disabled", "#9b968e")], background=[("active", "#efe9de")])
        style.configure("Accent.TButton", background=coral, foreground="white", bordercolor=coral, lightcolor=coral, darkcolor=coral, font=("Segoe UI", -13, "bold"), focuscolor="white")
        style.map("Accent.TButton", background=[("active", "#914b35"), ("disabled", "#e6dfd8")], foreground=[("disabled", muted), ("!disabled", "white")])
        style.configure("Upload.TButton", padding=(12, 18), background="#efe9de", bordercolor="#e2d8ca", lightcolor="#e2d8ca", darkcolor="#e2d8ca", font=("Segoe UI", -14))
        style.configure("Selected.Upload.TButton", foreground="#2f644a")
        style.configure("Selected.Soft.TLabel", background="#f5f0e8", foreground="#2f644a", font=("Segoe UI", -12, "bold"))
        style.configure("TEntry", padding=5, fieldbackground="#f5f0e8", bordercolor="#f5f0e8", lightcolor="#f5f0e8", darkcolor="#f5f0e8", foreground=muted)
        style.configure("TCombobox", padding=5, fieldbackground="white", bordercolor=line, lightcolor=line, darkcolor=line, arrowsize=12)
        style.map("TCombobox", fieldbackground=[("readonly", "white")], foreground=[("readonly", ink)])
        style.configure("Horizontal.TProgressbar", background=coral, troughcolor=line, lightcolor=coral, darkcolor=coral, borderwidth=0, troughborderwidth=0, thickness=4)
        self.theme_images = {}
        theme = self.assets / "theme"
        for path in theme.glob("*.png"):
            self.theme_images[path.stem] = tk.PhotoImage(file=str(path))
        if self.theme_images:
            style.configure("Card.TFrame", background=cream)
            style.configure("SoftCard.TFrame", background=cream)
            style.configure("Soft.TButton", background="#f5f0e8")
            style.configure("White.TButton", background="white")
            style.configure("Accent.TButton", background="#f5f0e8")
            style.configure("Upload.TButton", background="#f5f0e8")
            for button_style in ("TButton", "Soft.TButton", "White.TButton", "Accent.TButton", "Upload.TButton"):
                style.map(button_style, background=[])
            def image_element(name, base, border=14, states=()):
                style.element_create(name, "image", self.theme_images[base], *[(state, self.theme_images[image]) for state, image in states], border=border, padding=0, sticky="nswe", width=1, height=1)
            for name, image, hover, pressed in (("Rounded", "button", "button-hover", "button-pressed"), ("Primary", "primary", "primary-hover", "primary-pressed"), ("Upload", "upload", "upload", "upload"), ("SelectedUpload", "upload-selected", "upload-selected", "upload-selected")):
                image_element(name + ".button", image, 20 if name in ("Upload", "SelectedUpload") else 14, (("disabled", "disabled"), ("pressed", pressed), ("active", hover)))
                style.layout({"Rounded": "TButton", "Primary": "Accent.TButton", "Upload": "Upload.TButton", "SelectedUpload": "Selected.Upload.TButton"}[name], [(name + ".button", {"sticky": "nswe", "children": [("Button.focus", {"sticky": "nswe", "children": [("Button.padding", {"sticky": "nswe", "children": [("Button.label", {"sticky": "nswe"})]})]})]})])
            for name, image in (("Card.TFrame", "card"), ("SoftCard.TFrame", "soft-card")):
                image_element(image + ".surface", image, 20)
                style.layout(name, [(image + ".surface", {"sticky": "nswe"})])
            image_element("Rounded.field", "input", states=(("focus", "input-focus"),))
            style.element_create("Rounded.downarrow", "image", self.theme_images["chevron"],
                                 ("disabled", self.theme_images["chevron-disabled"]), width=16, height=16, sticky="")
            style.configure("TCombobox", background="#f5f0e8", padding=(12, 7))
            style.map("TCombobox", background=[])
            style.layout("TCombobox", [("Rounded.field", {"sticky": "nswe", "children": [
                ("Combobox.padding", {"sticky": "nswe", "children": [
                    ("Rounded.downarrow", {"side": "right", "sticky": ""}),
                    ("Combobox.textarea", {"sticky": "nswe"}),
                ]}),
            ]})])
        self.outer = outer = ttk.Frame(root, padding=20)
        outer.pack(fill="both", expand=True)
        brand = ttk.Frame(outer)
        brand.pack(fill="x")
        symbol = tk.Canvas(brand, width=25, height=25, bg=cream, highlightthickness=0)
        symbol.pack(side="left", padx=(0, 8))
        for x, top, bottom in ((3, 9, 16), (8, 5, 20), (13, 1, 24), (18, 6, 19), (23, 10, 15)):
            symbol.create_line(x, top, x, bottom, fill=coral, width=3, capstyle="round")
        ttk.Label(brand, text="Lume · Transcrição Local", font=("Segoe UI", -14, "bold")).pack(side="left")
        self.title_frame = title = ttk.Frame(outer)
        title.pack(fill="x", pady=(16, 18))
        ttk.Label(title, text="Dê espaço às suas palavras.", font=("Georgia", -27)).pack(anchor="w")
        ttk.Label(title, text="Arraste uma gravação para a janela ou escolha um arquivo.", style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
        self.workspace = ttk.Frame(outer)
        self.workspace.pack(fill="both", expand=True)
        self.config_card = ttk.Frame(self.workspace, style="SoftCard.TFrame", padding=16)
        self.config_card.columnconfigure(0, weight=1)
        self.file_block = ttk.Frame(self.config_card, style="Soft.TFrame")
        ttk.Label(self.file_block, text="SUA GRAVAÇÃO", style="SoftMuted.TLabel").pack(anchor="w", pady=(0, 8))
        self.select_button = ttk.Button(self.file_block, text="＋  Abrir vídeo ou áudio", style="Upload.TButton", command=self.select_file)
        self.select_button.pack(fill="x")
        self.file_hint = ttk.Label(self.file_block, text="Solte aqui · MP4, MP3, WAV e outros", style="SoftMuted.TLabel")
        self.file_hint.pack(anchor="w", pady=(6, 0))
        self.file_display = tk.StringVar(value="Nenhum arquivo selecionado")
        self.source.trace_add("write", self.refresh_file_selection)
        self.file_entry = ttk.Entry(self.file_block, textvariable=self.file_display, state="readonly", font=("Segoe UI", -11), width=18)
        self.file_entry.pack(fill="x", pady=(5, 0))
        self.options_block = ttk.Frame(self.config_card, style="Soft.TFrame")
        ttk.Label(self.options_block, text="Qualidade da transcrição", style="Soft.TLabel").pack(anchor="w", pady=(0, 5))
        self.model_combo = ttk.Combobox(self.options_block, textvariable=self.model, values=list(MODEL_CHOICES), state="readonly", font=("Segoe UI", -12), width=20)
        self.model_combo.pack(fill="x")
        self.model_combo.bind("<<ComboboxSelected>>", lambda _: self.refresh_model())
        self.model_status_label = ttk.Label(self.options_block, textvariable=self.model_status, style="SoftMuted.TLabel", wraplength=260)
        self.model_status_label.pack(anchor="w", pady=(5, 6))
        model_actions = ttk.Frame(self.options_block, style="Soft.TFrame")
        model_actions.pack(fill="x", pady=(0, 10))
        self.download_button = ttk.Button(model_actions, text="Baixar modelo", style="Soft.TButton", command=lambda: self.start("download"))
        self.download_button.pack(side="left")
        ttk.Button(model_actions, text="Pasta", style="Soft.TButton", command=lambda: self.open_folder(DATA / "models")).pack(side="left", padx=(6, 0))
        ttk.Label(self.options_block, text="Idioma falado", style="Soft.TLabel").pack(anchor="w", pady=(0, 5))
        self.language_combo = ttk.Combobox(self.options_block, textvariable=self.language, values=list(LANGUAGES), state="readonly", font=("Segoe UI", -12), width=18)
        self.language_combo.pack(fill="x")
        self.action_block = ttk.Frame(self.config_card, style="Soft.TFrame")
        self.start_button = ttk.Button(self.action_block, text="Transcrever", style="Accent.TButton", command=lambda: self.start("transcribe"))
        self.start_button.pack(side="left", fill="x", expand=True)
        self.cancel_button = ttk.Button(self.action_block, text="Cancelar", style="Soft.TButton", state="disabled", command=self.request_cancel)
        self.cancel_button.pack(side="left", padx=(6, 0))
        self.status_block = ttk.Frame(self.config_card, style="Soft.TFrame")
        progress_track = ttk.Frame(self.status_block, height=12, style="Soft.TFrame")
        progress_track.pack(fill="x", pady=(0, 6))
        progress_track.pack_propagate(False)
        self.progress = ttk.Progressbar(progress_track, maximum=100)
        self.progress.pack(fill="both", expand=True)
        self.status_label = ttk.Label(self.status_block, textvariable=self.status, style="SoftMuted.TLabel", wraplength=260)
        self.status_label.pack(fill="x")
        self.privacy_label = ttk.Label(self.config_card, text="CPU local · pode demorar. Internet só para baixar modelos.", style="SoftMuted.TLabel", wraplength=260)
        self.editor_card = ttk.Frame(self.workspace, style="Card.TFrame", padding=16)
        self.editor_card.columnconfigure(0, weight=1)
        self.editor_card.rowconfigure(1, weight=1)
        editor_header = ttk.Frame(self.editor_card, style="White.TFrame")
        editor_header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(editor_header, text="Transcrição", style="Card.TLabel", font=("Segoe UI", -15, "bold")).pack(side="left")
        ttk.Label(editor_header, text="SEU ESPAÇO DE ESCRITA", style="CardMuted.TLabel").pack(side="right")
        self.editor = ScrolledText(self.editor_card, wrap="word", height=4, width=1, font=("Segoe UI", -15), bg="white", fg=ink, insertbackground=coral, selectbackground="#ead2c8", selectforeground=ink, relief="flat", bd=0, padx=8, pady=10, undo=True)
        self.editor.frame.grid(row=1, column=0, sticky="nsew")
        self.empty_state = ttk.Frame(self.editor.frame, style="White.TFrame")
        self.empty_title = ttk.Label(self.empty_state, text="Uma nova página.\nUma voz para contar.", style="Card.TLabel", font=("Georgia", -24), justify="center")
        self.empty_title.pack()
        self.empty_hint = ttk.Label(self.empty_state, text="O texto aparece aqui, pronto para\nrevisar e exportar.", style="CardMuted.TLabel", justify="center")
        self.empty_hint.pack(pady=(12, 0))
        self.empty_state.bind("<Button-1>", lambda _: self.editor.focus_set())
        for child in self.empty_state.winfo_children():
            child.bind("<Button-1>", lambda _: self.editor.focus_set())
        self.editor.bind("<<Modified>>", self.refresh_empty_state)
        self.editor.bind("<FocusIn>", lambda _: self.empty_state.place_forget())
        self.editor.bind("<FocusOut>", self.refresh_empty_state)
        footer = ttk.Frame(self.editor_card, style="White.TFrame")
        footer.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        exports = ttk.Frame(footer, style="White.TFrame")
        exports.pack(fill="x")
        self.export_buttons = []
        for label, action in [("Copiar", self.copy), ("TXT", lambda: self.save("txt")), ("SRT", lambda: self.save("srt")), ("VTT", lambda: self.save("vtt"))]:
            button = ttk.Button(exports, text=label, style="White.TButton", command=action, state="disabled", width=5)
            button.pack(side="left", padx=(0, 5))
            self.export_buttons.append(button)
        self.folder_button = ttk.Button(exports, text="Pasta", style="White.TButton", command=lambda: self.open_folder(self.last_output.parent), state="disabled", width=5)
        self.folder_button.pack(side="right")
        ttk.Label(footer, text="Edições: TXT. Legendas mantêm o texto e os tempos originais.", style="CardMuted.TLabel", wraplength=520).pack(anchor="w", pady=(8, 0))
        self.layout_mode = None
        root.bind("<Configure>", self.reflow, add="+")
        self.reflow()
        self.refresh_empty_state()

    def reflow(self, event=None):
        if event is not None and event.widget is not self.root:
            return
        width = self.root.winfo_width()
        if width < 2:
            width = 1160
        narrow = width < 900
        mode = "narrow" if narrow else "wide"
        if mode == self.layout_mode:
            return
        self.layout_mode = mode
        self.outer.configure(padding=12 if narrow else 20)
        self.title_frame.pack_configure(pady=(8, 10) if narrow else (16, 18))
        self.editor_card.configure(padding=12 if narrow else 16)
        self.empty_title.configure(text="Uma voz para contar." if narrow else "Uma nova página.\nUma voz para contar.", font=("Georgia", -20 if narrow else -24))
        self.empty_hint.configure(text="O texto aparece aqui, pronto para revisar e exportar." if narrow else "O texto aparece aqui, pronto para\nrevisar e exportar.")
        self.empty_hint.pack_configure(pady=(6, 0) if narrow else (12, 0))
        for widget in (self.file_block, self.options_block, self.action_block, self.status_block, self.privacy_label):
            widget.grid_forget()
        self.config_card.grid_forget()
        self.editor_card.grid_forget()
        self.workspace.columnconfigure(0, weight=0, minsize=0)
        self.workspace.columnconfigure(1, weight=0, minsize=0)
        self.workspace.rowconfigure(0, weight=0)
        self.workspace.rowconfigure(1, weight=0)
        self.config_card.columnconfigure(0, weight=1, minsize=0)
        self.config_card.columnconfigure(1, weight=0, minsize=0)
        if narrow:
            self.workspace.columnconfigure(0, weight=1)
            self.workspace.rowconfigure(1, weight=1)
            self.config_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
            self.editor_card.grid(row=1, column=0, sticky="nsew")
            self.config_card.columnconfigure(1, weight=1, uniform="config")
            self.config_card.columnconfigure(0, weight=1, uniform="config")
            self.file_block.grid(row=0, column=0, sticky="new", padx=(0, 16))
            self.options_block.grid(row=0, column=1, sticky="new")
            self.action_block.grid(row=1, column=0, sticky="ew", padx=(0, 16), pady=(10, 0))
            self.status_block.grid(row=1, column=1, sticky="ew", pady=(10, 0))
            self.privacy_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
            self.privacy_label.configure(wraplength=max(540, width - 80))
        else:
            self.config_card.columnconfigure(0, uniform="")
            self.config_card.columnconfigure(1, uniform="")
            self.workspace.columnconfigure(0, minsize=300)
            self.workspace.columnconfigure(1, weight=1)
            self.workspace.rowconfigure(0, weight=1)
            self.config_card.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
            self.editor_card.grid(row=0, column=1, sticky="nsew")
            self.file_block.grid(row=0, column=0, sticky="ew")
            self.options_block.grid(row=1, column=0, sticky="ew", pady=(20, 0))
            self.action_block.grid(row=2, column=0, sticky="ew", pady=(20, 0))
            self.status_block.grid(row=3, column=0, sticky="ew", pady=(12, 0))
            self.privacy_label.grid(row=4, column=0, sticky="sw", pady=(20, 0))
            self.privacy_label.configure(wraplength=260)

    def refresh_empty_state(self, event=None):
        if self.editor.edit_modified():
            self.editor.edit_modified(False)
        if self.editor.get("1.0", "end-1c") or self.editor.focus_get() is self.editor:
            self.empty_state.place_forget()
        else:
            self.empty_state.place(relx=.5, rely=.45, anchor="center")

    def refresh_file_selection(self, *_):
        selected = bool(self.source.get())
        self.file_display.set(Path(self.source.get()).name if selected else "Nenhum arquivo selecionado")
        self.select_button.configure(text="✓  Trocar arquivo" if selected else "＋  Abrir vídeo ou áudio",
                                     style="Selected.Upload.TButton" if selected else "Upload.TButton")
        self.file_hint.configure(text="✓  Arquivo selecionado" if selected else "Solte aqui · MP4, MP3, WAV e outros",
                                 style="Selected.Soft.TLabel" if selected else "SoftMuted.TLabel")
        self.file_entry.configure(font=("Segoe UI", -13, "bold") if selected else ("Segoe UI", -11),
                                  foreground="#263b30" if selected else "#6c6a64")
        if "disabled" not in self.select_button.state():
            self.status.set("Arquivo selecionado. Clique em Transcrever para começar." if selected
                            else "Selecione um vídeo ou áudio para começar.")

    def select_file(self):
        selected = filedialog.askopenfilename(title="Selecione um vídeo ou áudio", filetypes=[("Vídeos e áudios", " ".join('*' + ext for ext in MEDIA_EXTENSIONS)), ("Todos os arquivos", "*.*")])
        if selected:
            self.receive_files([selected])

    def receive_files(self, files):
        if self.closing or 'disabled' in self.select_button.state():
            return
        if not files:
            return
        if len(files) != 1:
            messagebox.showwarning('Um arquivo por vez', 'Solte apenas um vídeo ou áudio por vez.', parent=self.root)
            return
        source = Path(files[0])
        if not source.is_file() or source.suffix.lower() not in MEDIA_EXTENSIONS:
            messagebox.showwarning('Selecione um vídeo ou áudio', 'Escolha um arquivo de mídia existente, como MP4, MOV, MP3, M4A ou WAV.', parent=self.root)
            return
        self.source.set(str(source))

    def refresh_model(self):
        model = MODELS[MODEL_CHOICES[self.model.get()]]
        path = DATA / "models" / model['filename']
        try:
            present = path.is_file() and path.stat().st_size == model['size']
        except OSError:
            present = False
        self.model_status.set("● Modelo disponível · verificado ao usar" if present else "○ Modelo ainda não baixado (aproximadamente 600 MB–1,1 GB)")

    def set_busy(self, busy):
        for widget in (self.select_button, self.start_button, self.download_button):
            widget.configure(state="disabled" if busy else "normal")
        for widget in (self.model_combo, self.language_combo):
            widget.configure(state="disabled" if busy else "readonly")
        self.cancel_button.configure(state="normal" if busy else "disabled")

    def start(self, operation):
        if self.worker and self.worker.is_alive():
            return
        source = Path(self.source.get())
        if operation == "transcribe" and (not self.source.get() or not source.is_file()):
            messagebox.showwarning("Selecione um arquivo", "Escolha um vídeo ou áudio existente antes de transcrever.")
            return
        if operation == "transcribe" and not self.confirm_discard():
            return
        model_key = MODEL_CHOICES[self.model.get()]
        language = LANGUAGES[self.language.get()]
        self.cancel.clear()
        self.set_busy(True)
        if operation == "transcribe":
            self.pending_source = source.resolve()
            self.editor.configure(state="disabled")
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self.status.set("Preparando… O primeiro uso pode exigir o download do modelo.")

        def work():
            def callback(stage, progress, message):
                self.queue.put(("progress", (stage, progress, message)))
            try:
                if operation == "download":
                    self.models.ensure(model_key, callback, self.cancel)
                    self.queue.put(("downloaded", None))
                else:
                    result = Transcriber(RUNTIME, self.models).transcribe(source, model_key, language, callback, self.cancel)
                    self.queue.put(("result", result))
            except Cancelled:
                self.queue.put(("cancelled", None))
            except Exception as error:
                logging.exception("Falha na operação %s", operation)
                self.queue.put(("error", str(error)))
            finally:
                self.queue.put(("done", None))

        self.worker = threading.Thread(target=work, name="Transcricao", daemon=False)
        self.worker.start()

    def poll(self):
        try:
            while True:
                kind, value = self.queue.get_nowait()
                if kind == "files":
                    self.receive_files(value)
                elif kind == "progress":
                    _, progress, message = value
                    if not self.cancel.is_set():
                        self.status.set(message if progress is None else f"{message} {max(0, min(100, round(progress * 100)))}%")
                    if progress is None:
                        if self.progress["mode"] != "indeterminate":
                            self.progress.configure(mode="indeterminate")
                            self.progress.start(12)
                    else:
                        self.progress.stop()
                        self.progress.configure(mode="determinate", value=max(0, min(100, progress * 100)))
                elif kind == "result":
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=100)
                    self.transcript = value
                    self.transcript_source = self.pending_source
                    self.editor.configure(state="normal")
                    self.editor.delete("1.0", "end")
                    self.editor.insert("1.0", value.text)
                    self.saved_text = None
                    for button in self.export_buttons:
                        button.configure(state="normal")
                    self.status.set("Transcrição concluída. Revise o texto e salve no formato desejado.")
                elif kind == "downloaded":
                    self.status.set("Modelo baixado e verificado. Você já pode transcrever sem internet.")
                elif kind == "cancelled":
                    self.status.set("Operação cancelada. Você pode tentar novamente.")
                elif kind == "error":
                    self.status.set("Não foi possível concluir a operação.")
                    if not self.closing:
                        messagebox.showerror("Não foi possível concluir", f"{value}\n\nConfira o arquivo, o espaço disponível e a conexão para baixar modelos.\nRegistro local: {DATA / 'app.log'}")
                elif kind == "done":
                    self.progress.stop()
                    self.editor.configure(state="normal")
                    self.set_busy(False)
                    self.refresh_model()
        except Empty:
            pass
        if self.closing and not (self.worker and self.worker.is_alive()):
            self.root.destroy()
            return
        self.root.after(100, self.poll)

    def request_cancel(self):
        self.cancel.set()
        self.cancel_button.configure(state="disabled")
        self.status.set("Cancelando… Aguarde a finalização do processamento.")

    def close(self):
        if self.worker and self.worker.is_alive():
            if not self.closing and messagebox.askyesno("Processamento em andamento", "Cancelar a operação e fechar? O programa aguardará o encerramento seguro."):
                if not self.confirm_discard():
                    return
                self.closing = True
                self.request_cancel()
        elif self.confirm_discard():
            self.root.destroy()

    def confirm_discard(self):
        text = self.editor.get("1.0", "end-1c")
        if not text or self.saved_text == text:
            return True
        return messagebox.askyesno("Texto ainda não salvo", "O texto atual ainda não foi salvo em TXT. Deseja continuar e descartar esse texto?")

    def copy(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.editor.get("1.0", "end-1c"))
        self.status.set("Texto copiado.")

    def save(self, format):
        if self.transcript is None:
            return
        selected = filedialog.asksaveasfilename(title="Salvar transcrição", initialfile=(self.transcript_source or Path(self.source.get())).stem + "." + format, defaultextension="." + format, filetypes=[(format.upper(), "*." + format)], confirmoverwrite=True)
        if not selected:
            return
        try:
            target = Path(selected)
            if target.resolve() in (Path(self.source.get()).resolve(), self.transcript_source):
                messagebox.showerror("Proteção do arquivo original", "Escolha outro nome. O vídeo ou áudio original não pode ser substituído.")
                return
            export_transcript(self.transcript, target, format, edited_text=self.editor.get("1.0", "end-1c") if format == "txt" else None)
            if format == "txt":
                self.saved_text = self.editor.get("1.0", "end-1c")
            self.last_output = target
            self.folder_button.configure(state="normal")
            self.status.set(f"Arquivo salvo: {target.name}")
        except Exception as error:
            logging.exception("Erro ao exportar")
            messagebox.showerror("Falha ao salvar", f"{error}\n\nEscolha uma pasta com permissão de escrita e tente novamente.")

    def open_folder(self, path):
        try:
            path.mkdir(parents=True, exist_ok=True)
            os.startfile(path)
        except OSError as error:
            messagebox.showerror("Não foi possível abrir a pasta", str(error))


def main():
    parser = argparse.ArgumentParser(description="Lume — Transcrição Local")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--smoke-report", type=Path)
    args = parser.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(DATA / "app.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(message)s")
    root = tk.Tk()
    app = App(root)
    if args.smoke_test:
        root.update()
        assert root.winfo_exists() and app.editor.winfo_exists()
        assert all(key in MODELS for key in MODEL_CHOICES.values())
        report = {"success": True, "title": root.title(), "tk": root.tk.call("info", "patchlevel"), "runtime_exists": RUNTIME.is_dir(), "models_path": str(DATA / "models"), "frozen": bool(getattr(sys, "frozen", False)), "file_drop_active": bool(app.file_drop and app.file_drop.active)}
        assert os.name != 'nt' or report['file_drop_active'], 'Arrastar e soltar não foi ativado.'
        if os.name == 'nt':
            from verify_drop import exercise_drop
            report['drop_mainloop'] = exercise_drop(root, app)
        if args.smoke_report:
            args.smoke_report.parent.mkdir(parents=True, exist_ok=True)
            args.smoke_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
