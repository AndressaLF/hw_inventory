"""Planilha e PDF no mesmo dossiê do programa de Windows."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from hw_inventory import __version__
from hw_inventory.collect import collect_hardware, slot_is_free, slot_purpose
from hw_inventory.license_key import is_free_license
from hw_inventory.models import FormData, Hardware, InventoryResult
from hw_inventory.paths import give_to_user, invoking_user, output_dir, output_filenames

SCHEMA_VERSION = "4"
_DIAS = (
    "segunda-feira",
    "terca-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sabado",
    "domingo",
)
_GENERICOS = {
    "",
    "none",
    "null",
    "n/a",
    "na",
    "unknown",
    "not available",
    "not specified",
    "default string",
    "system product name",
    "system serial number",
    "to be filled by oem",
    "to be filled by o.e.m.",
    "0",
    "00000000",
}
_COMP_COLS = (
    ("categoria", "Categoria", 14),
    ("fabricante", "Fabricante", 18),
    ("modelo", "Modelo", 32),
    ("numero_serie", "Nº serie", 22),
    ("serie_manual", "Serie manual", 16),
    ("serie_status", "Status serie", 28),
    ("conforme_patrimonial", "Conforme?", 12),
    ("capacidade", "Capacidade", 14),
    ("posicao", "Posicao", 18),
    ("socket_ou_slot", "Socket/Slot", 14),
    ("interface", "Interface", 14),
    ("velocidade", "Velocidade", 26),
    ("tipo_tecnologia", "Tecnologia", 16),
    ("part_number", "Part number", 18),
    ("quantidade_logica", "Detalhe", 18),
    ("expansivel", "Pode expandir?", 16),
    ("detalhe_expansao", "Slots / maximo da placa", 36),
    ("notas", "Notas", 36),
    ("hostname", "Hostname", 14),
    ("patrimonio_instituicao", "Patrimonio", 14),
)
_AUDIT_COLS = (
    ("categoria", "Categoria", 14),
    ("fabricante", "Fabricante", 18),
    ("modelo", "Modelo", 32),
    ("numero_serie", "Nº serie", 22),
    ("serie_manual", "Serie manual", 16),
    ("serie_status", "Status serie", 28),
    ("conforme_patrimonial", "Conforme?", 12),
    ("capacidade", "Capacidade", 14),
    ("notas", "Acao sugerida", 42),
)
_MONITOR_COLS = (
    ("fabricante", "Fabricante", 16),
    ("modelo", "Modelo / Nome", 28),
    ("numero_serie", "Nº serie", 20),
    ("serie_manual", "Serie manual", 16),
    ("serie_status", "Status serie", 28),
    ("conforme_patrimonial", "Conforme?", 12),
    ("part_number", "Codigo produto", 16),
    ("tipo_tecnologia", "Fabricacao", 16),
    ("notas", "Notas", 28),
    ("hostname", "Hostname", 14),
    ("patrimonio_instituicao", "Patrimonio", 14),
)
_ACAO_SERIE = "Etiquetar fisicamente e preencher serie manual"
_GPU_NOTA = (
    "Serie da GPU quase nunca e exposta pelo sistema. "
    "Para patrimonio: etiquete fisicamente e registre serie manual na planilha."
)


@dataclass
class Peca:
    categoria: str
    fabricante: str = ""
    modelo: str = ""
    numero_serie: str = ""
    serie_manual: str = ""
    serie_status: str = ""
    conforme_patrimonial: str = ""
    capacidade: str = ""
    posicao: str = ""
    socket_ou_slot: str = ""
    interface: str = ""
    velocidade: str = ""
    tipo_tecnologia: str = ""
    part_number: str = ""
    quantidade_logica: str = ""
    expansivel: str = ""
    detalhe_expansao: str = ""
    notas: str = ""
    hostname: str = ""
    patrimonio_instituicao: str = ""

    def get(self, name: str) -> str:
        return str(getattr(self, name, "") or "")


def validate_form(form: FormData) -> str | None:
    if not form.responsavel.strip() or not form.local.strip():
        return "Informe o responsável e o local."
    return None


def needs_patrimonio_confirmation(form: FormData) -> bool:
    return not form.patrimonio.strip()


def run_inventory(form: FormData, mode: str, folder: Path | None = None) -> InventoryResult:
    hardware = collect_hardware()
    return write_inventory(form, hardware, mode, folder)


def write_inventory(
    form: FormData,
    hardware: Hardware,
    mode: str,
    folder: Path | None = None,
) -> InventoryResult:
    destination = folder or output_dir()
    destination.mkdir(parents=True, exist_ok=True)
    spreadsheet_name, pdf_name = output_filenames(form.patrimonio, hardware.hostname)
    spreadsheet_path = destination / spreadsheet_name
    pdf_path = destination / pdf_name
    dossier = build_dossier(form, hardware, str(destination))
    _write_xlsx(spreadsheet_path, dossier)
    _write_pdf(pdf_path, dossier)
    user = invoking_user()
    give_to_user(destination, user)
    give_to_user(spreadsheet_path, user)
    give_to_user(pdf_path, user)
    return InventoryResult(
        folder=str(destination),
        spreadsheet=spreadsheet_name,
        pdf=pdf_name,
        spreadsheet_path=str(spreadsheet_path),
        pdf_path=str(pdf_path),
    )


@dataclass
class Dossier:
    form: FormData
    hardware: Hardware
    pecas: list[Peca]
    desktop: str
    criado_em: datetime
    fingerprint: str


def build_dossier(form: FormData, hardware: Hardware, desktop: str) -> Dossier:
    pecas = build_pecas(form, hardware)
    return Dossier(
        form=form,
        hardware=hardware,
        pecas=pecas,
        desktop=desktop,
        criado_em=datetime.now().astimezone(),
        fingerprint=fingerprint_of(hardware, pecas),
    )


def build_pecas(form: FormData, hardware: Hardware) -> list[Peca]:
    patrimonio = form.patrimonio.strip()
    host = hardware.hostname
    ram_note = hardware.memory_expansion
    pode_ram = _ram_pode(hardware)
    pecas: list[Peca] = []

    pecas.append(
        Peca(
            categoria="motherboard",
            fabricante=hardware.board_vendor,
            modelo=_join_space(hardware.board_name, hardware.board_version),
            numero_serie=hardware.board_serial,
            tipo_tecnologia=_join_space(hardware.bios_vendor, hardware.bios_version),
            notas=_join_space(
                f"Chipset: {hardware.chipset}" if hardware.chipset else "",
                f"Serie BIOS: {hardware.bios_serial}" if hardware.bios_serial else "",
            ).replace("  ", " "),
            detalhe_expansao=_pode_adicionar_placa(hardware),
        )
    )
    pecas.append(
        Peca(
            categoria="cpu",
            fabricante=_cpu_vendor(hardware.cpu_vendor),
            modelo=hardware.cpu_model,
            numero_serie=hardware.cpu_serial,
            velocidade=hardware.cpu_max_mhz,
            quantidade_logica=" / ".join(
                parte
                for parte in (
                    f"{hardware.cpu_cores} nucleos" if hardware.cpu_cores else "",
                    f"{hardware.cpu_threads} threads" if hardware.cpu_threads else "",
                )
                if parte
            ),
            tipo_tecnologia=hardware.arch,
            socket_ou_slot=hardware.cpu_socket or "Nao lido",
            posicao=hardware.cpu_position or "Nao lida",
            notas=_cpu_notes(hardware),
        )
    )
    for module in hardware.modules:
        if not module.installed:
            continue
        pecas.append(
            Peca(
                categoria="ram",
                fabricante=module.manufacturer,
                modelo=module.part_number,
                numero_serie=module.serial,
                capacidade=module.size,
                posicao=module.locator,
                socket_ou_slot=module.bank if module.bank and module.bank != module.locator else "",
                interface=module.form_factor,
                velocidade=module.speed,
                tipo_tecnologia=module.mem_type,
                part_number=module.part_number,
                expansivel=pode_ram,
                detalhe_expansao=ram_note,
                notas=_ram_notes(module),
            )
        )
    for disk in hardware.disks:
        pecas.append(
            Peca(
                categoria="disk",
                fabricante=_disk_brand(disk.model) or disk.vendor,
                modelo=disk.model,
                numero_serie=disk.serial,
                capacidade=disk.size,
                posicao=disk.volumes,
                interface=disk.interface,
                velocidade=disk.link,
                tipo_tecnologia=disk.media,
                expansivel="sim" if _inteiro(hardware.sata_ports_free) else ("nao" if _inteiro(hardware.sata_ports_total) else ""),
                detalhe_expansao=f"{_controlador_sata(hardware)}. Livres: {_portas_sata_livres(hardware)}",
            )
        )
    for gpu in hardware.gpus:
        name = gpu.name
        driver = " ".join(part for part in (gpu.driver, gpu.driver_version) if part)
        notas = f"Instalacao: {_instalacao_item(gpu.instalacao)}. {_GPU_NOTA}"
        if gpu.pci_id:
            notas = f"{notas} ID tecnico: {gpu.pci_id}"
        pecas.append(
            Peca(
                categoria="gpu",
                fabricante=_brand_from_text(name),
                modelo=name,
                capacidade=gpu.vram,
                velocidade=_mode_text(gpu.mode, gpu.refresh) if gpu.refresh and "@" not in gpu.mode else gpu.mode,
                tipo_tecnologia=gpu.driver_date,
                part_number=driver,
                notas=notas,
            )
        )
    for monitor in hardware.monitors:
        notas = ""
        if monitor.native_resolution and monitor.native_resolution != monitor.resolution:
            notas = f"Resolucao nativa: {monitor.native_resolution}"
        pecas.append(
            Peca(
                categoria="monitor",
                fabricante=_brand_from_text(monitor.name),
                modelo=monitor.name,
                numero_serie=monitor.serial,
                capacidade=monitor.physical_size,
                velocidade=_mode_text(monitor.resolution, monitor.refresh),
                interface=monitor.connector,
                posicao=monitor.connector,
                tipo_tecnologia=monitor.manufacture,
                part_number=monitor.product_code,
                notas=notas,
            )
        )
    outra_placa = _outra_placa_rede(hardware)
    for index, nic in enumerate(hardware.nics):
        notas = _nic_notes(nic)
        if index == 0 and outra_placa:
            notas = "; ".join(part for part in (notas, outra_placa) if part)
        pecas.append(
            Peca(
                categoria="network",
                fabricante=_brand_from_text(nic.description),
                modelo=nic.description,
                numero_serie=nic.mac,
                posicao=nic.name,
                interface=nic.driver,
                velocidade=nic.speed,
                part_number=nic.driver,
                notas=notas,
            )
        )
    for peca in pecas:
        peca.hostname = host
        peca.patrimonio_instituicao = patrimonio
        peca.serie_status = classify_serie(peca.numero_serie, peca.serie_manual)
        peca.conforme_patrimonial = "sim" if peca.serie_status in {"ok", "manual_registrada"} else "nao"
        if peca.conforme_patrimonial == "nao" and peca.categoria != "gpu":
            if not peca.notas.strip():
                peca.notas = _ACAO_SERIE
            elif _ACAO_SERIE not in peca.notas:
                peca.notas = f"{_ACAO_SERIE}; {peca.notas}"
    return pecas


def principais(pecas: list[Peca]) -> list[Peca]:
    return [peca for peca in pecas if peca.categoria != "slot"]


def nao_conformes(pecas: list[Peca]) -> list[Peca]:
    return [peca for peca in principais(pecas) if peca.conforme_patrimonial != "sim"]


def classify_serie(serial: str, manual: str = "") -> str:
    if manual.strip():
        return "manual_registrada"
    if not serial.strip():
        return "nao_informado_pelo_firmware"
    if serial.strip().casefold() in _GENERICOS:
        return "generico_ou_invalido"
    return "ok"


def fingerprint_of(hardware: Hardware, pecas: list[Peca]) -> str:
    lines = [hardware.hostname, hardware.uuid, hardware.serial]
    for peca in pecas:
        lines.append("|".join((peca.categoria, peca.modelo, peca.numero_serie)))
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def report_title(hostname: str) -> str:
    host = hostname.strip() or "UNKNOWN_HOST"
    return f"Inventario patrimonial de hardware do {host}"


def format_created_line(moment: datetime) -> str:
    dia = _DIAS[moment.weekday()]
    return (
        f"Criado em: {dia}, {moment.strftime('%d/%m/%Y')} as {moment.strftime('%H:%M:%S')}"
        f" | App {__version__}"
    )


def _write_xlsx(path: Path, dossier: Dossier) -> None:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise RuntimeError(
            "Dependência ausente: openpyxl. Instale com python3 -m pip install -r requirements.txt"
        ) from exc

    header_fill = PatternFill("solid", fgColor="1F4E79")
    section_fill = PatternFill("solid", fgColor="2E75B6")
    alert_fill = PatternFill("solid", fgColor="FFCDD2")
    warn_fill = PatternFill("solid", fgColor="FFF3CD")
    ok_fill = PatternFill("solid", fgColor="C8E6C9")
    zebra_fill = PatternFill("solid", fgColor="F5F5F5")
    label_fill = PatternFill("solid", fgColor="E7E6E6")
    thin = Border(
        left=Side(style="thin", color="B0B0B0"),
        right=Side(style="thin", color="B0B0B0"),
        top=Side(style="thin", color="B0B0B0"),
        bottom=Side(style="thin", color="B0B0B0"),
    )
    font_header = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
    font_section = Font(bold=True, color="FFFFFF", name="Calibri", size=12)
    font_label = Font(bold=True, name="Calibri", size=11)
    font_value = Font(name="Calibri", size=11)
    font_title = Font(bold=True, name="Calibri", size=16, color="1F4E79")
    font_created = Font(name="Calibri", size=10, italic=True, color="666666")
    wrap = Alignment(vertical="center", wrap_text=True)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    workbook = Workbook()
    capa = workbook.active
    capa.title = "Capa"
    maquina = workbook.create_sheet("Maquina")
    _build_capa(capa, dossier, font_title, font_created, font_section, font_label, font_value, section_fill, label_fill, warn_fill, thin, wrap, center)
    _build_maquina(maquina, dossier, font_title, font_created, font_section, font_label, font_value, section_fill, label_fill, warn_fill, alert_fill, thin, wrap)
    _build_table(workbook.create_sheet("Componentes"), principais(dossier.pecas), _COMP_COLS, header_fill, font_header, font_value, alert_fill, ok_fill, zebra_fill, thin, center, get_column_letter)
    _build_table(workbook.create_sheet("Monitores"), [p for p in dossier.pecas if p.categoria == "monitor"], _MONITOR_COLS, header_fill, font_header, font_value, alert_fill, ok_fill, zebra_fill, thin, center, get_column_letter)
    _build_table(workbook.create_sheet("Auditoria"), nao_conformes(dossier.pecas), _AUDIT_COLS, header_fill, font_header, font_value, alert_fill, ok_fill, zebra_fill, thin, center, get_column_letter)
    _build_expansao(workbook.create_sheet("Expansao"), dossier, font_section, font_label, font_value, section_fill, label_fill, warn_fill, thin, wrap)
    workbook.properties.title = report_title(dossier.hardware.hostname)
    workbook.properties.creator = f"hw-inventory {__version__}"
    workbook.save(path)


def _build_capa(sheet, dossier: Dossier, font_title, font_created, font_section, font_label, font_value, section_fill, label_fill, warn_fill, thin, wrap, center) -> None:
    sheet.merge_cells("A1:B1")
    sheet["A1"] = report_title(dossier.hardware.hostname)
    sheet["A1"].font = font_title
    sheet["A1"].alignment = wrap
    sheet.merge_cells("A2:B2")
    sheet["A2"] = format_created_line(dossier.criado_em)
    sheet["A2"].font = font_created
    pecas = principais(dossier.pecas)
    pendencias = nao_conformes(dossier.pecas)
    rows = [
        ("Patrimonio", dossier.form.patrimonio.strip() or "(sem tombamento)", False),
        ("Responsavel", dossier.form.responsavel, False),
        ("Local", dossier.form.local, False),
        ("Status do bem", dossier.form.status, False),
        ("Total de componentes", str(len(pecas)), False),
        ("Discos", str(sum(1 for peca in pecas if peca.categoria == "disk")), False),
        ("Monitores", str(sum(1 for peca in pecas if peca.categoria == "monitor")), False),
        ("Pendencias (sem serie)", str(len(pendencias)), bool(pendencias)),
        ("Licenca ligada a placa-mae?", _vinculo_placa(dossier.hardware), False),
        ("Chave manual informada?", "sim" if dossier.form.chave_licenca.strip() else "nao", False),
        ("Chave do Linux?", "sim" if dossier.hardware.license_key.strip() else "nao", False),
        ("Chave completa", _chave_efetiva(dossier.form, dossier.hardware) or "(nao encontrada)", bool(_chave_efetiva(dossier.form, dossier.hardware))),
        ("Fingerprint", dossier.fingerprint, False),
    ]
    _section(sheet, 4, "RESUMO RAPIDO", font_section, section_fill, center)
    row = 5
    for label, value, warn in rows:
        _kv(sheet, row, label, value, font_label, font_value, label_fill, warn_fill if warn else None, thin, wrap)
        row += 1
    row += 1
    _section(sheet, row, "ALERTAS", font_section, section_fill, center)
    row += 1
    alerts = _alertas(dossier, pendencias)
    if not alerts:
        _kv(sheet, row, "Situacao", "Sem alertas criticos nesta coleta", font_label, font_value, label_fill, None, thin, wrap)
        row += 1
    else:
        for label, value in alerts:
            _kv(sheet, row, label, value, font_label, font_value, label_fill, warn_fill, thin, wrap)
            row += 1
    row += 1
    sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    sheet.cell(row, 1, "Abas: Maquina | Componentes | Monitores | Auditoria | Expansao")
    sheet.cell(row, 1).font = font_created
    sheet.column_dimensions["A"].width = 36
    sheet.column_dimensions["B"].width = 88
    sheet.row_dimensions[1].height = 24


def _build_maquina(sheet, dossier: Dossier, font_title, font_created, font_section, font_label, font_value, section_fill, label_fill, warn_fill, alert_fill, thin, wrap) -> None:
    hardware = dossier.hardware
    form = dossier.form
    sheet.merge_cells("A1:B1")
    sheet["A1"] = report_title(hardware.hostname)
    sheet["A1"].font = font_title
    sheet["A1"].alignment = wrap
    sheet.merge_cells("A2:B2")
    sheet["A2"] = format_created_line(dossier.criado_em)
    sheet["A2"].font = font_created
    garantia_meses, garantia_fim = _garantia(form.garantia)
    blocks = [
        (
            "1. PATRIMONIO",
            [
                ("Instituicao", form.instituicao),
                ("Nº patrimonio", form.patrimonio.strip() or "(sem tombamento)"),
                ("Status", form.status),
                ("Responsavel", form.responsavel),
                ("Local fisico", form.local),
                ("Setor / Lab", form.setor),
                ("Data compra", form.compra),
                ("Garantia (meses)", garantia_meses),
                ("Garantia (fim)", garantia_fim),
                ("NF / Processo", form.nota_fiscal),
                ("Data conferencia", hardware.collected_at),
                ("Observacoes", form.observacoes),
            ],
        ),
        (
            "2. IDENTIDADE",
            [
                ("Hostname", hardware.hostname),
                ("Fabricante", hardware.manufacturer),
                ("Modelo", hardware.product),
                ("Tipo de chassi", hardware.chassis_type),
                ("Serie do gabinete", hardware.chassis_serial),
                ("UUID sistema", hardware.uuid),
                ("Serie sistema", hardware.serial),
                ("BIOS fabricante", hardware.bios_vendor),
                ("BIOS versao", hardware.bios_version),
                ("BIOS data", hardware.bios_date),
                ("Dominio / Grupo", hardware.domain_group or "Nao ingressado"),
                ("Fingerprint", dossier.fingerprint),
            ],
        ),
        (
            "3. SISTEMA OPERACIONAL E LICENCA",
            _licenca_rows(form, hardware),
        ),
        (
            "4. PLACA-MAE",
            [*_campos_placa(hardware), ("O que da para melhorar", _melhoria_placa(hardware))],
        ),
        (
            "5. PROCESSADOR",
            [*_campos_cpu(hardware), ("O que da para melhorar", _melhoria_cpu(hardware))],
        ),
        (
            "6. MEMORIA RAM",
            [*_campos_ram(hardware), ("O que da para melhorar", _melhoria_ram(hardware))],
        ),
        (
            "7. ARMAZENAMENTO",
            [*_campos_disco(hardware), ("O que da para melhorar", _melhoria_disco(hardware))],
        ),
        (
            "8. PLACA DE VIDEO",
            [*_campos_video(hardware), ("O que da para melhorar", _melhoria_video(hardware))],
        ),
        (
            "9. PERIFERICOS",
            [*_radio_rows(hardware), ("O que da para melhorar", _melhoria_perifericos(hardware))],
        ),
        (
            "10. METADADOS DA COLETA",
            [
                ("Coletado em", hardware.collected_at),
                ("Versao do app", __version__),
                ("Schema", SCHEMA_VERSION),
                ("Desktop", dossier.desktop),
            ],
        ),
    ]
    row = 4
    for title, pairs in blocks:
        _section(sheet, row, title, font_section, section_fill, wrap)
        row += 1
        for label, value in pairs:
            fill = alert_fill if label == "RISCO (chave completa)" else None
            amarelo = label == "O que da para melhorar" or label.startswith("ALERTA")
            _kv(sheet, row, label, value, font_label, font_value, label_fill, fill or (warn_fill if amarelo else None), thin, wrap)
            if amarelo:
                sheet.row_dimensions[row].height = 48
            row += 1
        row += 1
    sheet.column_dimensions["A"].width = 42
    sheet.column_dimensions["B"].width = 88
    sheet.row_dimensions[1].height = 24


def _licenca_rows(form: FormData, hardware: Hardware) -> list[tuple[str, str]]:
    manual = form.chave_licenca.strip()
    linux_key = hardware.license_key.strip()
    livre = is_free_license(linux_key)
    efetiva = _chave_efetiva(form, hardware)
    parcial = hardware.license_key_partial.strip() or (linux_key if livre else (efetiva[-5:] if efetiva else ""))
    if livre:
        status = "Software livre"
        tipo = "Software livre"
        canal = "distribuicao"
    elif linux_key:
        status = "Assinatura encontrada no sistema"
        tipo = "Assinatura"
        canal = "sistema"
    else:
        status = "Nao aplicavel"
        tipo = "Nao aplicavel"
        canal = ""
    rows = [
        ("SO (nome)", hardware.os_name),
        ("Edicao", hardware.os_edition),
        ("Versao", hardware.os_version),
        ("Build", hardware.kernel),
        ("Arquitetura", hardware.arch),
        ("Status da licenca", status),
        ("Tipo da licenca", tipo),
        ("Canal", canal),
        ("Ligada a placa-mae?", _vinculo_placa(hardware)),
        ("Chave parcial (auto)", parcial or "(nao encontrada)"),
        ("Chave do Linux", linux_key or "(nao encontrada)"),
        ("Chave completa (manual)", manual or "(nao informada)"),
    ]
    if efetiva and not is_free_license(efetiva):
        rows.append(
            (
                "RISCO (chave completa)",
                "Relatorio/planilha contem chave completa. Arquive com acesso restrito; nao compartilhe em canais abertos.",
            )
        )
    rows.append(
        (
            "Explicacao",
            "A chave do Linux entra automaticamente, lida da licenca da distribuicao instalada. A chave digitada no formulario tambem entra sempre.",
        )
    )
    return rows


def _instalacao_item(instalacao: str) -> str:
    if instalacao == "sim":
        return "Onboard, no processador"
    if instalacao == "nao":
        return "Dedicada"
    return "Indeterminada"


def _slots_livres(hardware: Hardware):
    return [slot for slot in hardware.slots if slot_is_free(slot.usage)]


def _slots_vazios_para(hardware: Hardware) -> str:
    livres = _slots_livres(hardware)
    textos = []
    ram_livres = _ram_livres(hardware)
    if ram_livres:
        textos.append(f"{ram_livres} slot(s) para memoria RAM")
    for slot in livres:
        uso = slot_purpose(slot.designation, slot.slot_type, slot.width)
        nome = slot.designation or slot.slot_type or "slot"
        detalhe = " / ".join(part for part in (slot.slot_type, slot.width) if part)
        textos.append(f"{nome}: {uso}" + (f" ({detalhe})" if detalhe else ""))
    if textos:
        return "; ".join(textos)
    if not hardware.slots:
        return "Sem lista de slots PCI. Com sudo, o dmidecode informa para que serve cada um."
    return "Nenhum slot PCI livre listado."


def _ram_livres(hardware: Hardware) -> int | None:
    try:
        total = int(hardware.memory_slots_total or "0")
        used = int(hardware.memory_slots_used or "0")
    except ValueError:
        return None
    if total <= 0:
        return None
    return max(total - used, 0)


def _slots_ram_texto(hardware: Hardware) -> str:
    livres = _ram_livres(hardware)
    if livres is None:
        return "Nao lidos"
    return f"{livres} livres de {hardware.memory_slots_total}"


def _slots_pci_texto(hardware: Hardware) -> str:
    if not hardware.slots:
        return "Nao lidos"
    livres = _slots_livres(hardware)
    if not livres:
        return f"Nenhum livre de {len(hardware.slots)}"
    return _slots_vazios_para(hardware)


def _slots_placa_texto(hardware: Hardware) -> str:
    return f"RAM: {_slots_ram_texto(hardware)}. PCI: {_slots_pci_texto(hardware)}."


def _expansao_video(hardware: Hardware) -> tuple[str, str]:
    if not hardware.slots:
        return (
            "Indeterminado. Os slots PCI nao foram lidos.",
            "No Linux o dmidecode so informa esses slots com sudo.",
        )
    livres = [
        slot
        for slot in _slots_livres(hardware)
        if "video" in slot_purpose(slot.designation, slot.slot_type, slot.width)
    ]
    if livres:
        nomes = ", ".join(slot.designation or slot.slot_type or "slot" for slot in livres)
        return (f"Sim. Slot livre: {nomes}.", "Serve para uma placa de video dedicada.")
    return ("Nao ha slot livre de video listado.", "A lista de slots PCI foi lida e nao ha x16 livre.")


_NAO_LIDO = "Nao lido. Execute com sudo."


def _pode_adicionar_placa(hardware: Hardware) -> str:
    partes = []
    livres = _ram_livres(hardware)
    if livres is None:
        partes.append("RAM: slots vazios nao lidos")
    elif livres:
        partes.append(f"RAM: {livres} slot(s) vazio(s), para modulo do mesmo tipo")
    else:
        partes.append("RAM: nenhum slot vazio; so troca dos modulos por maiores")
    if not hardware.slots:
        partes.append("PCI: slots vazios nao lidos. Servem para video, rede ou outra placa")
    else:
        livres_pci = _slots_livres(hardware)
        if not livres_pci:
            partes.append(f"PCI: 0 vazios de {len(hardware.slots)}")
        else:
            partes.append(f"PCI: {len(livres_pci)} vazio(s) de {len(hardware.slots)}. {_slots_vazios_para(hardware)}")
    return ". ".join(partes) + "."


def _campos_placa(hardware: Hardware) -> list[tuple[str, str]]:
    livres = _ram_livres(hardware)
    return [
        ("Chipset", hardware.chipset or "Nao identificado"),
        ("Slots de RAM totais", hardware.memory_slots_total or _NAO_LIDO),
        ("Slots de RAM em uso", hardware.memory_slots_used or _NAO_LIDO),
        ("Slots de RAM vazios", str(livres) if livres is not None else _NAO_LIDO),
        ("Slots PCI totais", str(len(hardware.slots)) if hardware.slots else _NAO_LIDO),
        ("Slots PCI vazios", str(len(_slots_livres(hardware))) if hardware.slots else _NAO_LIDO),
        ("O que ainda pode ser adicionado", _pode_adicionar_placa(hardware)),
    ]


def _melhoria_placa(hardware: Hardware) -> str:
    chip = hardware.chipset or "Chipset nao identificado"
    return f"{chip}. {_pode_adicionar_placa(hardware)}"


def _campos_cpu(hardware: Hardware) -> list[tuple[str, str]]:
    soquete = hardware.cpu_socket or _NAO_LIDO
    if hardware.cpu_position:
        posicao = hardware.cpu_position
    elif hardware.cpu_socket:
        posicao = "Unico processador da placa"
    else:
        posicao = _NAO_LIDO
    campos = [
        ("Nome", hardware.cpu_model or "Nao identificado"),
        ("Posicao", posicao),
        ("Soquete", soquete),
        ("Nucleos", hardware.cpu_cores or "Nao lido"),
        ("Threads", hardware.cpu_threads or "Nao lido"),
        ("Arquitetura", hardware.arch or "Nao lida"),
        ("Velocidade maxima", hardware.cpu_max_mhz or "Nao lida"),
        ("Clock atual", hardware.cpu_current_mhz or "Nao lido"),
        ("Cache L2", hardware.cpu_l2 or "Nao lido"),
        ("Cache L3", hardware.cpu_l3 or "Nao lido"),
        ("Virtualizacao", hardware.cpu_virtualization or "Nao lida"),
        ("Familia", hardware.cpu_family),
        ("Stepping", hardware.cpu_stepping),
        ("ProcessorId", hardware.cpu_id),
        ("Endereco", hardware.cpu_address),
        ("Modelo", hardware.cpu_model_number),
        ("Serie", hardware.cpu_serial),
    ]
    return [(label, value) for label, value in campos if value]


def _melhoria_cpu(hardware: Hardware) -> str:
    nome = hardware.cpu_model or "Processador nao identificado"
    nucleos = hardware.cpu_cores or "?"
    threads = hardware.cpu_threads or "?"
    clock = hardware.cpu_max_mhz or "clock maximo nao lido"
    soquete = hardware.cpu_socket or "soquete nao lido"
    return f"{nome}, {nucleos} nucleos, {threads} threads, ate {clock}. Troca: mesmo soquete ({soquete})."


def _specs_ram_troca(hardware: Hardware) -> tuple[str, str, str]:
    instalados = [module for module in hardware.modules if module.installed]
    tipos = sorted({module.mem_type for module in instalados if module.mem_type})
    velocidades = sorted({module.speed for module in instalados if module.speed})
    formatos = sorted({module.form_factor for module in instalados if module.form_factor})
    return (
        ", ".join(tipos) or _NAO_LIDO,
        ", ".join(velocidades) or _NAO_LIDO,
        ", ".join(formatos) or _NAO_LIDO,
    )


def _campos_ram(hardware: Hardware) -> list[tuple[str, str]]:
    livres = _ram_livres(hardware)
    tipo, velocidade, formato = _specs_ram_troca(hardware)
    if livres is None:
        pode = "Nao lido. Falta a lista de soquetes."
    elif livres:
        pode = f"Sim. {livres} soquete(s) vazio(s)."
    else:
        pode = "Nao. Soquetes cheios. So troca por modulos maiores."
    return [
        ("Memoria total", hardware.memory_total or "Nao lida"),
        ("Memoria maxima da placa", hardware.memory_max or _NAO_LIDO),
        ("Soquetes totais", hardware.memory_slots_total or _NAO_LIDO),
        ("Soquetes em uso", hardware.memory_slots_used or _NAO_LIDO),
        ("Soquetes vazios", str(livres) if livres is not None else _NAO_LIDO),
        ("Pode melhorar", pode),
        ("Tipo para troca", tipo),
        ("Velocidade para troca", velocidade),
        ("Formato para troca", formato),
    ]


def _melhoria_ram(hardware: Hardware) -> str:
    visivel = hardware.memory_total or "quantidade nao lida"
    tipo, velocidade, formato = _specs_ram_troca(hardware)
    livres = _ram_livres(hardware)
    if livres is None:
        vagas = "soquetes vazios nao lidos"
    elif livres:
        vagas = f"{livres} soquete(s) vazio(s)"
    else:
        vagas = "soquetes cheios, so troca por modulos maiores"
    return f"{visivel}. Tipo {tipo}. Velocidade {velocidade}. Formato {formato}. {vagas}."


def _contagem_discos(hardware: Hardware) -> tuple[int, int]:
    ssd = 0
    hdd = 0
    for disk in hardware.disks:
        if disk.media == "HDD":
            hdd += 1
        else:
            ssd += 1
    return ssd, hdd


def _limite_discos(hardware: Hardware) -> str:
    livres = _inteiro(hardware.sata_ports_free)
    total = _inteiro(hardware.sata_ports_total)
    extra = " Slot M.2 adicional nao lido." if not hardware.slots else ""
    if livres:
        return f"Ate {livres} no total, um por porta SATA. Cada porta aceita 1 HDD ou 1 SSD, nao os dois.{extra}"
    if total:
        return f"Nenhuma porta SATA livre.{extra}"
    return _NAO_LIDO + extra


def _campos_disco(hardware: Hardware) -> list[tuple[str, str]]:
    ssd, hdd = _contagem_discos(hardware)
    livres = _inteiro(hardware.sata_ports_free)
    total = _inteiro(hardware.sata_ports_total)
    capacidade = "; ".join(
        " ".join(parte for parte in (disk.media, disk.size, disk.model) if parte) for disk in hardware.disks
    ) or "Nenhum disco"
    ainda = _limite_discos(hardware)
    return [
        ("SSD instalados", str(ssd)),
        ("HDD instalados", str(hdd)),
        ("Capacidade instalada", capacidade),
        ("Velocidade do SSD", hardware.ssd_speed or "Nao identificada"),
        ("Controlador SATA", _controlador_sata(hardware)),
        ("Portas SATA totais", str(total) if total else _NAO_LIDO),
        ("Portas SATA livres", str(livres) if total else _NAO_LIDO),
        ("HDD que ainda cabem", ainda),
        ("SSD que ainda cabem", ainda),
        ("Espaco em disco", hardware.disk_space or "Nao lido"),
        (
            "Capacidade maxima",
            "O firmware nao publica um teto em GB. O limite pratico e 1 disco por porta SATA livre, "
            f"alem dos {ssd + hdd} disco(s) ja instalado(s).",
        ),
    ]


def _melhoria_disco(hardware: Hardware) -> str:
    ssd, hdd = _contagem_discos(hardware)
    livres = _inteiro(hardware.sata_ports_free)
    velocidade = hardware.ssd_speed or "velocidade nao lida"
    espaco = hardware.disk_space or "espaco nao lido"
    return (
        f"{ssd} SSD e {hdd} HDD. Velocidade {velocidade}. {espaco}. "
        f"Ainda cabem ate {livres} disco(s) SATA, HDD ou SSD. Teto em GB nao publicado pelo firmware."
    )


def _video_resolucao_taxa(gpu) -> tuple[str, str]:
    modo = gpu.mode or ""
    taxa = gpu.refresh or ""
    if " @ " in modo:
        resolucao, _, extra = modo.partition(" @ ")
        return resolucao, taxa or extra
    return modo, taxa


def _campos_video(hardware: Hardware) -> list[tuple[str, str]]:
    if not hardware.gpus:
        return [("Onboard", "Nao ha placa de video"), ("Nome", "Nenhuma")]
    linhas: list[tuple[str, str]] = []
    for gpu in hardware.gpus:
        resolucao, taxa = _video_resolucao_taxa(gpu)
        linhas.extend(
            [
                ("Onboard", {"sim": "Sim", "nao": "Nao"}.get(gpu.instalacao, "Indeterminado")),
                ("Nome", gpu.name or "Nao identificado"),
                ("Fabricante", gpu.vendor or "Nao identificado"),
                ("VRAM", gpu.vram or "Nao lida"),
                ("Resolucao", resolucao or "Nao lida"),
                ("Taxa", taxa or "Nao lida"),
                ("Driver", gpu.driver or "Nao identificado"),
                ("Versao do driver", gpu.driver_version or "Nao publicada pelo modulo"),
                ("Data do driver", gpu.driver_date or "Nao lida"),
                ("PCI", gpu.pci_id or "Nao lido"),
                ("Enlace PCI", gpu.bus or "Nao lido"),
            ]
        )
    return linhas


def _melhoria_video(hardware: Hardware) -> str:
    if not hardware.gpus:
        return "Nao ha placa de video. Dedicada depende de slot PCI Express x16."
    gpu = hardware.gpus[0]
    veredito, detalhe = _expansao_video(hardware)
    resolucao, taxa = _video_resolucao_taxa(gpu)
    modo = f"{resolucao} @ {taxa}" if resolucao and taxa else resolucao or taxa
    partes = [
        f"Onboard: {_campos_video(hardware)[0][1]}",
        gpu.name,
        gpu.vram,
        modo,
        gpu.driver,
    ]
    return f"{', '.join(parte for parte in partes if parte)}. {veredito} {detalhe}"


def _melhoria_monitor(hardware: Hardware) -> str:
    if not hardware.monitors:
        return "Nenhum monitor detectado. Um monitor usa uma saida HDMI ou DisplayPort da placa."
    ligados = []
    for monitor in hardware.monitors:
        ligados.append(", ".join(parte for parte in (monitor.name, monitor.connector, monitor.resolution) if parte))
    return f"{'; '.join(ligados)}. Outro monitor usa uma saida de video livre na placa."


def _melhoria_rede(hardware: Hardware) -> str:
    if not hardware.nics:
        return "Nao ha placa de rede. Cabe adaptador USB ou placa PCI, se houver slot."
    atuais = []
    for nic in hardware.nics:
        atuais.append(", ".join(parte for parte in (nic.adapter_type or "Rede", nic.speed, nic.description) if parte))
    return f"{' | '.join(atuais)}. {_outra_placa_rede(hardware)}"


def _melhoria_perifericos(hardware: Hardware) -> str:
    wifi = (
        "ja ha Wi-Fi"
        if hardware.wifi_adapter not in {"", "Nao"}
        else "nao ha Wi-Fi; hotspot exige adaptador USB com modo AP"
    )
    bluetooth = (
        "ja ha Bluetooth"
        if hardware.bluetooth not in {"", "Nao"}
        else "nao ha Bluetooth; cabe adaptador USB"
    )
    audio = hardware.saidas_audio or "saidas de audio nao identificadas"
    camera = "ha camera integrada" if hardware.camera_integrada == "Sim" else "nao ha camera integrada"
    return f"{wifi}. {bluetooth}. Audio: {audio}. {camera}."


def _outra_placa_rede(hardware: Hardware) -> str:
    livres = [
        slot
        for slot in _slots_livres(hardware)
        if "pci" in slot_purpose(slot.designation, slot.slot_type, slot.width).lower()
    ]
    if livres:
        nomes = ", ".join(slot.designation or slot.slot_type for slot in livres)
        return f"Outra placa: slot PCI livre ({nomes}); tambem cabe adaptador USB."
    if not hardware.slots:
        return "Outra placa interna: slots PCI nao lidos. Cabe adaptador USB."
    return "Outra placa interna: sem slot PCI livre. Cabe adaptador USB."


def _inteiro(value: str) -> int:
    try:
        return int(value or "0")
    except ValueError:
        return 0


def _controlador_sata(hardware: Hardware) -> str:
    total = _inteiro(hardware.sata_ports_total)
    if total <= 0:
        return "Nenhum"
    velocidade = hardware.sata_speed or "SATA"
    return f"SATA da placa, {velocidade}, {total} portas"


def _portas_sata_livres(hardware: Hardware) -> str:
    free = _inteiro(hardware.sata_ports_free)
    total = _inteiro(hardware.sata_ports_total)
    if total <= 0:
        texto = "Nenhuma"
    elif free > 0:
        texto = f"{free} de {total}. Cada porta aceita 1 SSD ou 1 HDD."
    else:
        texto = f"0 de {total}. As portas SATA estao ocupadas."
    if not hardware.slots:
        texto += " Slot M.2 adicional nao lido."
    return texto


def _suporta_adaptador_wifi(hardware: Hardware) -> str:
    if hardware.wifi_adapter not in {"", "Nao"}:
        return "Sim. Ja ha adaptador."
    livres = [
        slot
        for slot in _slots_livres(hardware)
        if "pci" in slot_purpose(slot.designation, slot.slot_type, slot.width).lower()
    ]
    if livres:
        return "Sim, por USB ou slot PCI livre"
    return "Sim, por USB"


def _suporta_adaptador_bluetooth(hardware: Hardware) -> str:
    if hardware.bluetooth not in {"", "Nao"}:
        return "Sim. Ja ha adaptador."
    return "Sim, por USB"


def _precisa_wifi_hotspot(hardware: Hardware) -> str:
    if hardware.hotspot == "Sim":
        return "Nao"
    if hardware.hotspot == "Indeterminado":
        return "Indeterminado"
    return "Sim"


def _hotspot_objetivo(hardware: Hardware) -> str:
    if hardware.hotspot == "Sim":
        return "Sim. O Wi-Fi atual aceita modo ponto de acesso."
    if hardware.hotspot == "Indeterminado":
        return "Indeterminado. Falta o comando iw para confirmar o modo AP."
    if hardware.wifi_adapter in {"", "Nao"}:
        return "Nao. Exige adaptador Wi-Fi com modo AP. A internet entra por outro enlace, em geral o cabo."
    return hardware.hotspot_detail or "Nao. O Wi-Fi atual nao oferece modo AP."


def _radio_rows(hardware: Hardware) -> list[tuple[str, str]]:
    wifi = hardware.wifi_adapter or "Nao"
    bluetooth = hardware.bluetooth or "Nao"
    return [
        ("Wi-Fi", "Nao ha" if wifi == "Nao" else wifi),
        ("Adaptador Wi-Fi", _suporta_adaptador_wifi(hardware)),
        ("Hotspot", _hotspot_objetivo(hardware)),
        ("Bluetooth", "Nao ha" if bluetooth == "Nao" else bluetooth),
        ("Adaptador Bluetooth", _suporta_adaptador_bluetooth(hardware)),
        ("Camera integrada", hardware.camera_integrada or "Nao"),
        ("Saidas de audio", hardware.saidas_audio or "Nao identificado"),
    ]


def _chave_efetiva(form: FormData, hardware: Hardware) -> str:
    return form.chave_licenca.strip() or hardware.license_key.strip()


def _vinculo_placa(hardware: Hardware) -> str:
    key = hardware.license_key.strip()
    if not key or is_free_license(key):
        return "Nao"
    return "Sim (assinatura desta maquina)"


def _build_table(sheet, pecas: list[Peca], columns, header_fill, font_header, font_value, alert_fill, ok_fill, zebra_fill, thin, center, get_column_letter) -> None:
    headers = [label for _key, label, _width in columns]
    for index, header in enumerate(headers, start=1):
        cell = sheet.cell(1, index, header)
        cell.fill = header_fill
        cell.font = font_header
        cell.alignment = center
        cell.border = thin
    sheet.row_dimensions[1].height = 22
    for row_index, peca in enumerate(pecas, start=2):
        if peca.conforme_patrimonial == "nao":
            fill = alert_fill
        elif peca.conforme_patrimonial == "sim":
            fill = ok_fill
        elif row_index % 2 == 0:
            fill = zebra_fill
        else:
            fill = None
        for col_index, (key, _label, _width) in enumerate(columns, start=1):
            cell = sheet.cell(row_index, col_index, peca.get(key))
            cell.font = font_value
            cell.alignment = center
            cell.border = thin
            cell.number_format = "@"
            if fill is not None:
                cell.fill = fill
    for index, (_key, _label, width) in enumerate(columns, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    last_row = max(sheet.max_row, 1)
    last_col = get_column_letter(len(columns))
    sheet.auto_filter.ref = f"A1:{last_col}{last_row}"
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:{last_col}{max(last_row, 2)}"


def _build_expansao(sheet, dossier: Dossier, font_section, font_label, font_value, section_fill, label_fill, warn_fill, thin, wrap) -> None:
    hardware = dossier.hardware
    sheet.merge_cells("A1:B1")
    sheet["A1"] = "O QUE AINDA DA PARA EXPANDIR?"
    sheet["A1"].font = font_section
    sheet["A1"].fill = section_fill
    sheet["A1"].alignment = wrap
    verdict, detalhe = _ram_text(hardware)
    video_veredito, video_detalhe = _expansao_video(hardware)
    rows = [
        ("1) MEMORIA RAM", ""),
        ("PODE EXPANDIR", verdict),
        ("Detalhe", detalhe),
        ("O que da para melhorar", _melhoria_ram(hardware)),
        ("2) PLACA DE VIDEO", ""),
        ("PODE EXPANDIR", video_veredito),
        ("Detalhe", video_detalhe),
        ("O que da para melhorar", _melhoria_video(hardware)),
        ("3) SSD E HDD", ""),
        ("Velocidade do SSD", hardware.ssd_speed or "Nao identificada"),
        ("Controlador SATA", _controlador_sata(hardware)),
        ("Portas SATA livres", _portas_sata_livres(hardware)),
        ("Espaco em disco", hardware.disk_space),
        ("O que da para melhorar", _melhoria_disco(hardware)),
        ("4) PROCESSADOR", ""),
        ("O que da para melhorar", _melhoria_cpu(hardware)),
        ("5) REDE E PERIFERICOS", ""),
        ("Rede", _melhoria_rede(hardware)),
        ("Perifericos", _melhoria_perifericos(hardware)),
    ]
    if hardware.slots:
        rows.append(("6) SLOTS PCI", ""))
        for slot in hardware.slots:
            detail = " / ".join(part for part in (slot.slot_type, slot.width, slot.usage) if part)
            rows.append((slot.designation, detail or "—"))
    for index, (label, value) in enumerate(rows, start=3):
        if value == "" and label[:1].isdigit():
            _section(sheet, index, label, font_section, section_fill, wrap)
            continue
        warn = label == "PODE EXPANDIR"
        _kv(sheet, index, label, value, font_label, font_value, label_fill, warn_fill if warn else None, thin, wrap)
    sheet.column_dimensions["A"].width = 40
    sheet.column_dimensions["B"].width = 88


def _section(sheet, row: int, title: str, font, fill, alignment) -> None:
    sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    cell = sheet.cell(row, 1, title)
    cell.font = font
    cell.fill = fill
    cell.alignment = alignment
    sheet.row_dimensions[row].height = 20


def _kv(sheet, row: int, label: str, value: str, font_label, font_value, label_fill, value_fill, thin, wrap) -> None:
    left = sheet.cell(row, 1, label)
    left.font = font_label
    left.fill = label_fill
    left.alignment = wrap
    left.border = thin
    right = sheet.cell(row, 2, value or "")
    right.font = font_value
    right.alignment = wrap
    right.border = thin
    right.number_format = "@"
    if value_fill is not None:
        right.fill = value_fill
    sheet.row_dimensions[row].height = 18


def _alertas(dossier: Dossier, pendencias: list[Peca]) -> list[tuple[str, str]]:
    alerts: list[tuple[str, str]] = []
    if not dossier.form.patrimonio.strip():
        alerts.append(("Tombamento", "FALTA numero de patrimonio"))
    if pendencias:
        alerts.append(("Series", f"{len(pendencias)} item(ns) sem serie efetiva — ver aba Auditoria"))
    return alerts


def _ram_text(hardware: Hardware) -> tuple[str, str]:
    tipo = next((module.mem_type for module in hardware.modules if module.installed and module.mem_type), "")
    try:
        total = int(hardware.memory_slots_total or "0")
        used = int(hardware.memory_slots_used or "0")
    except ValueError:
        total, used = 0, 0
    detail_parts = []
    if total:
        detail_parts.append(f"{used} de {total} slots em uso")
    if tipo:
        detail_parts.append(f"Tipo {tipo}")
    if hardware.memory_max:
        detail_parts.append(f"Maximo da placa: {hardware.memory_max}")
    detalhe = " | ".join(detail_parts) or hardware.memory_expansion
    if total <= 0:
        return "INDETERMINADO", detalhe or "Pode expandir: informacao incompleta no firmware"
    free = max(total - used, 0)
    if free:
        return f"SIM — ainda ha {free} slot(s) livre(s)", detalhe
    return "NAO — slots cheios (so trocando modulos)", detalhe


def _ram_pode(hardware: Hardware) -> str:
    verdict, _detail = _ram_text(hardware)
    if verdict.startswith("SIM"):
        return "sim"
    if verdict.startswith("NAO"):
        return "nao"
    return ""


def _write_pdf(path: Path, dossier: Dossier) -> None:
    try:
        from fpdf import FPDF
    except ImportError as exc:
        raise RuntimeError(
            "Dependência ausente: fpdf2. Instale com python3 -m pip install -r requirements.txt"
        ) from exc

    hardware = dossier.hardware
    form = dossier.form
    pendencias = nao_conformes(dossier.pecas)

    class Report(FPDF):
        def footer(self) -> None:
            self.set_y(-12)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(90, 90, 90)
            self.cell(
                0,
                8,
                _pdf_safe(f"Pagina {self.page_no()} | Dossie patrimonial local | sem telemetria"),
                align="C",
            )

    pdf = Report(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(31, 78, 121)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 7, _pdf_safe(report_title(hardware.hostname)), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(80, 80, 80)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 5, _pdf_safe(format_created_line(dossier.criado_em)), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_text_color(20, 20, 20)

    if not form.patrimonio.strip():
        _pdf_alert(pdf, "ALERTA: sem numero de tombamento — risco patrimonial.")

    _pdf_heading(pdf, "1. Dados patrimoniais")
    garantia_meses, garantia_fim = _garantia(form.garantia)
    garantia = " / ".join(part for part in (f"{garantia_meses} meses" if garantia_meses else "", f"ate {garantia_fim}" if garantia_fim else "") if part)
    for label, value in (
        ("Instituicao", form.instituicao),
        ("Patrimonio", form.patrimonio.strip()),
        ("Status", form.status),
        ("Responsavel", form.responsavel),
        ("Local", form.local),
        ("Setor/Lab", form.setor),
        ("Compra", form.compra),
        ("Garantia", garantia),
        ("NF/Processo", form.nota_fiscal),
        ("Observacoes", form.observacoes),
    ):
        _pdf_kv(pdf, label, value)

    _pdf_heading(pdf, "2. Identidade da maquina")
    for label, value in (
        ("Hostname", hardware.hostname),
        ("Fabricante", hardware.manufacturer),
        ("Modelo", hardware.product),
        ("Chassi", hardware.chassis_type),
        ("Serie do gabinete", hardware.chassis_serial),
        ("UUID", hardware.uuid),
        ("Serie sistema", hardware.serial),
        ("BIOS/UEFI", _join_space(hardware.bios_vendor, hardware.bios_version, hardware.bios_date)),
        ("Dominio/Grupo", hardware.domain_group or "Nao ingressado"),
        ("Fingerprint", dossier.fingerprint),
    ):
        _pdf_kv(pdf, label, value)

    _pdf_heading(pdf, "3. Sistema operacional e licenca")
    for label, value in _licenca_rows(form, hardware):
        if label == "RISCO (chave completa)":
            _pdf_alert(pdf, value)
            continue
        shown = value
        if label == "SO (nome)":
            label = "Sistema"
        elif label == "Build":
            label = "Build / Arch"
            shown = _join_space(hardware.kernel, hardware.arch)
        elif label == "Arquitetura":
            continue
        elif label == "Status da licenca":
            label = "Status licenca"
        elif label == "Tipo da licenca":
            label = "Tipo licenca:"
        elif label == "Ligada a placa-mae?":
            label = "Ligada a placa-mae"
        elif label == "Chave parcial (auto)":
            label = "Chave parcial"
        elif label == "Chave completa (manual)":
            label = "Chave (manual)"
        _pdf_kv(pdf, label, shown)

    _pdf_heading(pdf, "4. Placa-mae")
    for label, value in _campos_placa(hardware):
        _pdf_kv(pdf, label, value)
    _pdf_components(pdf, "", dossier, "motherboard")
    _pdf_melhoria(pdf, _melhoria_placa(hardware))
    _pdf_heading(pdf, "5. Processador")
    for label, value in _campos_cpu(hardware):
        _pdf_kv(pdf, label, value)
    _pdf_melhoria(pdf, _melhoria_cpu(hardware))
    _pdf_heading(pdf, "6. Memoria RAM")
    for label, value in _campos_ram(hardware):
        _pdf_kv(pdf, label, value)
    verdict, detalhe = _ram_text(hardware)
    if detalhe:
        _pdf_note(pdf, f"Detalhe: {detalhe}")
    _pdf_components(pdf, "", dossier, "ram")
    _pdf_melhoria(pdf, _melhoria_ram(hardware))
    _pdf_heading(pdf, "7. Armazenamento")
    for label, value in _campos_disco(hardware):
        _pdf_kv(pdf, label, value)
    _pdf_components(pdf, "", dossier, "disk")
    _pdf_melhoria(pdf, _melhoria_disco(hardware))
    _pdf_heading(pdf, "8. Placa de video")
    for label, value in _campos_video(hardware):
        _pdf_kv(pdf, label, value)
    _pdf_note(pdf, "Serie patrimonial da GPU: o Linux quase nunca expoe. Use etiqueta fisica e preencha serie manual na planilha (aba Componentes).")
    _pdf_melhoria(pdf, _melhoria_video(hardware))
    _pdf_components(pdf, "9. Monitores", dossier, "monitor")
    _pdf_melhoria(pdf, _melhoria_monitor(hardware))
    _pdf_components(pdf, "10. Rede (MAC)", dossier, "network")
    _pdf_note(pdf, "O MAC e usado como identidade de rastreio da placa de rede (campo serie).")
    _pdf_melhoria(pdf, _melhoria_rede(hardware))
    _pdf_sub(pdf, "Perifericos")
    for label, value in _radio_rows(hardware):
        _pdf_kv(pdf, label, value)
    _pdf_melhoria(pdf, _melhoria_perifericos(hardware))

    _pdf_heading(pdf, "11. O que ainda da para expandir?")
    _pdf_note(pdf, "Cada item abaixo registra o que ainda cabe neste computador.")
    _pdf_sub(pdf, "1) Memoria RAM")
    if verdict.startswith("SIM"):
        _pdf_verdict(pdf, f"PODE EXPANDIR: {verdict}", "sim")
    elif verdict.startswith("NAO"):
        _pdf_verdict(pdf, "PODE EXPANDIR: NAO — todos os slots estao ocupados (so trocando os modulos por outros maiores)", "nao")
    else:
        _pdf_verdict(pdf, "PODE EXPANDIR: INDETERMINADO", "info")
    _pdf_note(pdf, f"Detalhe: {detalhe}" if detalhe else "Detalhe: informacao incompleta no firmware")
    _pdf_sub(pdf, "2) Placa de video")
    video_veredito, video_detalhe = _expansao_video(hardware)
    _pdf_verdict(pdf, f"PODE EXPANDIR: {video_veredito}", "info")
    _pdf_note(pdf, f"Detalhe: {video_detalhe}")
    _pdf_sub(pdf, "3) SSD e HDD")
    _pdf_kv(pdf, "Velocidade do SSD", hardware.ssd_speed or "Nao identificada")
    _pdf_kv(pdf, "Controlador SATA", _controlador_sata(hardware))
    _pdf_kv(pdf, "Portas SATA livres", _portas_sata_livres(hardware))
    _pdf_kv(pdf, "Espaco em disco", hardware.disk_space)
    _pdf_melhoria(pdf, _melhoria_disco(hardware))
    _pdf_sub(pdf, "4) Processador")
    _pdf_melhoria(pdf, _melhoria_cpu(hardware))
    _pdf_sub(pdf, "5) Rede e perifericos")
    _pdf_melhoria(pdf, _melhoria_rede(hardware))
    _pdf_melhoria(pdf, _melhoria_perifericos(hardware))
    if hardware.slots:
        _pdf_sub(pdf, "6) Slots PCI")
        for slot in hardware.slots:
            detail = " / ".join(part for part in (slot.slot_type, slot.width, slot.usage) if part)
            _pdf_kv(pdf, slot.designation, detail or "—")

    _pdf_heading(pdf, "12. Pendencias patrimoniais (pecas sem serie)")
    if not pendencias:
        _pdf_note(pdf, "Nenhuma pendencia de serie nestas pecas.")
    for peca in pendencias:
        _pdf_kv(pdf, peca.categoria, _join_space(peca.fabricante, peca.modelo, peca.notas))

    pdf.output(str(path))


def _pdf_components(pdf, title: str, dossier: Dossier, categoria: str) -> None:
    items = [peca for peca in dossier.pecas if peca.categoria == categoria]
    if title:
        _pdf_heading(pdf, title)
    if not items and title:
        _pdf_note(pdf, "Nenhum item coletado.")
    for peca in items:
        _pdf_comp(pdf, peca)


def _pdf_comp(pdf, peca: Peca) -> None:
    titulo = _join_space(peca.fabricante, peca.modelo)
    if peca.fabricante and peca.modelo.lower().startswith(peca.fabricante.lower()):
        titulo = peca.modelo
    if peca.categoria == "disk" and not titulo:
        titulo = "Disco"
    if not titulo:
        titulo = peca.categoria
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 11)
    pdf.multi_cell(0, 6, _pdf_safe(f"* {titulo}"), new_x="LMARGIN", new_y="NEXT")
    lines = _pdf_comp_lines(peca)
    for label, value in lines:
        _pdf_kv(pdf, label, value, emph=label in {"MAC (serie)", "Serie", "Tipo", "Resolucao", "VRAM"})
    pdf.ln(1)


def _pdf_comp_lines(peca: Peca) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    if peca.categoria == "network" and peca.numero_serie:
        lines.append(("MAC (serie)", peca.numero_serie))
    elif peca.numero_serie:
        lines.append(("Serie", peca.numero_serie))
    if peca.serie_manual:
        lines.append(("Serie manual", peca.serie_manual))
    if peca.capacidade:
        if peca.categoria == "monitor":
            lines.append(("Tamanho aprox.", peca.capacidade))
        elif peca.categoria == "gpu":
            lines.append(("VRAM", peca.capacidade))
        else:
            lines.append(("Capacidade", peca.capacidade))
    if peca.categoria == "disk" and peca.posicao:
        lines.append(("Volumes", peca.posicao))
    elif peca.posicao or peca.socket_ou_slot:
        pos = peca.posicao or peca.socket_ou_slot
        label = "Conexao" if peca.categoria == "network" else "Posicao"
        lines.append((label, pos))
    if peca.interface:
        if peca.categoria == "gpu":
            label = "Chip de video"
        elif peca.categoria == "ram":
            label = "Formato"
        else:
            label = "Interface"
        lines.append((label, peca.interface))
    if peca.velocidade:
        if peca.categoria == "network":
            label = "Link"
        elif peca.categoria == "gpu":
            label = "Modo atual"
        elif peca.categoria == "monitor":
            label = "Resolucao"
        else:
            label = "Velocidade"
        lines.append((label, peca.velocidade))
    if peca.quantidade_logica:
        label = "Nucleos/threads" if peca.categoria == "cpu" else "Info"
        lines.append((label, peca.quantidade_logica))
    if peca.tipo_tecnologia and peca.categoria != "slot":
        labels = {"ram": "Tipo", "gpu": "Data driver", "monitor": "Fabricacao", "cpu": "Arquitetura", "disk": "Midia"}
        lines.append((labels.get(peca.categoria, "Tecnologia"), peca.tipo_tecnologia))
    if peca.part_number and peca.categoria in {"network", "monitor", "gpu"}:
        labels = {"gpu": "Driver", "network": "Servico"}
        lines.append((labels.get(peca.categoria, "Codigo produto"), peca.part_number))
    if peca.detalhe_expansao and peca.categoria == "motherboard":
        lines.append(("Slots", peca.detalhe_expansao))
    if peca.detalhe_expansao and peca.categoria == "disk":
        lines.append(("Portas SATA", peca.detalhe_expansao))
    if peca.notas:
        lines.append(("Obs.", peca.notas))
    if peca.serie_status and peca.serie_status != "ok":
        lines.append(("Status serie", peca.serie_status))
    return lines


def _pdf_heading(pdf, text: str) -> None:
    if pdf.get_y() > pdf.h - 30:
        pdf.add_page()
    pdf.ln(1)
    pdf.set_fill_color(46, 117, 182)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, _pdf_safe(text), fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(20, 20, 20)
    pdf.ln(1)


def _pdf_sub(pdf, text: str) -> None:
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(31, 78, 121)
    pdf.cell(0, 6, _pdf_safe(text), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(20, 20, 20)


def _pdf_kv(pdf, label: str, value: str, emph: bool = False) -> None:
    shown = value.strip() if value else ""
    if not shown:
        return
    pdf.set_font("Helvetica", "", 9)
    key_w = 48
    value_w = pdf.epw - key_w
    pdf.set_font("Helvetica", "B" if emph else "", 9)
    value_lines = _pdf_wrap(pdf, shown, value_w - 2)
    pdf.set_font("Helvetica", "B", 8)
    key_lines = _pdf_wrap(pdf, label, key_w - 2)
    height = max(6.5, 4.2 * max(len(key_lines), len(value_lines)) + 1.6)
    if pdf.get_y() + height > pdf.h - 16:
        pdf.add_page()
    x, y = pdf.l_margin, pdf.get_y()
    pdf.set_fill_color(231, 230, 230)
    pdf.rect(x, y, key_w, height, "F")
    pdf.rect(x + key_w, y, value_w, height, "D")
    pdf.set_xy(x + 1, y + 0.8)
    pdf.set_font("Helvetica", "B", 8)
    pdf.multi_cell(key_w - 2, 4.2, _pdf_safe(label))
    pdf.set_xy(x + key_w + 1, y + 0.8)
    pdf.set_font("Helvetica", "B" if emph else "", 9)
    pdf.multi_cell(value_w - 2, 4.2, _pdf_safe(shown))
    pdf.set_xy(x, y + height)


def _pdf_alert(pdf, text: str) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_fill_color(255, 205, 210)
    pdf.set_font("Helvetica", "B", 9)
    pdf.multi_cell(0, 5, _pdf_safe(text), border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def _pdf_melhoria(pdf, texto: str) -> None:
    baixo = texto.lower()
    if any(token in baixo for token in ("cabem", "sem particao", "slot livre", "livre(s)")):
        kind = "sim"
    elif baixo.startswith("nao ha") or "estao cheios" in baixo or "estao ocupad" in baixo:
        kind = "nao"
    else:
        kind = "info"
    _pdf_verdict(pdf, f"O que da para melhorar: {texto}", kind)


def _pdf_verdict(pdf, text: str, kind: str) -> None:
    colors = {"sim": (200, 230, 201), "nao": (255, 205, 210), "info": (255, 243, 205)}
    pdf.set_x(pdf.l_margin)
    pdf.set_fill_color(*colors.get(kind, colors["info"]))
    pdf.set_font("Helvetica", "B", 10)
    pdf.multi_cell(0, 6, _pdf_safe(text), border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def _pdf_note(pdf, text: str) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5, _pdf_safe(text), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(0.5)


def _pdf_wrap(pdf, text: str, width: float) -> list[str]:
    lines: list[str] = []
    for paragraph in _pdf_safe(text).splitlines() or [""]:
        current = ""
        for word in paragraph.split():
            trial = word if not current else f"{current} {word}"
            if pdf.get_string_width(trial) <= width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        lines.append(current or "")
    return lines or [""]


def _pdf_safe(text: str) -> str:
    cleaned = (text or "").replace("—", "-").replace("–", "-")
    return cleaned.encode("latin-1", "replace").decode("latin-1")


def _garantia(valor: str) -> tuple[str, str]:
    text = valor.strip()
    if text.isdigit():
        return text, ""
    return "", text


def _cpu_detail(hardware: Hardware) -> str:
    parts = []
    if hardware.cpu_cores:
        parts.append(f"{hardware.cpu_cores}c")
    if hardware.cpu_threads:
        parts.append(f"{hardware.cpu_threads}t")
    return "/".join(parts)


def _cpu_notes(hardware: Hardware) -> str:
    parts = []
    if hardware.cpu_family:
        parts.append(f"Family={hardware.cpu_family}")
    if hardware.cpu_stepping:
        parts.append(f"Stepping={hardware.cpu_stepping}")
    if hardware.cpu_l2:
        parts.append(f"L2 {hardware.cpu_l2}")
    if hardware.cpu_l3:
        parts.append(f"L3 {hardware.cpu_l3}")
    if hardware.cpu_virtualization:
        parts.append(f"Virtualizacao firmware: {hardware.cpu_virtualization}")
    if hardware.cpu_id:
        parts.append(f"ProcessorId: {hardware.cpu_id}")
    if hardware.cpu_current_mhz:
        parts.append(f"Clock atual: {hardware.cpu_current_mhz}")
    if hardware.cpu_address:
        parts.append(f"Endereco: {hardware.cpu_address}")
    if hardware.cpu_model_number:
        parts.append(f"Model={hardware.cpu_model_number}")
    return "; ".join(parts)


def _ram_notes(module) -> str:
    parts = []
    if module.data_width:
        parts.append(f"Largura de dados: {module.data_width}")
    if module.total_width:
        parts.append(f"Largura total: {module.total_width}")
    if module.rank:
        parts.append(f"Rank: {module.rank}")
    return "; ".join(parts)


def _mode_text(resolution: str, refresh: str) -> str:
    if resolution and refresh:
        return f"{resolution} @ {refresh}"
    return resolution or refresh


def _nic_notes(nic) -> str:
    parts = []
    if nic.status:
        parts.append(f"Status: {nic.status}")
    if nic.adapter_type:
        parts.append(f"Tipo: {nic.adapter_type}")
    if nic.pci_id:
        parts.append(f"ID tecnico: {nic.pci_id}")
    return "; ".join(parts)


def _disk_brand(model: str) -> str:
    upper = model.upper()
    brands = (
        ("KINGSTON", "Kingston"),
        ("SAMSUNG", "Samsung"),
        ("SEAGATE", "Seagate"),
        ("TOSHIBA", "Toshiba"),
        ("CRUCIAL", "Crucial/Micron"),
        ("MICRON", "Crucial/Micron"),
        ("WDC", "Western Digital"),
        ("WESTERN DIGITAL", "Western Digital"),
        ("SANDISK", "SanDisk"),
        ("INTEL", "Intel"),
        ("HGST", "HGST/Hitachi"),
    )
    for token, name in brands:
        if token in upper:
            return name
    return ""


def _cpu_vendor(vendor: str) -> str:
    mapped = {"AUTHENTICAMD": "AMD", "GENUINEINTEL": "Intel"}
    return mapped.get(vendor.strip().upper(), vendor.strip())


def _brand_from_text(text: str) -> str:
    upper = text.upper()
    if "ADVANCED MICRO DEVICES" in upper or upper.startswith("AMD"):
        return "AMD"
    if "NVIDIA" in upper:
        return "NVIDIA"
    if "INTEL" in upper:
        return "Intel"
    if upper.startswith("LG"):
        return "LG"
    if upper.startswith("DELL"):
        return "Dell"
    if "REALTEK" in upper:
        return "Realtek"
    token = text.strip().split(" ", 1)[0] if text.strip() else ""
    return token if token.isalpha() else ""


def _join_space(*parts: str) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())
