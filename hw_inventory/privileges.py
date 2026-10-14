"""O programa só inicia com permissão de administrador (root)."""

from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import messagebox


def is_root() -> bool:
    return os.geteuid() == 0


def ensure_root_or_exit() -> None:
    if is_root():
        return
    _show_blocked_dialog()
    raise SystemExit(1)


def _show_blocked_dialog() -> None:
    root = tk.Tk()
    root.withdraw()
    root.title("Privilegios insuficientes")
    messagebox.showerror(
        "Privilegios insuficientes",
        "O programa só inicia com permissão de administrador.\n\n"
        "Feche esta janela e execute de novo com sudo, "
        "preservando a sessão gráfica:\n\n"
        "sudo -E .venv/bin/python -m hw_inventory\n\n"
        "Ou, se já existir o binário:\n\n"
        "sudo -E ./dist/hw-inventory",
        parent=root,
    )
    root.destroy()
    try:
        sys.stdout.flush()
    except Exception:
        pass
