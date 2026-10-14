"""Interface do inventário local, no mesmo fluxo do programa de Windows."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
import traceback
from tkinter import messagebox, ttk

from hw_inventory import __version__
from hw_inventory.ad import check_ad
from hw_inventory.models import FormData
from hw_inventory.report import needs_patrimonio_confirmation, run_inventory, validate_form

_NAVY = "#1e3a5f"
_GREEN = "#1b7a4e"
_BLUE = "#1d4e89"
_BG = "#f4f7fb"
_CARD = "#ffffff"
_MUTED = "#5c6b7a"


class InventoryApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.mode = "individual"
        self.progress: tk.Toplevel | None = None
        self._worker: threading.Thread | None = None
        self._results: queue.Queue = queue.Queue()
        self.fields: dict[str, tk.Widget] = {}
        self.title(f"Inventário patrimonial · v{__version__}")
        self.configure(bg=_BG)
        self.minsize(640, 520)
        self.geometry("760x680")
        self._center()
        self._styles()
        self.container = ttk.Frame(self, padding=16)
        self.container.pack(fill="both", expand=True)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.show_mode_selection()

    def show_mode_selection(self) -> None:
        self._clear()
        self.title(f"Inventário patrimonial · v{__version__}")
        header = tk.Frame(self.container, bg=_NAVY)
        header.pack(fill="x")
        tk.Label(
            header,
            text=f"Inventário patrimonial  ·  v{__version__}",
            bg=_NAVY,
            fg="white",
            font=("DejaVu Sans", 15, "bold"),
            anchor="w",
            padx=16,
            pady=14,
        ).pack(fill="x")
        tk.Label(
            self.container,
            text="Escolha como inventariar este computador. A coleta é sempre local.",
            bg=_BG,
            fg=_MUTED,
            font=("DejaVu Sans", 10),
            anchor="w",
            pady=12,
        ).pack(fill="x")

        cards = tk.Frame(self.container, bg=_BG)
        cards.pack(fill="both", expand=True)
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)

        self._mode_card(
            cards,
            column=0,
            title="Modo Individual (recomendado)",
            color=_GREEN,
            lines=(
                "Uso geral, offline ou com pendrive",
                "Não depende de Active Directory",
                "Um computador por vez",
                "Depois de Concluído, fecha sozinho",
            ),
            command=lambda: self.select_mode("individual"),
        )
        self._mode_card(
            cards,
            column=1,
            title="Modo Active Directory",
            color=_BLUE,
            lines=(
                "Quando a instituição exigir este modo",
                "Precisa de domínio e do grupo Administrador",
                "Se não liberar, use Individual",
                "Continua inventariando só este PC",
            ),
            command=self._choose_ad,
        )

    def select_mode(self, mode: str) -> None:
        self.mode = mode
        self.show_form()

    def show_form(self) -> None:
        self._clear()
        self.title(f"Inventário patrimonial de hardware · v{__version__}")
        header = tk.Frame(self.container, bg=_NAVY)
        header.pack(fill="x")
        tk.Label(
            header,
            text="Inventário patrimonial de hardware",
            bg=_NAVY,
            fg="white",
            font=("DejaVu Sans", 14, "bold"),
            anchor="w",
            padx=14,
            pady=8,
        ).pack(fill="x")
        tk.Label(
            header,
            text=f"{'Modo Individual' if self.mode == 'individual' else 'Modo Active Directory'}  ·  v{__version__}  ·  somente este computador",
            bg=_NAVY,
            fg="#d6e2f0",
            font=("DejaVu Sans", 9),
            anchor="w",
            padx=14,
            pady=0,
        ).pack(fill="x", pady=(0, 10))

        actions = tk.Frame(self.container, bg=_BG)
        actions.pack(side="bottom", fill="x", pady=(10, 0))
        hint = tk.Label(
            actions,
            text="Os arquivos vão para a Área de Trabalho, na pasta Inventario_Patrimonial.",
            bg=_BG,
            fg=_MUTED,
            font=("DejaVu Sans", 9),
            anchor="w",
            justify="left",
        )
        hint.pack(fill="x", pady=(0, 8))

        def _wrap_hint(event) -> None:
            hint.configure(wraplength=max(event.width - 4, 200))

        actions.bind("<Configure>", _wrap_hint)
        buttons = tk.Frame(actions, bg=_BG)
        buttons.pack(fill="x")
        tk.Button(
            buttons,
            text="Voltar",
            command=self.show_mode_selection,
            bg=_BG,
            fg=_NAVY,
            relief="flat",
            font=("DejaVu Sans", 10),
            padx=10,
            pady=8,
            cursor="hand2",
        ).pack(side="left")
        self.generate_button = tk.Button(
            buttons,
            text="Gerar inventario",
            command=self.on_generate,
            bg=_GREEN,
            fg="white",
            activebackground="#14633e",
            activeforeground="white",
            relief="flat",
            font=("DejaVu Sans", 12, "bold"),
            padx=18,
            pady=10,
            cursor="hand2",
        )
        self.generate_button.pack(side="right", fill="x", expand=True, padx=(12, 0))

        canvas = tk.Canvas(self.container, bg=_BG, highlightthickness=0)
        scroll = ttk.Scrollbar(self.container, orient="vertical", command=canvas.yview)
        form = tk.Frame(canvas, bg=_BG)
        form_window = canvas.create_window((0, 0), window=form, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True, pady=(12, 0))
        scroll.pack(side="right", fill="y", pady=(12, 0))

        def _fit(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(form_window, width=canvas.winfo_width())

        form.bind("<Configure>", _fit)
        canvas.bind("<Configure>", _fit)
        canvas.bind_all("<Button-4>", lambda _event: canvas.yview_scroll(-3, "units"))
        canvas.bind_all("<Button-5>", lambda _event: canvas.yview_scroll(3, "units"))

        self._field(form, "patrimonio", "Nº patrimônio", "Número do bem, se existir")
        self._field(form, "responsavel", "Responsável *", "Quem responde pelo equipamento")
        self._field(form, "local", "Local *", "Sala, bancada ou laboratório")

        optional = tk.LabelFrame(
            form,
            text=" Outros campos (opcionais) ",
            bg=_CARD,
            fg=_NAVY,
            font=("DejaVu Sans", 10, "bold"),
            padx=12,
            pady=8,
        )
        optional.pack(fill="x", pady=8)
        self._field(optional, "instituicao", "Instituição", "Nome da unidade")
        self._field(optional, "setor", "Setor", "Setor ou departamento")
        pair = tk.Frame(optional, bg=_CARD)
        pair.pack(fill="x")
        pair.columnconfigure(0, weight=1)
        pair.columnconfigure(1, weight=1)
        self._field(pair, "compra", "Compra", "Data ou referência", grid=(0, 0))
        self._field(pair, "garantia", "Garantia", "Até quando", grid=(0, 1))
        self._field(optional, "nota_fiscal", "Nota fiscal", "Número, se houver")
        self._status_field(optional)
        self._field(optional, "chave_licenca", "Chave de licença", "Opcional. A licença do Linux entra sozinha no relatório.")
        self._text_field(optional, "observacoes", "Observações")
        self._prefill_license_key()

    def _prefill_license_key(self) -> None:
        from hw_inventory.license_key import is_free_license, read_linux_key

        key = read_linux_key()
        entry = self.fields.get("chave_licenca")
        if key and not is_free_license(key) and isinstance(entry, tk.Entry) and not entry.get().strip():
            entry.insert(0, key)

    def on_generate(self) -> None:
        form = self.read_form()
        error = validate_form(form)
        if error:
            messagebox.showerror("Erro", error, parent=self)
            return
        if needs_patrimonio_confirmation(form):
            proceed = messagebox.askyesno(
                "Sem patrimônio",
                "O número de patrimônio está em branco.\n\n"
                "O relatório será provisório e incluirá um alerta de bem sem tombamento.\n\n"
                "Deseja continuar?",
                parent=self,
            )
            if not proceed:
                return
        self.generate_button.configure(state="disabled")
        self._open_progress()
        self._worker = threading.Thread(
            target=self._generate_worker,
            args=(form, self.mode),
            daemon=True,
        )
        self._worker.start()
        self.after(100, self._poll_generation)

    def _poll_generation(self) -> None:
        try:
            kind, payload = self._results.get_nowait()
        except queue.Empty:
            if self.winfo_exists():
                self.after(100, self._poll_generation)
            return
        if kind == "ok":
            self._generation_done(payload)
            return
        self._generation_failed(payload)

    def read_form(self) -> FormData:
        def value(name: str) -> str:
            widget = self.fields[name]
            if isinstance(widget, tk.Text):
                return widget.get("1.0", "end").strip()
            return str(widget.get()).strip()

        return FormData(
            patrimonio=value("patrimonio"),
            responsavel=value("responsavel"),
            local=value("local"),
            instituicao=value("instituicao"),
            setor=value("setor"),
            compra=value("compra"),
            garantia=value("garantia"),
            nota_fiscal=value("nota_fiscal"),
            status=value("status"),
            chave_licenca=value("chave_licenca"),
            observacoes=value("observacoes"),
        )

    def _generate_worker(self, form: FormData, mode: str) -> None:
        try:
            result = run_inventory(form, mode)
        except Exception as exc:
            traceback.print_exc()
            message = str(exc) or exc.__class__.__name__
            self._results.put(("erro", message))
            return
        self._results.put(("ok", result))

    def _generation_done(self, result) -> None:
        self._close_progress()
        if self.generate_button.winfo_exists():
            self.generate_button.configure(state="normal")
        messagebox.showinfo(
            "Concluído",
            "Inventário gerado com sucesso.\n\n"
            f"Pasta:\n{result.folder}\n\n"
            f"{result.spreadsheet}\n"
            f"{result.pdf}",
            parent=self,
        )
        if self.mode == "individual":
            self.destroy()
            return
        again = messagebox.askyesno(
            "Continuar?",
            "Deseja inventariar outro equipamento neste computador?",
            parent=self,
        )
        if not again:
            self.destroy()

    def _generation_failed(self, message: str) -> None:
        self._close_progress()
        if self.generate_button.winfo_exists():
            self.generate_button.configure(state="normal")
        messagebox.showerror(
            "Erro",
            "Não foi possível concluir a coleta ou gravar os arquivos.\n\n" + message,
            parent=self,
        )

    def _choose_ad(self) -> None:
        status = check_ad()
        if not status.authorized:
            messagebox.showwarning("Modo AD indisponível", status.reason, parent=self)
            return
        messagebox.showinfo(
            "Modo AD autorizado",
            "Modo Active Directory autorizado.\n\n"
            f"Domínio: {status.domain}\n\n"
            "A coleta será feita somente neste computador.",
            parent=self,
        )
        self.select_mode("ad")

    def _open_progress(self) -> None:
        window = tk.Toplevel(self)
        window.title("Gerando inventário")
        window.configure(bg=_CARD)
        window.resizable(False, False)
        window.transient(self)
        window.protocol("WM_DELETE_WINDOW", lambda: None)
        tk.Label(
            window,
            text="Coletando as informações deste computador\ne gerando a planilha e o PDF.",
            bg=_CARD,
            fg=_NAVY,
            font=("DejaVu Sans", 11),
            justify="center",
            padx=28,
            pady=18,
        ).pack()
        bar = ttk.Progressbar(window, mode="indeterminate", length=300)
        bar.pack(padx=28, pady=(0, 20))
        bar.start(12)
        self._progress_bar = bar
        window.update_idletasks()
        self._place_over_parent(window)
        window.grab_set()
        self.progress = window

    def _close_progress(self) -> None:
        bar = getattr(self, "_progress_bar", None)
        if bar is not None:
            try:
                bar.stop()
            except tk.TclError:
                pass
            self._progress_bar = None
        if self.progress is not None:
            try:
                if self.progress.winfo_exists():
                    self.progress.grab_release()
                    self.progress.destroy()
            except tk.TclError:
                pass
        self.progress = None

    def _mode_card(self, parent, column: int, title: str, color: str, lines: tuple[str, ...], command) -> None:
        card = tk.Frame(parent, bg=_CARD, highlightbackground=color, highlightthickness=2)
        card.grid(row=0, column=column, sticky="nsew", padx=8, pady=4)
        tk.Label(
            card,
            text=title,
            bg=color,
            fg="white",
            font=("DejaVu Sans", 11, "bold"),
            anchor="w",
            padx=12,
            pady=10,
        ).pack(fill="x")
        body = tk.Frame(card, bg=_CARD)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        for line in lines:
            tk.Label(
                body,
                text="•  " + line,
                bg=_CARD,
                fg="#243140",
                font=("DejaVu Sans", 10),
                anchor="w",
                justify="left",
            ).pack(fill="x", pady=2)
        tk.Button(
            card,
            text="Usar este modo",
            command=command,
            bg=color,
            fg="white",
            activeforeground="white",
            relief="flat",
            font=("DejaVu Sans", 10, "bold"),
            padx=10,
            pady=6,
            cursor="hand2",
        ).pack(anchor="w", padx=12, pady=(0, 12))

    def _field(self, parent, name: str, label: str, hint: str, grid: tuple[int, int] | None = None) -> None:
        frame = tk.Frame(parent, bg=parent["bg"])
        if grid is None:
            frame.pack(fill="x", pady=4)
        else:
            frame.grid(row=grid[0], column=grid[1], sticky="ew", padx=4, pady=4)
        tk.Label(frame, text=label, bg=parent["bg"], fg=_NAVY, font=("DejaVu Sans", 10, "bold"), anchor="w").pack(fill="x")
        entry = tk.Entry(frame, font=("DejaVu Sans", 11), relief="solid", bd=1)
        entry.pack(fill="x", ipady=4, pady=(2, 0))
        tk.Label(frame, text=hint, bg=parent["bg"], fg=_MUTED, font=("DejaVu Sans", 8), anchor="w").pack(fill="x")
        self.fields[name] = entry

    def _status_field(self, parent) -> None:
        frame = tk.Frame(parent, bg=_CARD)
        frame.pack(fill="x", pady=4)
        tk.Label(frame, text="Status do bem", bg=_CARD, fg=_NAVY, font=("DejaVu Sans", 10, "bold"), anchor="w").pack(fill="x")
        status = ttk.Combobox(
            frame,
            values=("ativo", "em manutenção", "emprestado", "transferido", "baixado"),
            font=("DejaVu Sans", 11),
        )
        status.pack(fill="x", ipady=2, pady=(2, 0))
        tk.Label(
            frame,
            text="Exemplo: ativo. Você pode digitar outro status.",
            bg=_CARD,
            fg=_MUTED,
            font=("DejaVu Sans", 8),
            anchor="w",
        ).pack(fill="x")
        self.fields["status"] = status

    def _text_field(self, parent, name: str, label: str) -> None:
        frame = tk.Frame(parent, bg=_CARD)
        frame.pack(fill="x", pady=4)
        tk.Label(frame, text=label, bg=_CARD, fg=_NAVY, font=("DejaVu Sans", 10, "bold"), anchor="w").pack(fill="x")
        text = tk.Text(frame, height=4, font=("DejaVu Sans", 11), relief="solid", bd=1, wrap="word")
        text.pack(fill="x", pady=(2, 0))
        self.fields[name] = text

    def _styles(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background=_BG)
        style.configure("Horizontal.TProgressbar", troughcolor="#e6edf5", background=_GREEN)

    def _clear(self) -> None:
        self.unbind_all("<Button-4>")
        self.unbind_all("<Button-5>")
        for child in self.container.winfo_children():
            child.destroy()
        self.fields = {}

    def _center(self) -> None:
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = max((self.winfo_screenwidth() - width) // 2, 0)
        y = max((self.winfo_screenheight() - height) // 2, 0)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _place_over_parent(self, window: tk.Toplevel) -> None:
        window.update_idletasks()
        x = self.winfo_rootx() + max((self.winfo_width() - window.winfo_width()) // 2, 0)
        y = self.winfo_rooty() + max((self.winfo_height() - window.winfo_height()) // 2, 0)
        window.geometry(f"+{x}+{y}")

    def _close(self) -> None:
        self.destroy()


def main() -> None:
    from hw_inventory.privileges import ensure_root_or_exit
    from hw_inventory.x11_session import prepare_root_display

    ensure_root_or_exit()
    prepare_root_display()
    app = InventoryApp()
    app.mainloop()
