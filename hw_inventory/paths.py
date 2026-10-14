"""Pasta de saída na Área de Trabalho de quem executou o programa."""

from __future__ import annotations

import os
import pwd
import re
from pathlib import Path

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def invoking_user() -> str:
    """Usuário da sessão, mesmo quando o programa roda com sudo."""
    sudo_user = os.environ.get("SUDO_USER", "").strip()
    if sudo_user and sudo_user != "root":
        return sudo_user
    current = os.environ.get("USER", "").strip()
    if current and current != "root":
        return current
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except KeyError:
        return "root"


def home_of(user: str) -> Path:
    if user == "root":
        return Path("/root")
    try:
        return Path(pwd.getpwnam(user).pw_dir)
    except KeyError:
        return Path.home()


def desktop_dir(user: str | None = None) -> Path:
    user = user or invoking_user()
    home = home_of(user)
    configured = _xdg_desktop(home)
    if configured is not None:
        return configured
    for name in ("Desktop", "Área de Trabalho", "Area de Trabalho"):
        candidate = home / name
        if candidate.is_dir():
            return candidate
    return home / "Desktop"


def output_dir(user: str | None = None) -> Path:
    return desktop_dir(user) / "Inventario_Patrimonial"


def safe_token(value: str) -> str:
    cleaned = _UNSAFE.sub("-", value.strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-._")
    return cleaned.upper()[:80]


def output_filenames(patrimonio: str, hostname: str) -> tuple[str, str]:
    host = safe_token(hostname) or "PC"
    patrimony = safe_token(patrimonio)
    base = f"{patrimony}_{host}" if patrimony else host
    return f"{base}_inventario.xlsx", f"{base}_relatorio_hardware.pdf"


def give_to_user(path: Path, user: str | None = None) -> None:
    """Devolve a pasta e os arquivos ao usuário que chamou o sudo."""
    if os.geteuid() != 0:
        return
    user = user or invoking_user()
    if not user or user == "root":
        return
    try:
        account = pwd.getpwnam(user)
    except KeyError:
        return
    if path.is_dir():
        os.chmod(path, 0o755)
    elif path.is_file():
        os.chmod(path, 0o644)
    os.chown(path, account.pw_uid, account.pw_gid)


def _xdg_desktop(home: Path) -> Path | None:
    config = home / ".config" / "user-dirs.dirs"
    if not config.is_file():
        return None
    try:
        lines = config.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in lines:
        line = line.strip()
        if not line.startswith("XDG_DESKTOP_DIR="):
            continue
        raw = line.split("=", 1)[1].strip().strip('"').strip("'")
        raw = raw.replace("$HOME", str(home))
        path = Path(raw)
        if path.is_dir():
            return path
    return None
