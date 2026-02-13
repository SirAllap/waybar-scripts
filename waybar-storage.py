#!/usr/bin/env python3
# ----------------------------------------------------------------------------
# WAYBAR STORAGE MODULE
# ----------------------------------------------------------------------------
# Auto-detects mounted physical drives and displays usage in a sleek dashboard.
# Features:
# - Dynamic drive detection (ignores snaps, loops, etc.)
# - Real-time I/O speeds (Read/Write)
# - Drive temperature monitoring (requires lm_sensors/smartctl)
# - Health status via smartctl (requires sudo)
# ----------------------------------------------------------------------------

import json
import subprocess
import os
import psutil
import re
import time
import pickle
from collections import deque
import math
import pathlib

# ---------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------
SSD_ICON = "\uf0a0"
HDD_ICON = "\uf2db"
HISTORY_FILE = "/tmp/waybar_storage_history.pkl"
TOOLTIP_WIDTH = 45

# Custom drive name mapping
# Format: "base_device_name": "Custom Name"
# Base names: nvme0n1, nvme1n1, sda, dm-0, root, etc.
DRIVE_NAME_MAPPING = {
    "nvme1n1": "Omarchy",   # 1TB WD_BLACK (Root drive)
    "sda": "Mula",          # HDD drive
    "nvme0n1": "Games",     # 256GB Intel SSD
}

# ---------------------------------------------------
# THEME & COLORS
# ---------------------------------------------------
SSD_ICON = ""
HDD_ICON = "󰋊"
HISTORY_FILE = "/tmp/waybar_storage_history.pkl"
TOOLTIP_WIDTH = 45

# ---------------------------------------------------
# THEME & COLORS
# ---------------------------------------------------
try:
    import tomllib
except ImportError:
    tomllib = None

def load_theme_colors():
    # UPDATED: Omarchy theme path with flat color structure
    theme_path = pathlib.Path.home() / ".config/omarchy/current/theme/colors.toml"
    
    defaults = {
        "black": "#000000", "red": "#ff0000", "green": "#00ff00", "yellow": "#ffff00",
        "blue": "#0000ff", "magenta": "#ff00ff", "cyan": "#00ffff", "white": "#ffffff",
        "bright_black": "#555555", "bright_red": "#ff5555", "bright_green": "#55ff55",
        "bright_yellow": "#ffff55", "bright_blue": "#5555ff", "bright_magenta": "#ff55ff",
        "bright_cyan": "#55ffff", "bright_white": "#ffffff"
    }

    if not tomllib or not theme_path.exists():
        return defaults

    try:
        data = tomllib.loads(theme_path.read_text())
        # UPDATED: Omarchy's flat color structure (color0-15)
        colors = {
            "black": data.get("color0", "#000000"),
            "red": data.get("color1", "#ff0000"),
            "green": data.get("color2", "#00ff00"),
            "yellow": data.get("color3", "#ffff00"),
            "blue": data.get("color4", "#0000ff"),
            "magenta": data.get("color5", "#ff00ff"),
            "cyan": data.get("color6", "#00ffff"),
            "white": data.get("color7", "#ffffff"),
            "bright_black": data.get("color8", "#555555"),
            "bright_red": data.get("color9", "#ff5555"),
            "bright_green": data.get("color10", "#55ff55"),
            "bright_yellow": data.get("color11", "#ffff55"),
            "bright_blue": data.get("color12", "#5555ff"),
            "bright_magenta": data.get("color13", "#ff55ff"),
            "bright_cyan": data.get("color14", "#55ffff"),
            "bright_white": data.get("color15", "#ffffff"),
        }
        return {**defaults, **colors}
    except Exception:
        return defaults

COLORS = load_theme_colors()

SECTION_COLORS = {
    "Storage": {"icon": COLORS["blue"], "text": COLORS["blue"]},
}

COLOR_TABLE = [
    {"color": COLORS["blue"],           "mem_storage": (0.0, 10),  "drive_temp": (0, 35)},
    {"color": COLORS["cyan"],           "mem_storage": (10.0, 20), "drive_temp": (36, 45)},
    {"color": COLORS["green"],          "mem_storage": (20.0, 40), "drive_temp": (46, 54)},
    {"color": COLORS["yellow"],         "mem_storage": (40.0, 60), "drive_temp": (55, 60)},
    {"color": COLORS["bright_yellow"],  "mem_storage": (60.0, 80), "drive_temp": (61, 70)},
    {"color": COLORS["bright_red"],     "mem_storage": (80.0, 90), "drive_temp": (71, 80)},
    {"color": COLORS["red"],            "mem_storage": (90.0,100), "drive_temp": (81, 999)}
]

def get_color(value, metric_type):
    if value is None: return "#ffffff"
    try: value = float(value)
    except ValueError: return "#ffffff"
    for entry in COLOR_TABLE:
        if metric_type in entry:
            low, high = entry[metric_type]
            if low <= value <= high: return entry["color"]
    return COLOR_TABLE[-1]["color"]

# ---------------------------------------------------
# HISTORY & UTILS
# ---------------------------------------------------
def format_compact(val, suffix=""):
    if val is None: return f"0{suffix}"
    try: val = float(val)
    except: return f"0{suffix}"
    if val < 1024: return f"{val:.0f}{suffix}"
    val /= 1024
    if val < 1024: return f"{val:.1f}K{suffix}"
    val /= 1024
    if val < 1024: return f"{val:.1f}M{suffix}"
    val /= 1024
    return f"{val:.1f}G{suffix}"

def load_history():
    try:
        with open(HISTORY_FILE, 'rb') as f:
            data = pickle.load(f)
            if not isinstance(data, dict): return {'io': {}, 'timestamp': 0}
            return data
    except: return {'io': {}, 'timestamp': 0}

def save_history(data):
    try:
        with open(HISTORY_FILE, 'wb') as f: pickle.dump(data, f)
    except: pass

# ---------------------------------------------------
# HARDWARE SENSORS
# ---------------------------------------------------
def get_nvme_pci_mapping():
    """Map NVMe device names to sensors-compatible PCI addresses."""
    mapping = {}
    try:
        for dev in os.listdir("/sys/class/nvme"):
            try:
                # Read the PCI address from the device path
                dev_path = f"/sys/class/nvme/{dev}/device"
                if os.path.islink(dev_path):
                    pci_addr = os.path.basename(os.readlink(dev_path))
                    # Convert "0000:01:00.0" -> "0100" format used by sensors
                    # Format is: domain:bus:device.function -> busdevice (without leading zeros in bus)
                    parts = pci_addr.split(':')
                    if len(parts) == 3:
                        bus = parts[1].lstrip('0') or '0'
                        device_fn = parts[2].replace('.', '')
                        sensors_key = f"{bus}{device_fn}"
                        mapping[dev] = sensors_key
            except: pass
    except: pass
    return mapping

def resolve_device_to_physical(device_path):
    """Resolve a device path (including mapper/LVM/crypt) to physical device."""
    disk_name = os.path.basename(device_path)
    
    # Handle /dev/mapper/ devices - resolve symlink
    if device_path.startswith("/dev/mapper/") or disk_name in os.listdir("/dev/mapper/"):
        try:
            # Get the actual dm-* device
            real_path = os.path.realpath(device_path)
            disk_name = os.path.basename(real_path)
        except: pass
    
    # Handle dm-* devices
    if disk_name.startswith("dm-"):
        try:
            slaves = os.listdir(f"/sys/class/block/{disk_name}/slaves")
            if slaves:
                disk_name = slaves[0]
        except: pass
    
    return disk_name

def get_drive_temp(mountpoint):
    """
    Attempts to find drive temperature via psutil -> device -> hwmon/smartctl.
    """
    try:
        partitions = psutil.disk_partitions()
        partition = next((p for p in partitions if p.mountpoint == mountpoint), None)
        if not partition: return None
        
        # Resolve to physical device
        disk_name = resolve_device_to_physical(partition.device)

        # Get base device name
        base_name = disk_name
        if base_name.startswith("nvme"):
            base_name = re.sub(r'p\d+$', '', base_name)
        else:
            base_name = re.sub(r'\d+$', '', base_name)
            
        # Try sensors command (lm_sensors) - NVMe PCI mapping
        try:
            nvme_pci_map = get_nvme_pci_mapping()
            output = subprocess.check_output(["sensors", "-j"], text=True, stderr=subprocess.DEVNULL)
            data = json.loads(output)
            
            # For NVMe, map device name to PCI address
            if base_name.startswith("nvme"):
                pci_addr = nvme_pci_map.get(base_name)
                if pci_addr:
                    # Look for nvme-pci-<address> in sensors
                    sensor_key = f"nvme-pci-{pci_addr}"
                    if sensor_key in data:
                        # Get Composite temperature
                        for sub_k, sub_v in data[sensor_key].items():
                            if isinstance(sub_v, dict) and "temp1_input" in sub_v:
                                return int(sub_v["temp1_input"])
            else:
                # For SATA drives, try to find matching sensor
                for key, val in data.items():
                    if base_name in key.lower():
                        for sub_k, sub_v in val.items():
                            if isinstance(sub_v, dict) and "temp1_input" in sub_v:
                                return int(sub_v["temp1_input"])
        except Exception as e:
            pass

        # Fallback: Try all nvme-pci sensors (for NVMe drives)
        try:
            output = subprocess.check_output(["sensors", "-j"], text=True, stderr=subprocess.DEVNULL)
            data = json.loads(output)
            if base_name.startswith("nvme"):
                # Try any nvme-pci sensor
                for key, val in data.items():
                    if key.startswith("nvme-pci-"):
                        for sub_k, sub_v in val.items():
                            if isinstance(sub_v, dict) and "temp1_input" in sub_v:
                                return int(sub_v["temp1_input"])
        except: pass

        # Fallback: smartctl (requires sudo NOPASSWD)
        try:
            cmd = ["sudo", "-n", "smartctl", "-A", f"/dev/{base_name}", "-j"]
            result = subprocess.run(cmd, text=True, capture_output=True, timeout=5)
            if result.stdout and result.returncode == 0:
                data = json.loads(result.stdout)
                return data.get("temperature", {}).get("current")
        except: pass

    except Exception:
        pass
    return None

def get_smart_info(mountpoint):
    """
    Fetches basic health info via smartctl.
    """
    health, lifespan, tbw = "N/A", "N/A", "N/A"
    try:
        partitions = psutil.disk_partitions()
        partition = next((p for p in partitions if p.mountpoint == mountpoint), None)
        if not partition: return health, lifespan, tbw
        
        # Resolve to physical device
        disk_name = resolve_device_to_physical(partition.device)
        
        # Get base device name
        if disk_name.startswith("nvme"):
            disk_name = re.sub(r'p\d+$', '', disk_name)
        else:
            disk_name = re.sub(r'\d+$', '', disk_name)
        
        cmd = ["sudo", "-n", "smartctl", "-a", "-j", f"/dev/{disk_name}"]
        result = subprocess.run(cmd, text=True, capture_output=True, timeout=5)
        if result.stdout and result.returncode == 0:
            data = json.loads(result.stdout)
            passed = data.get("smart_status", {}).get("passed")
            health = "OK" if passed else "FAIL" if passed is False else "N/A"
            
            # NVMe specific
            if "nvme_smart_health_information_log" in data:
                nvme = data["nvme_smart_health_information_log"]
                used = nvme.get("percentage_used")
                if used is not None: lifespan = f"{max(0, 100 - used)}%"
                duw = nvme.get("data_units_written")
                if duw: tbw = f"{(duw * 512000) / 1e12:.1f} TB"
            # ATA/SATA smart data
            elif "ata_smart_attributes" in data:
                # For regular SSDs/HDDs, try to estimate from power-on hours or other attrs
                attrs = {a.get("id"): a for a in data.get("ata_smart_attributes", {}).get("table", [])}
                # Power on hours (id 9)
                if 9 in attrs:
                    poh = attrs[9].get("raw", {}).get("value", 0)
                    # Rough estimate: assume 5 year lifespan = 43800 hours
                    if poh > 0:
                        lifespan_est = max(0, 100 - (poh / 43800 * 100))
                        lifespan = f"~{lifespan_est:.0f}%"
                # Total LBAs written (id 241) - rough TBW estimate
                if 241 in attrs:
                    lba_written = attrs[241].get("raw", {}).get("value", 0)
                    # Assuming 512 bytes per sector
                    tbw_calc = (lba_written * 512) / (1024**4)
                    tbw = f"~{tbw_calc:.1f} TB"
    except: pass
    return health, lifespan, tbw

# ---------------------------------------------------
# MAIN LOGIC
# ---------------------------------------------------
def get_drives():
    drives = []
    seen_devices = set()  # Track physical devices to avoid duplicates
    
    # Auto-detect physical drives
    for p in psutil.disk_partitions():
        if any(x in p.mountpoint for x in ['/snap', '/boot', '/docker', '/run', '/sys', '/proc']): continue
        if any(x in p.device for x in ['/loop']): continue
        
        # Skip if fstype is empty or not a real filesystem
        if not p.fstype or p.fstype not in ['ext4', 'btrfs', 'xfs', 'ntfs', 'vfat', 'apfs', 'zfs', 'exfat', 'crypto_LUKS']:
            continue
        
        # Get physical device name for deduplication
        physical_dev = resolve_device_to_physical(p.device)
        
        # Normalize device name (remove partition numbers)
        if physical_dev.startswith("nvme"):
            base_dev = re.sub(r'p\d+$', '', physical_dev)
        else:
            base_dev = re.sub(r'\d+$', '', physical_dev)
        
        # Skip if we've already seen this physical device
        if base_dev in seen_devices:
            continue
        seen_devices.add(base_dev)
            
        # Determine drive name using custom mapping or auto-detection
        if base_dev in DRIVE_NAME_MAPPING:
            name = DRIVE_NAME_MAPPING[base_dev]
        elif p.mountpoint == "/":
            name = "Root"
        elif p.mountpoint.startswith("/mnt/"):
            name = os.path.basename(p.mountpoint)
        elif p.mountpoint == "/home":
            name = "Home"
        elif p.mountpoint == "/var/log":
            name = "Root"
        else:
            name = os.path.basename(p.mountpoint) if p.mountpoint else "Unknown"
        
        # Detect if it's SSD or HDD
        icon = SSD_ICON  # Default
        try:
            # Check if rotational (HDD=1, SSD/NVMe=0 or not present)
            rotational_path = f"/sys/class/block/{base_dev}/queue/rotational"
            if os.path.exists(rotational_path):
                with open(rotational_path, 'r') as f:
                    if f.read().strip() == "1":
                        icon = HDD_ICON
        except: pass
        
        drives.append((name, p.mountpoint, icon))
    return drives

def main():
    history = load_history()
    last_io = history.get('io', {})
    last_time = history.get('timestamp', 0)
    current_time = time.time()
    
    try: current_io = psutil.disk_io_counters(perdisk=True)
    except: current_io = {}

    drives = get_drives()
    storage_entries = []
    
    # Map mountpoints to device names for I/O lookup
    try:
        partitions = psutil.disk_partitions()
        mount_map = {p.mountpoint: os.path.basename(p.device) for p in partitions}
    except: mount_map = {}

    root_usage = 0

    for name, mountpoint, icon in drives:
        try:
            usage = psutil.disk_usage(mountpoint)
            used_pct = int(usage.percent)
            total_tb = usage.total / (1024**4)
            
            if mountpoint == "/": root_usage = used_pct
            
            temp = get_drive_temp(mountpoint)
            health, lifespan, tbw = get_smart_info(mountpoint)
            
            # I/O Speed - resolve to physical device for I/O counters
            r_spd, w_spd = 0, 0
            partition = next((p for p in psutil.disk_partitions() if p.mountpoint == mountpoint), None)
            if partition:
                dev_name = resolve_device_to_physical(partition.device)
                # Remove partition number for I/O lookup
                if dev_name.startswith("nvme"):
                    dev_name = re.sub(r'p\d+$', '', dev_name)
                else:
                    dev_name = re.sub(r'\d+$', '', dev_name)
            else:
                dev_name = None
            if dev_name and dev_name in current_io and dev_name in last_io:
                curr, prev = current_io[dev_name], last_io[dev_name]
                dt = current_time - last_time
                if dt > 0:
                    r_spd = (curr.read_bytes - prev.read_bytes) / dt
                    w_spd = (curr.write_bytes - prev.write_bytes) / dt

            storage_entries.append({
                "name": name, "icon": icon, "total": total_tb, "pct": used_pct,
                "temp": temp, "health": health, "lifespan": lifespan, "tbw": tbw,
                "r_spd": r_spd, "w_spd": w_spd
            })
        except: continue

    # ---------------------------------------------------
    # TOOLTIP - Dashboard Style
    # ---------------------------------------------------
    lines = []
    lines.append(f"<span foreground='{SECTION_COLORS['Storage']['text']}'>{SSD_ICON} Storage:</span>")
    lines.append(f"<span foreground='{COLORS['white']}'>{'─' * TOOLTIP_WIDTH}</span>")

    for entry in storage_entries:
        c_temp = get_color(entry['temp'], "drive_temp") if entry['temp'] else COLORS["bright_black"]
        c_usage = get_color(entry['pct'], "mem_storage")
        
        # Header: Icon Name Size
        size_str = f"{entry['total']:.1f}TB"
        lines.append(f"{entry['icon']} <span foreground='{COLORS['white']}'><b>{entry['name']}</b></span> - {size_str}")
        
        # Temperature line with thermometer icon
        temp_str = f"{entry['temp']}°C" if entry['temp'] else "N/A"
        lines.append(f"<span foreground='{c_temp}'></span> <span foreground='{c_temp}'>{temp_str}</span>")
        
        # Lifespan / TBW line with hourglass icon
        if entry['lifespan'] != "N/A":
            lifespan_str = f"Lifespan: {entry['lifespan']}"
            lines.append(f"<span foreground='{COLORS['yellow']}'></span> <span foreground='{COLORS['white']}'>{lifespan_str}</span>")
        elif entry['tbw'] != "N/A":
            tbw_str = f"TB Written: {entry['tbw']}"
            lines.append(f"<span foreground='{COLORS['yellow']}'></span> <span foreground='{COLORS['white']}'>{tbw_str}</span>")
        
        # Health line with checkmark icon
        health_c = COLORS['green'] if entry['health'] == "OK" else COLORS['red'] if entry['health'] == "FAIL" else COLORS["bright_black"]
        health_icon = "" if entry['health'] == "OK" else "" if entry['health'] == "FAIL" else ""
        lines.append(f"<span foreground='{health_c}'>{health_icon}</span> <span foreground='{COLORS['white']}'>Health</span> <span foreground='{health_c}'>{health_icon} {entry['health']}</span>")
        
        # I/O Speed line with arrows
        rs = format_compact(entry['r_spd'], "/s")
        ws = format_compact(entry['w_spd'], "/s")
        lines.append(f"<span size='small'><span foreground='{COLORS['green']}'></span> Write: <span foreground='{COLORS['green']}'>{ws}</span>  <span foreground='{COLORS['blue']}'></span> Read: <span foreground='{COLORS['blue']}'>{rs}</span></span>")
        
        # Progress bar - use blocks for cleaner look
        bar_w = 25
        filled = int((entry['pct'] / 100) * bar_w)
        # Use different colors based on usage percentage
        if entry['pct'] < 50:
            bar_color = COLORS['green']
        elif entry['pct'] < 80:
            bar_color = COLORS['yellow']
        else:
            bar_color = COLORS['red']
        
        bar = f"<span foreground='{bar_color}'>{''.join(['█']*filled)}</span><span foreground='{COLORS['bright_black']}'>{''.join(['░']*(bar_w-filled))}</span>"
        lines.append(f"{SSD_ICON} {bar} <span foreground='{bar_color}'>{entry['pct']}%</span>")
        lines.append("")


    save_history({'io': current_io, 'timestamp': current_time})

    print(json.dumps({
        "text": f"{SSD_ICON} <span foreground='{get_color(root_usage,'mem_storage')}'>{root_usage}%</span>",
        "tooltip": f"<span size='12000'>{'\n'.join(lines)}</span>",
        "markup": "pango",
        "class": "storage"
    }))

if __name__ == "__main__":
    main()
