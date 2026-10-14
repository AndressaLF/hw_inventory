"""Cookie X11 da sessão de quem chamou o programa via sudo.

O Tk roda como root. O servidor só aceita a conexão se XAUTHORITY tiver uma
entrada MIT-MAGIC-COOKIE-1 para o hostname atual e o display. Um arquivo
legível com cookies de outro hostname não envia protocolo nenhum.
"""

from __future__ import annotations

import os
import pwd
import socket
import struct
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

_FAMILY_LOCAL = 256
_FAMILY_WILD = 65535
_COOKIE_NAME = b"MIT-MAGIC-COOKIE-1"
_GRAPHICAL_PREFIXES = (
    "cinnamon",
    "Xwayland",
    "Xorg",
    "gnome-shell",
    "gnome-session",
    "mutter",
    "plasma",
    "kwin",
    "marco",
    "xfwm",
    "mate-",
    "xfce",
    "budgie",
    "sway",
    "labwc",
)


@dataclass(frozen=True)
class XAuthEntry:
    family: int
    address: bytes
    number: bytes
    name: bytes
    data: bytes

    def __repr__(self) -> str:
        return (
            f"XAuthEntry(family={self.family}, address={self.address!r}, "
            f"number={self.number!r}, name={self.name!r}, datalen={len(self.data)})"
        )


def prepare_root_display() -> None:
    """Aponta DISPLAY e XAUTHORITY para a sessão de SUDO_USER quando euid é 0."""
    if os.geteuid() != 0:
        return
    sudo_user = os.environ.get("SUDO_USER", "").strip()
    if not sudo_user or sudo_user == "root":
        return
    try:
        account = pwd.getpwnam(sudo_user)
    except KeyError:
        return

    session = graphical_session_env(account.pw_uid)
    display = os.environ.get("DISPLAY", "").strip() or session.get("DISPLAY", "").strip() or ":0"
    os.environ["DISPLAY"] = display
    hostname = socket.gethostname().split(".", 1)[0]

    chosen = select_xauthority(
        env_xauthority=os.environ.get("XAUTHORITY"),
        process_xauthority=session.get("XAUTHORITY"),
        run_user_dir=Path("/run/user") / str(account.pw_uid),
        home=Path(account.pw_dir),
    )
    server_auth = xorg_server_auth(display)
    for source in (chosen, server_auth):
        if source is not None and authority_matches(source, display, hostname):
            os.environ["XAUTHORITY"] = str(source)
            return
    for source in (server_auth, chosen):
        if source is None:
            continue
        rewritten = rekey_authority(source, display, hostname)
        if rewritten is not None:
            os.environ["XAUTHORITY"] = str(rewritten)
            return
    print("Não foi possível localizar o cookie da sessão gráfica.", file=sys.stderr)


def select_xauthority(
    *,
    env_xauthority: str | None,
    process_xauthority: str | None,
    run_user_dir: Path,
    home: Path,
) -> Path | None:
    """Primeiro arquivo de cookie legível e não vazio, na ordem da sessão."""
    for candidate in (env_xauthority, process_xauthority):
        usable = _usable_file(candidate)
        if usable is not None:
            return usable
    mutter = _newest_mutter(run_user_dir)
    if mutter is not None:
        return mutter
    for candidate in (run_user_dir / "gdm" / "Xauthority", home / ".Xauthority"):
        usable = _usable_file(candidate)
        if usable is not None:
            return usable
    return None


def authority_matches(path: Path, display: str, hostname: str) -> bool:
    try:
        entries = list(iter_xauth(path.read_bytes()))
    except OSError:
        return False
    number = display_number(display).encode()
    host = hostname.encode()
    return any(_entry_matches(entry, number, host) for entry in entries)


def rekey_authority(
    source: Path,
    display: str,
    hostname: str,
    dest: Path | None = None,
) -> Path | None:
    """Copia o cookie do display para o hostname atual, sem alterar o original."""
    try:
        entries = list(iter_xauth(source.read_bytes()))
    except OSError:
        return None
    number = display_number(display).encode()
    chosen = _cookie_for_number(entries, number) or _any_cookie(entries)
    if chosen is None:
        return None
    payload = pack_xauth(
        XAuthEntry(_FAMILY_LOCAL, hostname.encode(), number, _COOKIE_NAME, chosen.data)
    )
    if dest is None:
        fd, name = tempfile.mkstemp(prefix=".hw-inventory-xauth-")
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
        os.chmod(name, 0o600)
        return Path(name)
    dest.write_bytes(payload)
    os.chmod(dest, 0o600)
    return dest


def graphical_session_env(uid: int) -> dict[str, str]:
    proc = Path("/proc")
    if not proc.is_dir():
        return {}
    best: dict[str, str] = {}
    best_score = -1
    for pid in proc.iterdir():
        if not pid.name.isdigit():
            continue
        try:
            if pid.stat().st_uid != uid:
                continue
            comm = (pid / "comm").read_text(encoding="utf-8", errors="replace").strip()
            raw = (pid / "environ").read_bytes()
        except OSError:
            continue
        picked = _display_env(raw)
        if not picked:
            continue
        score = (2 if comm.startswith(_GRAPHICAL_PREFIXES) else 0) + (
            1 if "XAUTHORITY" in picked else 0
        )
        if score > best_score:
            best = picked
            best_score = score
    return best


def xorg_server_auth(display: str | None = None) -> Path | None:
    """Arquivo -auth do Xorg/Xwayland, se este processo puder lê-lo."""
    want = display_number(display) if display else ""
    proc = Path("/proc")
    if not proc.is_dir():
        return None
    fallback: Path | None = None
    for pid in proc.iterdir():
        if not pid.name.isdigit():
            continue
        try:
            raw = (pid / "cmdline").read_bytes()
        except OSError:
            continue
        parts = [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]
        if not parts or not _is_display_server(parts[0]):
            continue
        auth = _auth_argument(parts)
        if auth is None:
            continue
        usable = _usable_file(auth)
        if usable is None:
            continue
        if want and want == _cmdline_display(parts):
            return usable
        fallback = fallback or usable
    return fallback


def display_number(display: str) -> str:
    text = display.strip()
    if text.startswith("unix:"):
        text = text[5:]
    elif ":" in text:
        text = text.split(":", 1)[1]
    number = text.split(".", 1)[0]
    return number or "0"


def iter_xauth(data: bytes):
    index = 0
    size = len(data)
    while index + 4 <= size:
        family, address_len = struct.unpack_from(">HH", data, index)
        index += 4
        if index + address_len + 2 > size:
            return
        address = data[index : index + address_len]
        index += address_len
        number_len = struct.unpack_from(">H", data, index)[0]
        index += 2
        if index + number_len + 2 > size:
            return
        number = data[index : index + number_len]
        index += number_len
        name_len = struct.unpack_from(">H", data, index)[0]
        index += 2
        if index + name_len + 2 > size:
            return
        name = data[index : index + name_len]
        index += name_len
        data_len = struct.unpack_from(">H", data, index)[0]
        index += 2
        if index + data_len > size:
            return
        cookie = data[index : index + data_len]
        index += data_len
        yield XAuthEntry(family, address, number, name, cookie)


def pack_xauth(entry: XAuthEntry) -> bytes:
    parts = [struct.pack(">H", entry.family)]
    for field in (entry.address, entry.number, entry.name, entry.data):
        parts.append(struct.pack(">H", len(field)))
        parts.append(field)
    return b"".join(parts)


def _usable_file(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    text = str(path).strip()
    if not text:
        return None
    candidate = Path(text)
    try:
        if candidate.is_file() and os.access(candidate, os.R_OK) and candidate.stat().st_size > 0:
            return candidate
    except OSError:
        return None
    return None


def _newest_mutter(run_user_dir: Path) -> Path | None:
    try:
        matches = [
            path
            for path in run_user_dir.glob(".mutter-Xwaylandauth.*")
            if _usable_file(path) is not None
        ]
    except OSError:
        return None
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def _entry_matches(entry: XAuthEntry, number: bytes, hostname: bytes) -> bool:
    if entry.name != _COOKIE_NAME or entry.number != number or not entry.data:
        return False
    if entry.family == _FAMILY_WILD:
        return True
    return entry.family == _FAMILY_LOCAL and entry.address == hostname


def _cookie_for_number(entries: list[XAuthEntry], number: bytes) -> XAuthEntry | None:
    chosen = None
    for entry in entries:
        if entry.name == _COOKIE_NAME and entry.number == number and entry.data:
            chosen = entry
    return chosen


def _any_cookie(entries: list[XAuthEntry]) -> XAuthEntry | None:
    chosen = None
    for entry in entries:
        if entry.name == _COOKIE_NAME and entry.data:
            chosen = entry
    return chosen


def _display_env(raw: bytes) -> dict[str, str]:
    found: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        if key in {b"DISPLAY", b"XAUTHORITY"} and value:
            found[key.decode()] = value.decode("utf-8", "replace")
    return found


def _is_display_server(argv0: str) -> bool:
    name = Path(argv0).name
    return name in {"Xorg", "Xwayland"} or "Xorg" in argv0 or "Xwayland" in argv0


def _auth_argument(parts: list[str]) -> str | None:
    if "-auth" not in parts:
        return None
    index = parts.index("-auth")
    if index + 1 >= len(parts):
        return None
    return parts[index + 1]


def _cmdline_display(parts: list[str]) -> str:
    for part in parts:
        if part.startswith(":") or part.startswith("unix:"):
            return display_number(part)
    return ""
