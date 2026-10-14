"""Dados do formulário e do equipamento coletado neste computador."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FormData:
    patrimonio: str = ""
    responsavel: str = ""
    local: str = ""
    instituicao: str = ""
    setor: str = ""
    compra: str = ""
    garantia: str = ""
    nota_fiscal: str = ""
    status: str = ""
    chave_licenca: str = ""
    observacoes: str = ""


@dataclass
class MemoryModule:
    locator: str
    size: str
    mem_type: str
    speed: str
    manufacturer: str
    serial: str
    part_number: str
    installed: bool
    form_factor: str = ""
    bank: str = ""
    data_width: str = ""
    total_width: str = ""
    rank: str = ""


@dataclass
class Disk:
    name: str
    model: str
    size: str
    interface: str
    media: str
    serial: str
    volumes: str = ""
    vendor: str = ""
    link: str = ""


@dataclass
class Monitor:
    name: str
    connector: str
    resolution: str
    physical_size: str
    serial: str
    manufacture: str = ""
    product_code: str = ""
    native_resolution: str = ""
    refresh: str = ""


@dataclass
class NetworkInterface:
    name: str
    description: str
    mac: str
    ipv4: str
    speed: str
    driver: str
    status: str = ""
    adapter_type: str = ""
    pci_id: str = ""


@dataclass
class Gpu:
    name: str
    vendor: str = ""
    vram: str = ""
    driver: str = ""
    driver_version: str = ""
    driver_date: str = ""
    pci_id: str = ""
    mode: str = ""
    refresh: str = ""
    instalacao: str = ""
    bus: str = ""


@dataclass
class PciSlot:
    designation: str
    slot_type: str = ""
    width: str = ""
    usage: str = ""


@dataclass
class Hardware:
    hostname: str
    os_name: str
    kernel: str
    arch: str
    manufacturer: str
    product: str
    version: str
    serial: str
    uuid: str
    bios_vendor: str
    bios_version: str
    bios_date: str
    board_vendor: str
    board_name: str
    board_version: str
    board_serial: str
    chassis_type: str
    chassis_serial: str
    cpu_model: str
    cpu_vendor: str
    cpu_cores: str
    cpu_threads: str
    cpu_max_mhz: str
    cpu_serial: str
    memory_total: str
    memory_slots_total: str
    memory_slots_used: str
    memory_max: str
    memory_expansion: str
    modules: list[MemoryModule] = field(default_factory=list)
    disks: list[Disk] = field(default_factory=list)
    gpus: list[Gpu] = field(default_factory=list)
    slots: list[PciSlot] = field(default_factory=list)
    video_expansion: str = "Indeterminada"
    storage_expansion: str = "Indeterminada"
    monitors: list[Monitor] = field(default_factory=list)
    nics: list[NetworkInterface] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    collected_at: str = ""
    license_key: str = ""
    license_key_partial: str = ""
    os_edition: str = ""
    os_version: str = ""
    domain_group: str = ""
    cpu_socket: str = ""
    cpu_position: str = ""
    cpu_family: str = ""
    cpu_stepping: str = ""
    cpu_l2: str = ""
    cpu_l3: str = ""
    cpu_virtualization: str = ""
    cpu_id: str = ""
    cpu_current_mhz: str = ""
    cpu_address: str = ""
    cpu_model_number: str = ""
    bios_serial: str = ""
    chipset: str = ""
    wifi_adapter: str = ""
    hotspot: str = ""
    hotspot_detail: str = ""
    bluetooth_adapter: str = ""
    bluetooth: str = ""
    camera_integrada: str = ""
    caixa_som: str = ""
    saidas_audio: str = ""
    ssd_speed: str = ""
    sata_ports_total: str = ""
    sata_ports_free: str = ""
    sata_speed: str = ""
    disk_space: str = ""


@dataclass
class InventoryResult:
    folder: str
    spreadsheet: str
    pdf: str
    spreadsheet_path: str
    pdf_path: str
