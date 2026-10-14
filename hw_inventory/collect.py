"""Coleta de hardware somente neste computador, no Linux."""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
from datetime import datetime
from pathlib import Path

from hw_inventory.license_key import partial_key, read_linux_key
from hw_inventory.models import Disk, Gpu, Hardware, MemoryModule, Monitor, NetworkInterface, PciSlot

_EMPTY_SERIALS = {
    "",
    "none",
    "n/a",
    "na",
    "not specified",
    "not available",
    "to be filled by o.e.m.",
    "to be filled by o.e.m",
    "default string",
    "system serial number",
    "chassis serial number",
    "unknown",
    "0",
    "00000000",
    "000000000000",
    "ffffffff",
    "not present",
}


def collect_hardware() -> Hardware:
    dmi_text, dmi_error = _dmidecode()
    records = parse_dmidecode(dmi_text)
    by_type: dict[int, list[dict[str, str]]] = {}
    for record in records:
        by_type.setdefault(record["type"], []).append(record["fields"])

    system = _first(by_type, 1)
    board = _first(by_type, 2)
    bios = _first(by_type, 0)
    chassis = _first(by_type, 3)
    cpu_dmi = _first_populated_cpu(by_type.get(4, []))
    arrays = by_type.get(16, [])
    modules_raw = by_type.get(17, [])

    sysfs = _sysfs_dmi()
    cpu = _cpu_info()
    modules = [_memory_module(fields) for fields in modules_raw]
    installed = [item for item in modules if item.installed]
    slots_total = _sum_int(arrays, "Number Of Devices")
    if slots_total <= 0 and modules:
        slots_total = len(modules)
    slots_used = len(installed) if modules else 0
    memory_max = _first_value(arrays, "Maximum Capacity")
    memory_total = _installed_memory(installed) or _meminfo_total()

    hardware = Hardware(
        hostname=_hostname(),
        os_name=_os_name(),
        kernel=os.uname().release,
        arch=os.uname().machine,
        manufacturer=_prefer(system.get("Manufacturer"), sysfs.get("sys_vendor")),
        product=_prefer(system.get("Product Name"), sysfs.get("product_name")),
        version=_prefer(system.get("Version"), sysfs.get("product_version")),
        serial=blank_serial(_prefer(system.get("Serial Number"), sysfs.get("product_serial"))),
        uuid=_prefer(system.get("UUID"), sysfs.get("product_uuid")),
        bios_vendor=_prefer(bios.get("Vendor"), sysfs.get("bios_vendor")),
        bios_version=_prefer(bios.get("Version"), sysfs.get("bios_version")),
        bios_date=_prefer(bios.get("Release Date"), sysfs.get("bios_date")),
        board_vendor=_prefer(board.get("Manufacturer"), sysfs.get("board_vendor")),
        board_name=_prefer(board.get("Product Name"), sysfs.get("board_name")),
        board_version=_prefer(board.get("Version"), sysfs.get("board_version")),
        board_serial=blank_serial(_prefer(board.get("Serial Number"), sysfs.get("board_serial"))),
        chassis_type=_prefer(chassis.get("Type"), _chassis_type_name(sysfs.get("chassis_type", ""))),
        chassis_serial=blank_serial(_prefer(chassis.get("Serial Number"), sysfs.get("chassis_serial"))),
        cpu_model=cpu["model"],
        cpu_vendor=_prefer(cpu_dmi.get("Manufacturer"), cpu["vendor"]),
        cpu_cores=cpu["cores"] or _field(cpu_dmi, "Core Count"),
        cpu_threads=cpu["threads"] or _field(cpu_dmi, "Thread Count"),
        cpu_max_mhz=cpu["max_mhz"] or _mhz(cpu_dmi.get("Max Speed", "")),
        cpu_serial=blank_serial(cpu_dmi.get("Serial Number", "")),
        memory_total=memory_total,
        memory_slots_total=str(slots_total) if slots_total else "",
        memory_slots_used=str(slots_used) if modules else "",
        memory_max=memory_max,
        memory_expansion=_memory_expansion(slots_total, slots_used, memory_max, bool(modules or arrays)),
        modules=modules,
        disks=_disks(),
        gpus=_gpus(),
        video_expansion="Indeterminada. Os slots PCI nao foram lidos; no Linux o dmidecode precisa de sudo.",
        storage_expansion="Indeterminada. As baias M.2 nao foram lidas; no Linux o dmidecode precisa de sudo.",
        monitors=_monitors(),
        nics=_nics(),
        collected_at=datetime.now().strftime("%d/%m/%Y %H:%M"),
    )
    edition, version = os_edition_version(_os_release())
    hardware.os_edition = edition
    hardware.os_version = version
    hardware.domain_group = _domain_group()
    hardware.cpu_position, hardware.cpu_socket = cpu_place_and_socket(
        cpu_dmi.get("Socket Designation", ""),
        cpu_dmi.get("Upgrade", ""),
        len(_populated_cpus(by_type.get(4, []))),
    )
    hardware.cpu_family = cpu.get("family", "")
    hardware.cpu_stepping = cpu.get("stepping", "")
    hardware.cpu_l2 = _prefer(_cache_size(cpu_dmi, "L2"), cpu.get("l2"))
    hardware.cpu_l3 = _prefer(_cache_size(cpu_dmi, "L3"), cpu.get("l3"))
    hardware.cpu_virtualization = cpu.get("virtualization", "")
    hardware.cpu_id = blank_serial(cpu_dmi.get("ID", ""))
    hardware.cpu_current_mhz = cpu.get("current_mhz", "")
    hardware.cpu_address = cpu.get("address", "")
    hardware.cpu_model_number = cpu.get("model_number", "")
    hardware.bios_serial = blank_serial(bios.get("Serial Number", ""))
    hardware.slots = _pci_slots(by_type.get(9, []))
    hardware.chipset = _chipset() or chipset_from_name(hardware.board_name, hardware.product)
    for gpu in hardware.gpus:
        gpu.instalacao = gpu_instalacao(gpu.name, hardware.cpu_model)
    if hardware.gpus and hardware.monitors and not hardware.gpus[0].mode:
        shown = next((item for item in hardware.monitors if item.resolution), None)
        if shown is not None:
            hardware.gpus[0].mode = _mode_text(shown.resolution, shown.refresh)
            hardware.gpus[0].refresh = shown.refresh
    radio = _radio()
    hardware.wifi_adapter = radio["wifi_adapter"]
    hardware.hotspot = radio["hotspot"]
    hardware.hotspot_detail = radio["hotspot_detail"]
    hardware.bluetooth_adapter = radio["bluetooth_adapter"]
    hardware.bluetooth = radio["bluetooth"]
    hardware.camera_integrada = radio["camera_integrada"]
    hardware.caixa_som = radio["caixa_som"]
    hardware.saidas_audio = radio["saidas_audio"]
    hardware.ssd_speed = "; ".join(disk.link for disk in hardware.disks if disk.link)
    sata_free, sata_total, sata_speed = _sata_ports()
    hardware.sata_ports_free = str(sata_free)
    hardware.sata_ports_total = str(sata_total)
    hardware.sata_speed = sata_speed
    if sata_total:
        hardware.storage_expansion = f"Sim, {sata_free} de {sata_total} portas SATA livres"
    hardware.disk_space = _disk_space()
    linux_key = read_linux_key()
    hardware.license_key = linux_key
    hardware.license_key_partial = partial_key(linux_key)
    if dmi_error:
        hardware.notes.append(dmi_error)
    if not hardware.modules and not arrays:
        hardware.notes.append(
            "Slots de memória não apareceram. Com sudo, o dmidecode mostra cada módulo e a expansão."
        )
    if not hardware.monitors:
        hardware.notes.append(
            "Nenhum monitor identificado. Execute com sudo -E para enxergar a sessão gráfica."
        )
    return hardware


def parse_dmidecode(text: str) -> list[dict]:
    records: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        if line.startswith("Handle "):
            if current is not None:
                records.append(current)
            match = re.search(r"DMI type (\d+)", line)
            current = {
                "type": int(match.group(1)) if match else -1,
                "fields": {},
            }
            continue
        if current is None:
            continue
        if line.startswith("\t") and ":" in line:
            key, value = line.strip().split(":", 1)
            current["fields"][key.strip()] = value.strip()
    if current is not None:
        records.append(current)
    return records


def blank_serial(value: str | None) -> str:
    text = (value or "").strip()
    if text.lower() in _EMPTY_SERIALS:
        return ""
    if text.lower().startswith("to be filled"):
        return ""
    return text


def run_command(command: list[str], timeout: int = 20) -> str:
    if not command or not command[0]:
        return ""
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout or ""


def _dmidecode() -> tuple[str, str]:
    binary = shutil.which("dmidecode") or "/usr/sbin/dmidecode"
    if not Path(binary).is_file() and shutil.which("dmidecode") is None:
        return "", "dmidecode não está instalado. A identificação de série, memória e placa-mãe fica incompleta."
    try:
        completed = subprocess.run(
            [binary],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "", "Não foi possível executar o dmidecode."
    if completed.returncode != 0 and not completed.stdout:
        detail = (completed.stderr or "").strip().splitlines()
        message = detail[-1] if detail else "dmidecode recusou a leitura."
        if "permission" in message.lower() or "permissão" in message.lower():
            message = "Sem permissão para ler o dmidecode. Execute com sudo."
        return "", message
    return completed.stdout or "", ""


def _sysfs_dmi() -> dict[str, str]:
    base = Path("/sys/class/dmi/id")
    names = (
        "sys_vendor",
        "product_name",
        "product_version",
        "product_serial",
        "product_uuid",
        "bios_vendor",
        "bios_version",
        "bios_date",
        "board_vendor",
        "board_name",
        "board_version",
        "board_serial",
        "chassis_vendor",
        "chassis_type",
        "chassis_serial",
        "chassis_version",
    )
    found: dict[str, str] = {}
    for name in names:
        found[name] = _read_text(base / name)
    return found


def _cpu_info() -> dict[str, str]:
    model = ""
    vendor = ""
    cores = ""
    family = ""
    stepping = ""
    flags = ""
    address = ""
    model_number = ""
    current_mhz = ""
    text = _read_text(Path("/proc/cpuinfo"))
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key == "model name" and not model:
            model = value
        elif key == "vendor_id" and not vendor:
            vendor = value
        elif key == "cpu cores" and not cores:
            cores = value
        elif key == "cpu family" and not family:
            family = value
        elif key == "stepping" and not stepping:
            stepping = value
        elif key == "flags" and not flags:
            flags = value
        elif key == "address sizes" and not address:
            address = value
        elif key == "model" and not model_number:
            model_number = value
        elif key == "cpu MHz" and not current_mhz:
            try:
                current_mhz = f"{float(value):.0f} MHz"
            except ValueError:
                current_mhz = value
    threads = str(os.cpu_count() or "")
    max_mhz = ""
    freq = _read_text(Path("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq"))
    if freq.isdigit():
        max_mhz = f"{int(freq) / 1000:.0f} MHz"
    l2, l3 = _cpu_caches()
    flag_set = set(flags.split())
    if "svm" in flag_set:
        virtualization = "sim (svm)"
    elif "vmx" in flag_set:
        virtualization = "sim (vmx)"
    else:
        virtualization = "nao" if flags else ""
    return {
        "model": model,
        "vendor": vendor,
        "cores": cores,
        "threads": threads,
        "max_mhz": max_mhz,
        "family": family,
        "stepping": stepping,
        "l2": l2,
        "l3": l3,
        "virtualization": virtualization,
        "address": address,
        "model_number": model_number,
        "current_mhz": current_mhz,
    }


def _cpu_caches() -> tuple[str, str]:
    base = Path("/sys/devices/system/cpu/cpu0/cache")
    l2 = ""
    l3 = ""
    if not base.is_dir():
        return l2, l3
    for index in sorted(base.glob("index*")):
        level = _read_text(index / "level")
        size = _read_text(index / "size")
        if level == "2" and size:
            l2 = size
        elif level == "3" and size:
            l3 = size
    return l2, l3


def _cache_size(fields: dict[str, str], level: str) -> str:
    for key in (f"{level} Cache Size", f"{level} Cache"):
        value = (fields.get(key) or "").strip()
        if value and value.lower() not in {"unknown", "none"}:
            return value
    return ""


def _memory_module(fields: dict[str, str]) -> MemoryModule:
    size = fields.get("Size", "").strip()
    installed = _module_installed(size)
    return MemoryModule(
        locator=fields.get("Locator") or fields.get("Bank Locator") or "—",
        size=size if installed else "vazio",
        mem_type=fields.get("Type", "") if installed else "",
        speed=_prefer(fields.get("Configured Memory Speed"), fields.get("Speed")) if installed else "",
        manufacturer=fields.get("Manufacturer", "") if installed else "",
        serial=blank_serial(fields.get("Serial Number")) if installed else "",
        part_number=(fields.get("Part Number") or "").strip() if installed else "",
        installed=installed,
        form_factor=(fields.get("Form Factor") or "").strip() if installed else "",
        bank=(fields.get("Bank Locator") or "").strip() if installed else "",
        data_width=(fields.get("Data Width") or "").strip() if installed else "",
        total_width=(fields.get("Total Width") or "").strip() if installed else "",
        rank=(fields.get("Rank") or "").strip() if installed else "",
    )


def _module_installed(size: str) -> bool:
    lowered = size.lower()
    if not size:
        return False
    if "no module" in lowered or "not installed" in lowered or "empty" in lowered:
        return False
    return size not in {"0", "0 MB", "0 GB"}


def _installed_memory(modules: list[MemoryModule]) -> str:
    total_mb = 0
    for module in modules:
        total_mb += _size_to_mb(module.size)
    if total_mb <= 0:
        return ""
    if total_mb % 1024 == 0:
        return f"{total_mb // 1024} GB"
    return f"{total_mb / 1024:.1f} GB".replace(".", ",")


def _size_to_mb(size: str) -> int:
    match = re.search(r"(\d+)\s*(GB|MB|TB)", size.upper())
    if not match:
        return 0
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "TB":
        return amount * 1024 * 1024
    if unit == "GB":
        return amount * 1024
    return amount


def _meminfo_total() -> str:
    text = _read_text(Path("/proc/meminfo"))
    match = re.search(r"MemTotal:\s+(\d+)\s+kB", text)
    if not match:
        return ""
    mb = int(match.group(1)) / 1024
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB".replace(".", ",")
    return f"{mb:.0f} MB"


def _memory_expansion(slots_total: int, slots_used: int, memory_max: str, known: bool) -> str:
    if not known or slots_total <= 0:
        return "Indeterminada"
    free = max(slots_total - slots_used, 0)
    text = f"{slots_used} de {slots_total} slots em uso"
    if free:
        text += f"; {free} slot(s) livre(s)"
    else:
        text += "; nenhum slot livre"
    if memory_max:
        text += f"; capacidade máxima da placa: {memory_max}"
    return text


def _disks() -> list[Disk]:
    command = [
        "lsblk",
        "-b",
        "-J",
        "-o",
        "NAME,SIZE,TYPE,MODEL,SERIAL,TRAN,ROTA,LABEL,FSTYPE,MOUNTPOINT,VENDOR",
    ]
    raw = run_command(command)
    devices = _lsblk_devices(raw)
    mounts = _mount_table()
    labels = _labels_by_device()
    disks: list[Disk] = []
    for device in devices:
        if device.get("type") != "disk":
            continue
        name = str(device.get("name") or "")
        if name.startswith("loop") or name.startswith("ram"):
            continue
        size_raw = device.get("size")
        try:
            size = _human_bytes(int(size_raw))
        except (TypeError, ValueError):
            size = str(size_raw or "")
        transport = str(device.get("tran") or "")
        rotational = device.get("rota")
        disks.append(
            Disk(
                name=name,
                model=str(device.get("model") or "").strip(),
                size=size,
                interface=transport or "—",
                media=_media(transport, rotational),
                serial=blank_serial(str(device.get("serial") or "")),
                volumes=volume_summary(device, mounts, labels),
                vendor=str(device.get("vendor") or "").strip(),
                link=_disk_link(name, transport),
            )
        )
    return disks


def _lsblk_devices(raw: str) -> list[dict]:
    if not raw.strip():
        return []
    try:
        import json

        payload = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return list(payload.get("blockdevices") or [])


_PCIE_GEN = {
    "2.5": "1.0",
    "5.0": "2.0",
    "8.0": "3.0",
    "16.0": "4.0",
    "32.0": "5.0",
    "64.0": "6.0",
}


def nvme_link_label(speed: str, width: str) -> str:
    number = speed.strip().split()[0] if speed else ""
    generation = _PCIE_GEN.get(number, "")
    lanes = width.strip()
    if not generation or not lanes.isdigit():
        return ""
    rate = number.split(".")[0]
    return f"PCIe {generation} x{lanes} ({rate} GT/s)"


def sata_speed_from_caps(caps: str) -> str:
    try:
        value = int(str(caps).strip(), 16)
    except ValueError:
        return ""
    iss = (value >> 20) & 0xF
    return {1: "1.5 Gbps", 2: "3 Gbps", 3: "6 Gbps"}.get(iss, "")


def sata_port_is_real(port_cmd: str) -> bool:
    try:
        return int(str(port_cmd).strip(), 16) != 0
    except ValueError:
        return False


def _disk_link(name: str, transport: str) -> str:
    if not name.startswith("nvme"):
        return ""
    match = re.match(r"(nvme\d+)", name)
    if not match:
        return ""
    controller = match.group(1)
    device = Path("/sys/class/nvme") / controller / "device"
    return nvme_link_label(
        _read_text(device / "current_link_speed"),
        _read_text(device / "current_link_width"),
    )


def _sata_ports() -> tuple[int, int, str]:
    root = Path("/sys/class/scsi_host")
    if not root.is_dir():
        return 0, 0, ""
    total = 0
    free = 0
    speed = ""
    for host in sorted(root.glob("host*")):
        if _read_text(host / "proc_name") != "ahci":
            continue
        if not speed:
            speed = sata_speed_from_caps(_read_text(host / "ahci_host_caps"))
        if not sata_port_is_real(_read_text(host / "ahci_port_cmd")):
            continue
        total += 1
        if not any((host / "device").glob("target*/*/block")):
            free += 1
    return free, total, speed


def _media(transport: str, rotational: object) -> str:
    if str(transport).lower() == "nvme":
        return "NVMe"
    if rotational in (True, 1, "1"):
        return "HDD"
    if rotational in (False, 0, "0"):
        return "SSD"
    return "—"


def volume_summary(
    device: dict,
    mounts: dict[str, tuple[str, str]] | None = None,
    labels: dict[str, str] | None = None,
) -> str:
    parts: list[str] = []
    _walk_volumes(device.get("children") or [], parts, mounts or {}, labels or {})
    return "; ".join(parts)


def _walk_volumes(
    children: list,
    parts: list[str],
    mounts: dict[str, tuple[str, str]],
    labels: dict[str, str],
) -> None:
    for child in children:
        if not isinstance(child, dict):
            continue
        kind = str(child.get("type") or "")
        if kind in {"part", "lvm", "crypt", "raid"}:
            name = str(child.get("name") or "")
            fstype = str(child.get("fstype") or "").strip()
            label = str(child.get("label") or "").strip() or labels.get(name, "")
            mount = str(child.get("mountpoint") or "").strip()
            known = mounts.get(name)
            if known:
                fstype = fstype or known[0]
                mount = mount or known[1]
            bits = [name]
            for value in (fstype, label, mount):
                if value and value not in bits:
                    bits.append(value)
            text = " ".join(bit for bit in bits if bit)
            if text:
                parts.append(text)
        nested = child.get("children") or []
        if nested:
            _walk_volumes(nested, parts, mounts, labels)


def _mount_table() -> dict[str, tuple[str, str]]:
    found: dict[str, tuple[str, str]] = {}
    for line in _read_text(Path("/proc/mounts")).splitlines():
        parts = line.split()
        if len(parts) < 3 or not parts[0].startswith("/dev/"):
            continue
        name = parts[0].rsplit("/", 1)[-1]
        mount = parts[1].replace("\\040", " ")
        found[name] = (parts[2], mount)
    return found


def _labels_by_device() -> dict[str, str]:
    root = Path("/dev/disk/by-label")
    found: dict[str, str] = {}
    if not root.is_dir():
        return found
    for entry in root.iterdir():
        try:
            found[entry.resolve().name] = entry.name
        except OSError:
            continue
    return found


def gpu_instalacao(name: str, cpu_model: str) -> str:
    lowered = name.lower()
    if any(token in lowered for token in ("geforce", "quadro", "rtx ", "gtx ", "radeon rx", "radeon pro", "arc a")):
        return "nao"
    onboard = (
        "phoenix",
        "raphael",
        "rembrandt",
        "cezanne",
        "renoir",
        "picasso",
        "barcelo",
        "lucienne",
        "mendocino",
        "hawk point",
        "radeon graphics",
        "uhd graphics",
        "hd graphics",
        "iris",
        "780m",
        "760m",
        "740m",
    )
    if any(token in lowered for token in onboard):
        return "sim"
    if "graphics" in cpu_model.lower() and any(token in lowered for token in ("amd", "intel", "ati")):
        return "sim"
    return ""


def chipset_from_name(board: str, product: str) -> str:
    match = re.search(r"\b([ABHXZ]\d{3}[A-Z]?)\b", f"{board} {product}".upper())
    return match.group(1) if match else ""


def slot_is_free(usage: str) -> bool:
    text = usage.lower()
    return "available" in text or "dispon" in text or text in {"empty", "vazio"}


def slot_purpose(designation: str, slot_type: str, width: str) -> str:
    text = f"{designation} {slot_type} {width}".lower()
    if "m.2" in text or "m2" in text:
        return "SSD M.2"
    if "x16" in text:
        return "placa de video (PCI Express x16)"
    if any(token in text for token in ("x1", "x4", "x8", "pci express", "pcie", "pci-e")):
        return "placa de expansao, inclusive rede (PCI Express)"
    if "pci" in text:
        return "placa PCI"
    return slot_type or "expansao"


def _chipset() -> str:
    raw = run_command(["lspci"])
    for token in ("A620", "B650E", "B650", "X670E", "X670", "A520", "B550", "A320", "B450", "H610", "B660", "Z690"):
        for line in raw.splitlines():
            if token.lower() in line.lower():
                return line.split(": ", 1)[-1].strip()
    return ""


def _gpus() -> list[Gpu]:
    raw = run_command(["lspci", "-nn"])
    found: list[Gpu] = []
    for line in raw.splitlines():
        lowered = line.lower()
        if not any(token in lowered for token in ("vga compatible", "3d controller", "display controller")):
            continue
        address = line.split(" ", 1)[0] if line.split() else ""
        pci_match = re.search(r"\[([0-9a-fA-F]{4}:[0-9a-fA-F]{4})\]", line)
        pci_id = pci_match.group(1).lower() if pci_match else ""
        description = line.split(":", 2)[-1].strip() if line.count(":") >= 2 else line.strip()
        name = re.sub(r"\s*\[[0-9a-fA-F]{4}:[0-9a-fA-F]{4}\]", "", description)
        name = re.sub(r"\s*\(rev [0-9a-fA-F]+\)\s*$", "", name).strip()
        gpu = Gpu(name=name, pci_id=pci_id)
        _enrich_gpu(gpu, address)
        found.append(gpu)
    return found


def _enrich_gpu(gpu: Gpu, address: str) -> None:
    verbose = run_command(["lspci", "-v", "-s", address]) if address else ""
    driver = ""
    for line in verbose.splitlines():
        if "Kernel driver in use:" in line:
            driver = line.split(":", 1)[1].strip()
        elif "Kernel modules:" in line and not driver:
            driver = line.split(":", 1)[1].split(",", 1)[0].strip()
    gpu.driver = driver
    gpu.vram = _gpu_vram(address, verbose)
    gpu.bus = _gpu_link(address)
    if not driver:
        return
    version_lines = run_command(["modinfo", "-F", "version", driver]).splitlines()
    gpu.driver_version = version_lines[0].strip() if version_lines else ""
    filename_lines = run_command(["modinfo", "-F", "filename", driver]).splitlines()
    if not filename_lines:
        return
    module_path = Path(filename_lines[0].strip())
    try:
        stamp = module_path.stat().st_mtime
    except OSError:
        return
    gpu.driver_date = datetime.fromtimestamp(stamp).strftime("%Y-%m-%d")


def _gpu_link(address: str) -> str:
    if not address:
        return ""
    device = Path("/sys/bus/pci/devices") / f"0000:{address}"
    if not (device / "current_link_speed").is_file():
        device = Path("/sys/bus/pci/devices") / address
    return nvme_link_label(
        _read_text(device / "current_link_speed"),
        _read_text(device / "current_link_width"),
    )


def _gpu_vram(address: str, verbose: str) -> str:
    root = Path("/sys/class/drm")
    if root.is_dir() and address:
        for card in root.glob("card[0-9]"):
            if "-" in card.name or not card.is_dir():
                continue
            try:
                pci = (card / "device").resolve().name
            except OSError:
                continue
            short = pci[5:] if pci.startswith("0000:") else pci
            if short != address:
                continue
            for name in ("mem_info_vram_total", "mem_info_vis_vram_total"):
                text = _read_text(card / "device" / name)
                if text.isdigit() and int(text) > 0:
                    return _human_bytes(int(text))
    sizes: list[int] = []
    for line in verbose.splitlines():
        match = re.search(r"prefetchable\)\s*\[size=([0-9.]+)([KMG])\]", line, re.IGNORECASE)
        if not match:
            continue
        amount = float(match.group(1))
        factor = {"K": 1024, "M": 1024**2, "G": 1024**3}[match.group(2).upper()]
        sizes.append(int(amount * factor))
    if sizes:
        return _human_bytes(max(sizes))
    return ""


def _pci_slots(records: list[dict[str, str]]) -> list[PciSlot]:
    slots: list[PciSlot] = []
    for fields in records:
        designation = (fields.get("Designation") or fields.get("Slot Designation") or "").strip()
        if not designation:
            continue
        slots.append(
            PciSlot(
                designation=designation,
                slot_type=(fields.get("Type") or "").strip(),
                width=(fields.get("Data Bus Width") or fields.get("Length") or "").strip(),
                usage=(fields.get("Current Usage") or "").strip(),
            )
        )
    return slots


def _monitors() -> list[Monitor]:
    from_xrandr = _monitors_xrandr()
    edids = _edid_by_connector()
    if from_xrandr:
        for monitor in from_xrandr:
            extra = _match_edid(monitor.connector, edids)
            if extra:
                if extra.get("name") and monitor.name == monitor.connector:
                    monitor.name = extra["name"]
                if extra.get("serial") and not monitor.serial:
                    monitor.serial = extra["serial"]
                monitor.manufacture = extra.get("manufacture", "")
                monitor.product_code = extra.get("product_code", "")
                monitor.native_resolution = extra.get("native", "")
        return from_xrandr
    monitors: list[Monitor] = []
    for connector, info in edids.items():
        if info.get("status") not in {"", "connected"}:
            continue
        if info.get("status") == "disconnected":
            continue
        monitors.append(
            Monitor(
                name=info.get("name") or connector,
                connector=connector,
                resolution="",
                physical_size="",
                serial=info.get("serial", ""),
                manufacture=info.get("manufacture", ""),
                product_code=info.get("product_code", ""),
                native_resolution=info.get("native", ""),
            )
        )
    return [item for item in monitors if item.name]


_XRANDR_CONNECTED = re.compile(
    r"^(\S+)\s+connected(?: primary)?\s+(\d+x\d+)\S*"
    r"(?:\s+\([^)]*\))?(?:\s+(\d+mm x \d+mm))?"
)


def parse_xrandr_monitors(text: str) -> list[Monitor]:
    monitors: list[Monitor] = []
    for line in text.splitlines():
        match = _XRANDR_CONNECTED.match(line.strip())
        if not match:
            continue
        connector = match.group(1)
        monitors.append(
            Monitor(
                name=connector,
                connector=connector,
                resolution=match.group(2),
                physical_size=match.group(3) or "",
                serial="",
            )
        )
    return monitors


def _monitors_xrandr() -> list[Monitor]:
    if not os.environ.get("DISPLAY"):
        return []
    text = run_command(["xrandr", "--query"])
    monitors = parse_xrandr_monitors(text)
    rates = parse_xrandr_refresh(text)
    for monitor in monitors:
        monitor.refresh = rates.get(monitor.connector, "")
    return monitors


def parse_xrandr_refresh(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    current = ""
    for line in text.splitlines():
        head = re.match(r"^(\S+)\s+connected\b", line)
        if head:
            current = head.group(1)
            continue
        if current and line and not line[0].isspace():
            current = ""
            continue
        if not current or "*" not in line:
            continue
        match = re.search(r"(\d+(?:\.\d+)?)\*", line)
        if not match:
            continue
        found[current] = f"{float(match.group(1)):.0f} Hz"
        current = ""
    return found


def _mode_text(resolution: str, refresh: str) -> str:
    if resolution and refresh:
        return f"{resolution} @ {refresh}"
    return resolution or refresh


def _edid_by_connector() -> dict[str, dict[str, str]]:
    root = Path("/sys/class/drm")
    found: dict[str, dict[str, str]] = {}
    if not root.is_dir():
        return found
    for status_file in root.glob("card*-*/status"):
        connector = status_file.parent.name.split("-", 1)[-1]
        status = _read_text(status_file)
        if status != "connected":
            continue
        edid_path = status_file.parent / "edid"
        name = ""
        serial = ""
        manufacture = ""
        product_code = ""
        native = ""
        try:
            data = edid_path.read_bytes()
        except OSError:
            data = b""
        if data:
            name = edid_descriptor(data, 0xFC)
            serial = edid_descriptor(data, 0xFF) or edid_numeric_serial(data)
            manufacture = edid_manufacture(data)
            product_code = edid_product_code(data)
            native = edid_native_resolution(data)
        found[connector] = {
            "status": status,
            "name": name,
            "serial": blank_serial(serial),
            "manufacture": manufacture,
            "product_code": product_code,
            "native": native,
        }
    return found


def edid_product_code(data: bytes) -> str:
    if len(data) < 12:
        return ""
    code = int.from_bytes(data[10:12], "little")
    if code == 0:
        return ""
    return f"{code:04X}"


def edid_manufacture(data: bytes) -> str:
    if len(data) < 18:
        return ""
    week = data[16]
    year = data[17]
    if year == 0:
        return ""
    full_year = 1990 + year
    if 1 <= week <= 54:
        return f"{full_year} (semana {week})"
    return str(full_year)


def edid_native_resolution(data: bytes) -> str:
    if len(data) < 72:
        return ""
    block = data[54:72]
    if block[0] == 0 and block[1] == 0:
        return ""
    width = block[2] + ((block[4] & 0xF0) << 4)
    height = block[5] + ((block[7] & 0xF0) << 4)
    if width < 640 or height < 480:
        return ""
    return f"{width}x{height}"


def edid_numeric_serial(data: bytes) -> str:
    if len(data) < 16:
        return ""
    number = int.from_bytes(data[12:16], "little")
    if number == 0:
        return ""
    return str(number)


def edid_descriptor(data: bytes, kind: int) -> str:
    if len(data) < 128:
        return ""
    for index in range(4):
        block = data[54 + index * 18 : 54 + (index + 1) * 18]
        if len(block) < 18:
            continue
        if block[0:3] == b"\x00\x00\x00" and block[3] == kind:
            text = block[5:18].decode("ascii", errors="replace")
            return text.replace("\n", "").replace("\x00", "").strip()
    return ""


def _match_edid(connector: str, edids: dict[str, dict[str, str]]) -> dict[str, str]:
    if connector in edids:
        return edids[connector]
    normalized = connector.upper().replace("DISPLAYPORT", "DP")
    for key, info in edids.items():
        if key.upper().replace("-", "")[:4] and key.upper() in normalized:
            return info
        family = re.sub(r"[^A-Z]", "", key.upper())
        other = re.sub(r"[^A-Z]", "", normalized)
        if family and family == other:
            return info
    return {}


def ap_mode_supported(iw_text: str) -> bool:
    in_modes = False
    for line in iw_text.splitlines():
        if "Supported interface modes" in line:
            in_modes = True
            continue
        if not in_modes:
            continue
        stripped = line.strip()
        if not stripped.startswith("*"):
            if stripped:
                in_modes = False
            continue
        mode = stripped.lstrip("*").strip()
        if mode == "AP" or mode.startswith("AP "):
            return True
    return False


def usb_has_bluetooth(class_code: str, subclass: str, protocol: str) -> bool:
    return class_code.lower() in {"e0", "0xe0"} and subclass in {"01", "1"} and protocol in {"01", "1"}


def usb_is_video(class_code: str) -> bool:
    return class_code.lower() in {"0e", "0x0e"}


def usb_is_audio(class_code: str) -> bool:
    return class_code.lower() in {"01", "0x01"}


def _radio() -> dict[str, str]:
    wifi_names = _wifi_adapters()
    bluetooth_names = _bluetooth_adapters()
    if not wifi_names:
        hotspot = "Nao"
        detail = "Nenhum adaptador Wi-Fi. So a rede cabeada nao cria hotspot."
    elif not shutil.which("iw"):
        hotspot = "Indeterminado"
        detail = "Ha adaptador Wi-Fi, mas o comando iw nao esta instalado para confirmar o modo AP."
    elif ap_mode_supported(run_command(["iw", "list"])):
        hotspot = "Sim"
        detail = "O adaptador Wi-Fi aceita modo ponto de acesso. A internet de entrada precisa vir de outro enlace, em geral o cabo."
    else:
        hotspot = "Nao"
        detail = "O adaptador Wi-Fi nao oferece modo AP, entao nao cria hotspot."
    if bluetooth_names:
        bluetooth = "Sim"
    else:
        bluetooth = "Nao"
    return {
        "wifi_adapter": ", ".join(wifi_names) if wifi_names else "Nao",
        "hotspot": hotspot,
        "hotspot_detail": detail,
        "bluetooth_adapter": ", ".join(bluetooth_names) if bluetooth_names else "Nao",
        "bluetooth": bluetooth,
        "camera_integrada": _camera_integrada(),
        "caixa_som": _caixa_som(),
        "saidas_audio": _saidas_audio(),
    }


def _wifi_adapters() -> list[str]:
    names: list[str] = []
    phy_root = Path("/sys/class/ieee80211")
    if phy_root.is_dir():
        for phy in sorted(phy_root.iterdir()):
            driver = ""
            link = phy / "device" / "driver"
            if link.exists():
                driver = link.resolve().name
            names.append(" ".join(part for part in (phy.name, driver) if part))
    net_root = Path("/sys/class/net")
    if net_root.is_dir():
        for entry in sorted(net_root.iterdir()):
            if (entry / "wireless").exists() or (entry / "phy80211").exists():
                if not any(entry.name in item for item in names):
                    names.append(entry.name)
    return names


def _bluetooth_adapters() -> list[str]:
    names: list[str] = []
    root = Path("/sys/class/bluetooth")
    if root.is_dir():
        for entry in sorted(root.iterdir()):
            if not entry.name.startswith("hci"):
                continue
            product = _read_text(entry / "device" / "product") or entry.name
            names.append(product)
    usb = Path("/sys/bus/usb/devices")
    if usb.is_dir():
        for dev in usb.iterdir():
            if not (dev / "idVendor").is_file():
                continue
            hit = False
            for iface in dev.glob(dev.name + ":*"):
                if usb_has_bluetooth(
                    _read_text(iface / "bInterfaceClass"),
                    _read_text(iface / "bInterfaceSubClass"),
                    _read_text(iface / "bInterfaceProtocol"),
                ):
                    hit = True
                    break
            if not hit:
                continue
            product = _read_text(dev / "product") or _read_text(dev / "manufacturer") or dev.name
            if product not in names:
                names.append(product)
    return names


def _usb_interface_codes(dev: Path) -> list[str]:
    codes = []
    for iface in dev.glob(dev.name + ":*"):
        code = _read_text(iface / "bInterfaceClass")
        if code:
            codes.append(code.lower())
    return codes


def _camera_integrada() -> str:
    usb = Path("/sys/bus/usb/devices")
    if usb.is_dir():
        for dev in usb.iterdir():
            if not (dev / "idVendor").is_file():
                continue
            if not any(usb_is_video(code) for code in _usb_interface_codes(dev)):
                continue
            if _read_text(dev / "removable").lower() == "fixed":
                return "Sim"
    root = Path("/sys/class/video4linux")
    if root.is_dir():
        for node in root.iterdir():
            try:
                device = (node / "device").resolve()
            except OSError:
                continue
            if "usb" not in str(device):
                return "Sim"
    return "Nao"


_PIN_AUDIO = re.compile(r"Pin Default 0x[0-9a-f]+: \[([^\]]+)\] (.+)", re.IGNORECASE)
_SAIDA_ORDEM = (
    "Fone frontal",
    "Fone traseiro",
    "Line-out frontal",
    "Line-out traseiro",
    "Line-out",
    "HDMI",
    "Caixa USB",
)


def saidas_from_codec(text: str) -> list[str]:
    found: list[str] = []
    for presence, desc in _PIN_AUDIO.findall(text):
        if presence.strip().upper() == "N/A":
            continue
        low = " ".join(desc.split()).lower()
        if "hp out" in low and "front" in low:
            label = "Fone frontal"
        elif "hp out" in low and "rear" in low:
            label = "Fone traseiro"
        elif low.startswith("line out") and "rear" in low:
            label = "Line-out traseiro"
        elif low.startswith("line out") and "front" in low:
            label = "Line-out frontal"
        elif low.startswith("line out"):
            label = "Line-out"
        else:
            continue
        if label not in found:
            found.append(label)
    return found


def hdmi_audio_active(eld_text: str) -> bool:
    present = False
    valid = False
    for line in eld_text.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        if parts[0] == "monitor_present" and parts[-1] == "1":
            present = True
        elif parts[0] == "eld_valid" and parts[-1] == "1":
            valid = True
    return present and valid


def _caixa_som() -> str:
    root = Path("/proc/asound")
    if not root.is_dir():
        return "Nao"
    for card in sorted(root.glob("card[0-9]*")):
        playback = any(item.is_dir() and item.name.startswith("pcm") and item.name.endswith("p") for item in card.iterdir())
        usbid = _read_text(card / "usbid").lower()
        if not playback or ":" not in usbid:
            continue
        vendor, product = usbid.split(":", 1)
        device = _usb_device(vendor, product)
        if device is None:
            continue
        if any(usb_is_video(code) for code in _usb_interface_codes(device)):
            continue
        if _read_text(device / "removable").lower() == "fixed":
            continue
        return "Sim"
    return "Nao"


def _saidas_audio() -> str:
    labels: list[str] = []
    root = Path("/proc/asound")
    if root.is_dir():
        for card in sorted(root.glob("card[0-9]*")):
            for codec in sorted(card.glob("codec#*")):
                for label in saidas_from_codec(_read_text(codec)):
                    if label not in labels:
                        labels.append(label)
            for eld in sorted(card.glob("eld#*")):
                if hdmi_audio_active(_read_text(eld)) and "HDMI" not in labels:
                    labels.append("HDMI")
    if _caixa_som() == "Sim" and "Caixa USB" not in labels:
        labels.append("Caixa USB")
    labels.sort(key=lambda item: _SAIDA_ORDEM.index(item) if item in _SAIDA_ORDEM else len(_SAIDA_ORDEM))
    return ", ".join(labels) if labels else "Nao identificado"


def _usb_device(vendor: str, product: str) -> Path | None:
    root = Path("/sys/bus/usb/devices")
    if not root.is_dir():
        return None
    for dev in root.iterdir():
        if _read_text(dev / "idVendor").lower() == vendor and _read_text(dev / "idProduct").lower() == product:
            return dev
    return None


def _nics() -> list[NetworkInterface]:
    root = Path("/sys/class/net")
    if not root.is_dir():
        return []
    interfaces: list[NetworkInterface] = []
    for entry in sorted(root.iterdir()):
        if not (entry / "device").exists():
            continue
        name = entry.name
        mac = _read_text(entry / "address")
        speed_raw = _read_text(entry / "speed")
        if speed_raw.isdigit() and int(speed_raw) > 0:
            speed = f"{speed_raw} Mb/s"
        else:
            speed = ""
        driver = ""
        driver_link = entry / "device" / "driver"
        if driver_link.exists():
            driver = driver_link.resolve().name
        oper = _read_text(entry / "operstate")
        status = {"up": "conectado", "down": "desconectado"}.get(oper, oper)
        wireless = (entry / "wireless").exists() or (entry / "phy80211").exists()
        pci_id = ""
        device = entry / "device"
        try:
            pci_name = device.resolve().name
        except OSError:
            pci_name = ""
        if pci_name:
            pci_id = pci_name[5:] if pci_name.startswith("0000:") else pci_name
        interfaces.append(
            NetworkInterface(
                name=name,
                description=_nic_description(entry),
                mac=mac if mac and mac != "00:00:00:00:00:00" else "",
                ipv4=_ipv4(name),
                speed=speed,
                driver=driver,
                status=status,
                adapter_type="Wi-Fi" if wireless else "Ethernet",
                pci_id=pci_id,
            )
        )
    return interfaces


def _nic_description(entry: Path) -> str:
    device = entry / "device"
    try:
        pci = device.resolve().name
    except OSError:
        return ""
    address = pci[5:] if pci.startswith("0000:") else pci
    raw = run_command(["lspci", "-s", address])
    line = raw.strip().splitlines()
    if not line:
        return ""
    text = line[0]
    if ": " in text:
        return text.split(": ", 1)[1].strip()
    return text


def _ipv4(name: str) -> str:
    raw = run_command(["ip", "-4", "-o", "addr", "show", "dev", name])
    match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", raw)
    return match.group(1) if match else ""


def _hostname() -> str:
    name = socket.gethostname().split(".", 1)[0].strip()
    return name or "PC"


def _os_name() -> str:
    return _os_release().get("PRETTY_NAME", "")


def _os_release() -> dict[str, str]:
    found: dict[str, str] = {}
    for line in _read_text(Path("/etc/os-release")).splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        found[key.strip()] = value.strip().strip('"')
    return found


def os_edition_version(release: dict[str, str]) -> tuple[str, str]:
    version = (release.get("VERSION_ID") or release.get("VERSION") or "").strip()
    edition = (release.get("VERSION_CODENAME") or "").strip()
    parenthetical = re.search(r"\(([^)]+)\)", release.get("VERSION", ""))
    if parenthetical:
        edition = parenthetical.group(1).strip() or edition
    if edition and edition == edition.lower():
        edition = edition[:1].upper() + edition[1:]
    return edition, version


def domain_group_label(realm_text: str, dns_domain: str, workgroup: str) -> str:
    from hw_inventory.ad import domain_from_realm

    domain = domain_from_realm(realm_text)
    if domain:
        return f"Dominio: {domain}"
    dns = (dns_domain or "").strip().rstrip(".")
    if dns and dns.lower() not in {"(none)", "localdomain", "local", "none"}:
        return f"Dominio: {dns}"
    group = (workgroup or "").strip()
    if group:
        return f"Grupo: {group}"
    return "Nao ingressado"


def _domain_group() -> str:
    realm_text = run_command(["realm", "list"]) if shutil.which("realm") else ""
    dns = run_command(["hostname", "-d"]).strip()
    return domain_group_label(realm_text, dns, _samba_workgroup())


def _samba_workgroup() -> str:
    for path in (Path("/etc/samba/smb.conf"), Path("/etc/smb.conf")):
        for line in _read_text(path).splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith(";"):
                continue
            if stripped.lower().startswith("workgroup"):
                return stripped.split("=", 1)[-1].strip()
    return ""


def unallocated_from_partitions(text: str) -> list[tuple[str, int]]:
    sizes: dict[str, int] = {}
    for line in text.splitlines():
        cols = line.split()
        if len(cols) != 4 or not cols[0].isdigit():
            continue
        name = cols[3]
        if name.startswith(("loop", "ram", "zram", "dm-")):
            continue
        sizes[name] = int(cols[2]) * 1024
    gaps: list[tuple[str, int]] = []
    for name, size in sizes.items():
        if _partition_parent(name):
            continue
        used = sum(part_size for part, part_size in sizes.items() if _partition_parent(part) == name)
        gap = size - used
        if gap > 100 * 1024 * 1024:
            gaps.append((name, gap))
    return gaps


def _partition_parent(name: str) -> str:
    if re.fullmatch(r"nvme\d+n\d+p\d+", name) or re.fullmatch(r"mmcblk\d+p\d+", name):
        return re.sub(r"p\d+$", "", name)
    if re.fullmatch(r"[a-z]+\d+", name):
        return re.sub(r"\d+$", "", name)
    return ""


def _disk_space() -> str:
    partes: list[str] = []
    try:
        status = os.statvfs("/")
        partes.append(
            "Particao em uso: "
            f"{_human_bytes(status.f_bavail * status.f_frsize)} livres de "
            f"{_human_bytes(status.f_blocks * status.f_frsize)}"
        )
    except OSError:
        pass
    gaps = unallocated_from_partitions(_read_text(Path("/proc/partitions")))
    if gaps:
        partes.append(
            "; ".join(f"{name} sem particao {_human_bytes(gap)}" for name, gap in gaps)
        )
    return ". ".join(partes)


def _human_bytes(amount: int) -> str:
    value = float(amount)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            rendered = f"{value:.1f} {unit}"
            return rendered.replace(".0 ", " ").replace(".", ",")
        value /= 1024
    return str(amount)


def _first(by_type: dict[int, list[dict[str, str]]], kind: int) -> dict[str, str]:
    items = by_type.get(kind) or []
    return items[0] if items else {}


_SOCKET_RE = re.compile(r"(?i)\b(?:socket\s+)?(AM\d+|SP\d+|sTRX4|TR4|LGA\s*\d+|FCLGA\d+|BGA\d+)\b")


def _socket_label(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned or cleaned.lower() in {"other", "unknown", "none", "not specified"}:
        return ""
    match = _SOCKET_RE.search(cleaned)
    if not match:
        return ""
    return re.sub(r"\s+", "", match.group(1)).upper()


def cpu_place_and_socket(designation: str, upgrade: str, populated: int = 1) -> tuple[str, str]:
    """Separa o lugar na placa do tipo de soquete usado numa troca."""
    place_name = (designation or "").strip()
    socket = _socket_label(upgrade) or _socket_label(place_name)
    designation_is_socket = bool(socket) and _socket_label(place_name) == socket
    if place_name and not designation_is_socket:
        place = place_name
    elif populated > 1 and place_name:
        place = place_name
    elif socket or place_name:
        place = "Unico processador da placa"
    else:
        place = ""
    return place, socket


def _populated_cpus(records: list[dict[str, str]]) -> list[dict[str, str]]:
    return [fields for fields in records if "Unpopulated" not in fields.get("Status", "")]


def _first_populated_cpu(records: list[dict[str, str]]) -> dict[str, str]:
    for fields in records:
        if "Unpopulated" not in fields.get("Status", ""):
            return fields
    return records[0] if records else {}


def _sum_int(records: list[dict[str, str]], key: str) -> int:
    total = 0
    for fields in records:
        match = re.search(r"\d+", fields.get(key, ""))
        if match:
            total += int(match.group(0))
    return total


def _first_value(records: list[dict[str, str]], key: str) -> str:
    for fields in records:
        value = fields.get(key, "").strip()
        if value and value.lower() not in {"unknown", "none"}:
            return value
    return ""


def _field(fields: dict[str, str], key: str) -> str:
    return (fields.get(key) or "").strip()


def _prefer(*values: str | None) -> str:
    for value in values:
        text = (value or "").strip()
        if text and not _looks_like_placeholder(text):
            return text
    return ""


def _looks_like_placeholder(value: str) -> bool:
    return blank_serial(value) == "" and bool((value or "").strip())


def _mhz(value: str) -> str:
    return value.strip()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


_CHASSIS_TYPES = {
    "3": "Desktop",
    "4": "Low Profile Desktop",
    "6": "Mini Tower",
    "7": "Tower",
    "8": "Portable",
    "9": "Laptop",
    "10": "Notebook",
    "13": "All in One",
    "17": "Main Server Chassis",
    "23": "Rack Mount Chassis",
    "35": "Mini PC",
}


def _chassis_type_name(code: str) -> str:
    return _CHASSIS_TYPES.get(code.strip(), "")
