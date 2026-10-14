"""Licença do Linux instalado neste computador.

A chave do relatório é a licença da distribuição (por exemplo GPL-2.0+).
Se o sistema tiver uma assinatura (Ubuntu Pro), entra o token dessa assinatura.
A tabela ACPI MSDM continua disponível só como leitura de uma chave OEM
que o firmware eventualmente guarde; ela não é a chave do Linux.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_KEY = re.compile(r"[A-Z0-9]{5}(?:-[A-Z0-9]{5}){4}")
_LICENSE_LINE = re.compile(r"(?m)^License:\s*([A-Za-z0-9.+-]+)")
_FREE = re.compile(r"^(?:GPL|LGPL|AGPL|MIT|BSD|Apache|MPL|Artistic|CC0|ISC)", re.IGNORECASE)
_MSDM = Path("/sys/firmware/acpi/tables/MSDM")
_PRO_TOKEN = Path("/var/lib/ubuntu-advantage/private/machine-token.json")
_FREE_DISTROS = {
    "linuxmint": "GPL-2.0+",
    "ubuntu": "GPL-2.0+",
    "debian": "GPL-2.0+",
    "pop": "GPL-2.0+",
    "zorin": "GPL-2.0+",
    "fedora": "MIT",
    "rhel": "GPL-2.0",
    "arch": "GPL-2.0",
    "manjaro": "GPL-2.0",
    "opensuse-leap": "GPL-2.0",
    "opensuse-tumbleweed": "GPL-2.0",
}


def read_firmware_key() -> str:
    try:
        data = _MSDM.read_bytes()
    except OSError:
        return ""
    return key_from_msdm(data)


def key_from_msdm(data: bytes) -> str:
    if len(data) >= 56 and data[:4] == b"MSDM":
        length = int.from_bytes(data[52:56], "little")
        if 0 < length <= 64 and 56 + length <= len(data):
            text = data[56 : 56 + length].decode("ascii", "ignore").strip("\x00").strip()
            if _KEY.fullmatch(text):
                return text
    match = _KEY.search(data.decode("latin-1", "ignore"))
    return match.group(0) if match else ""


def partial_key(key: str) -> str:
    text = key.strip()
    if not text:
        return ""
    if is_free_license(text):
        return text
    return text[-5:]


def is_free_license(key: str) -> bool:
    return bool(_FREE.match((key or "").strip()))


def license_from_copyright(text: str) -> str:
    match = _LICENSE_LINE.search(text or "")
    return match.group(1) if match else ""


def token_from_ubuntu_pro(data: dict) -> str:
    for name in ("contractToken", "token"):
        value = data.get(name)
        if not isinstance(value, str):
            continue
        text = value.strip()
        if len(text) < 10 or " " in text or text.count(".") >= 2:
            continue
        return text
    return ""


def read_linux_key() -> str:
    token = _subscription_token()
    if token:
        return token
    return _distro_license()


def _subscription_token() -> str:
    try:
        data = json.loads(_PRO_TOKEN.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return ""
    if not isinstance(data, dict):
        return ""
    return token_from_ubuntu_pro(data)


def _distro_license() -> str:
    release = _os_release()
    distro = release.get("ID", "").lower()
    paths = [Path("/usr/share/doc/base-files/copyright")]
    if distro == "linuxmint":
        paths.insert(0, Path("/usr/share/doc/mintsystem/copyright"))
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        found = license_from_copyright(text)
        if found:
            return found
    return _FREE_DISTROS.get(distro, "")


def _os_release() -> dict[str, str]:
    found: dict[str, str] = {}
    try:
        text = Path("/etc/os-release").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return found
    for line in text.splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        found[key.strip()] = value.strip().strip('"')
    return found
