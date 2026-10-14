"""Checagem do modo Active Directory neste computador.

A coleta nunca sai da máquina local. O modo AD só libera quando o PC está
no domínio e o usuário da sessão está no grupo Administrador do domínio.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass

from hw_inventory.collect import run_command
from hw_inventory.paths import invoking_user

_ADMIN_GROUPS = (
    "domain admins",
    "domain admin",
    "admins. do domínio",
    "admins do domínio",
    "administradores do domínio",
    "administradores de domínio",
    "administrador do domínio",
    "administrador do dominio",
)


@dataclass(frozen=True)
class AdStatus:
    joined: bool
    domain: str
    authorized: bool
    reason: str


def check_ad(user: str | None = None) -> AdStatus:
    user = user or invoking_user()
    domain = domain_from_realm(run_command(_realm_command()))
    if not domain and shutil.which("realm") is None:
        domain = domain_from_sssd(_read_sssd())
    if not domain:
        return AdStatus(
            joined=False,
            domain="",
            authorized=False,
            reason=(
                "Este computador não está em um domínio Active Directory. "
                "Use o Modo Individual."
            ),
        )
    groups = run_command(["id", "-Gn", user])
    if user_is_domain_admin(groups):
        return AdStatus(joined=True, domain=domain, authorized=True, reason="")
    return AdStatus(
        joined=True,
        domain=domain,
        authorized=False,
        reason=(
            f"O computador está no domínio {domain}, mas o usuário {user} "
            "não pertence ao grupo Administrador do domínio. "
            "Use o Modo Individual."
        ),
    )


def domain_from_realm(text: str) -> str:
    for line in text.splitlines():
        lowered = line.strip().lower()
        if lowered.startswith("domain-name:"):
            return line.split(":", 1)[1].strip()
    return ""


def domain_from_sssd(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().replace(" ", "").startswith("domains="):
            domains = stripped.split("=", 1)[1].strip()
            first = domains.split(",")[0].strip()
            if first and first.lower() not in {"nss", "pam", "sudo", "ssh"}:
                return first
    return ""


def user_is_domain_admin(groups_text: str) -> bool:
    lowered = groups_text.lower()
    return any(marker in lowered for marker in _ADMIN_GROUPS)


def _realm_command() -> list[str]:
    realm = shutil.which("realm")
    if not realm:
        return []
    return [realm, "list"]


def _read_sssd() -> str:
    try:
        with open("/etc/sssd/sssd.conf", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""
