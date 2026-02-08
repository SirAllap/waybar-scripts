#!/usr/bin/env python3
# ----------------------------------------------------------------------------
# WAYBAR SYSTEM STATUS MODULE
# ----------------------------------------------------------------------------
# Comprehensive system overview showing all hardware stats in one tooltip
# ----------------------------------------------------------------------------

import json
import psutil
import subprocess
import os
import re
import pathlib
from datetime import timedelta

try:
    import tomllib
except ImportError:
    tomllib = None

# ---------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------
SYS_ICON = ""
TOOLTIP_WIDTH = 60

# ---------------------------------------------------
# THEME & COLORS
# ---------------------------------------------------
def load_theme_colors():
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

# ---------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------
def get_color(value, thresholds):
    """Get color based on value and thresholds"""
    if value is None:
        return COLORS["white"]
    try:
        value = float(value)
    except:
        return COLORS["white"]
    
    for threshold, color in thresholds:
        if value <= threshold:
            return color
    return thresholds[-1][1] if thresholds else COLORS["white"]

def format_bytes(bytes_val):
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"

def get_uptime():
    """Get system uptime"""
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
            return str(timedelta(seconds=int(uptime_seconds)))
    except:
        return "Unknown"

def get_cpu_info():
    """Get CPU information"""
    info = {"model": "Unknown", "cores": 0, "threads": 0, "temp": 0, "usage": 0}
    
    # Model
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if 'model name' in line:
                    info["model"] = line.split(':')[1].strip()
                    break
    except:
        pass
    
    # Cores and threads
    info["cores"] = psutil.cpu_count(logical=False) or 0
    info["threads"] = psutil.cpu_count(logical=True) or 0
    
    # Usage
    info["usage"] = psutil.cpu_percent(interval=0.1)
    
    # Temperature
    try:
        temps = psutil.sensors_temperatures()
        if 'coretemp' in temps:
            info["temp"] = max(t.current for t in temps['coretemp'])
        elif 'k10temp' in temps:
            info["temp"] = temps['k10temp'][0].current
    except:
        pass
    
    return info

def get_gpu_info():
    """Get GPU information"""
    info = {"name": "GPU", "temp": 0, "usage": 0, "vram_used": 0, "vram_total": 0}
    
    # AMD GPU
    drm_path = "/sys/class/drm/card0/device"
    if not os.path.exists(f"{drm_path}/mem_info_vram_total"):
        drm_path = "/sys/class/drm/card1/device"
    
    try:
        # Temperature
        hwmon_dirs = [d for d in os.listdir(f"{drm_path}/hwmon") if d.startswith("hwmon")]
        if hwmon_dirs:
            hwmon = hwmon_dirs[0]
            with open(f"{drm_path}/hwmon/{hwmon}/temp1_input", "r") as f:
                info["temp"] = int(f.read().strip()) // 1000
        
        # Usage
        with open(f"{drm_path}/gpu_busy_percent", "r") as f:
            info["usage"] = int(f.read().strip())
        
        # VRAM
        with open(f"{drm_path}/mem_info_vram_used", "r") as f:
            info["vram_used"] = int(f.read().strip()) // 1024 // 1024
        with open(f"{drm_path}/mem_info_vram_total", "r") as f:
            info["vram_total"] = int(f.read().strip()) // 1024 // 1024
        
        info["name"] = "AMD GPU"
    except:
        pass
    
    return info

def get_memory_info():
    """Get memory information"""
    mem = psutil.virtual_memory()
    return {
        "total": mem.total // (1024**3),
        "used": mem.used // (1024**3),
        "percent": mem.percent,
        "available": mem.available // (1024**3)
    }

def get_storage_info():
    """Get storage information"""
    drives = []
    for p in psutil.disk_partitions():
        if any(x in p.mountpoint for x in ['/snap', '/boot', '/docker', '/run', '/sys', '/proc']):
            continue
        if any(x in p.device for x in ['/loop']):
            continue
        
        try:
            usage = psutil.disk_usage(p.mountpoint)
            name = "Root" if p.mountpoint == "/" else os.path.basename(p.mountpoint)
            if name in ['hdd', 'intel-ssd']:
                name = name.replace('-', ' ').title()
            drives.append({
                "name": name,
                "mount": p.mountpoint,
                "used": usage.used // (1024**3),
                "total": usage.total // (1024**3),
                "percent": usage.percent
            })
        except:
            continue
    return drives

def get_network_info():
    """Get network information"""
    info = {"down": 0, "up": 0, "ssid": "Disconnected"}
    try:
        # Get IO stats
        io = psutil.net_io_counters()
        info["down"] = io.bytes_recv
        info["up"] = io.bytes_sent
        
        # Get WiFi SSID
        result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            info["ssid"] = result.stdout.strip()
    except:
        pass
    return info

def get_system_info():
    """Get general system information"""
    return {
        "hostname": os.uname().nodename,
        "kernel": os.uname().release,
        "uptime": get_uptime()
    }

# ---------------------------------------------------
# MAIN
# ---------------------------------------------------
def main():
    # Gather all info
    cpu = get_cpu_info()
    gpu = get_gpu_info()
    mem = get_memory_info()
    storage = get_storage_info()
    net = get_network_info()
    sys = get_system_info()
    
    # Calculate overall health score
    health_score = 100
    if cpu["temp"] > 80: health_score -= 20
    if cpu["usage"] > 90: health_score -= 10
    if gpu["temp"] > 80: health_score -= 20
    if mem["percent"] > 90: health_score -= 10
    for drive in storage:
        if drive["percent"] > 90: health_score -= 10
    
    # Color for health score
    health_color = get_color(100 - health_score, [
        (20, COLORS["green"]),
        (50, COLORS["yellow"]),
        (100, COLORS["red"])
    ])
    
    # Build tooltip
    lines = []
    border = f"<span foreground='{COLORS['bright_black']}'>{'─' * TOOLTIP_WIDTH}</span>"
    
    # Header
    lines.append(f"<span foreground='{COLORS['cyan']}'>{SYS_ICON}</span> <span foreground='{COLORS['white']}'><b>System Overview</b></span>")
    lines.append(f"<span foreground='{COLORS['white']}'>{sys['hostname']}</span> | Kernel: {sys['kernel']}")
    lines.append(f"Uptime: <span foreground='{COLORS['yellow']}'>{sys['uptime']}</span>")
    lines.append(border)
    
    # CPU Section
    cpu_temp_color = get_color(cpu["temp"], [(60, COLORS["green"]), (75, COLORS["yellow"]), (100, COLORS["red"])])
    cpu_usage_color = get_color(cpu["usage"], [(50, COLORS["green"]), (75, COLORS["yellow"]), (100, COLORS["red"])])
    lines.append(f"<span foreground='{COLORS['blue']}'></span> <b>CPU:</b> {cpu['model'][:30]}")
    lines.append(f"   Cores: {cpu['cores']}/{cpu['threads']} | Temp: <span foreground='{cpu_temp_color}'>{cpu['temp']}°C</span> | Usage: <span foreground='{cpu_usage_color}'>{cpu['usage']}%</span>")
    lines.append("")
    
    # GPU Section
    gpu_temp_color = get_color(gpu["temp"], [(60, COLORS["green"]), (75, COLORS["yellow"]), (100, COLORS["red"])])
    gpu_usage_color = get_color(gpu["usage"], [(50, COLORS["green"]), (75, COLORS["yellow"]), (100, COLORS["red"])])
    vram_pct = (gpu["vram_used"] / gpu["vram_total"] * 100) if gpu["vram_total"] > 0 else 0
    lines.append(f"<span foreground='{COLORS['magenta']}'>󰢮</span> <b>GPU:</b> {gpu['name']}")
    lines.append(f"   Temp: <span foreground='{gpu_temp_color}'>{gpu['temp']}°C</span> | Usage: <span foreground='{gpu_usage_color}'>{gpu['usage']}%</span> | VRAM: {gpu['vram_used']}/{gpu['vram_total']} MB ({vram_pct:.0f}%)")
    lines.append("")
    
    # Memory Section
    mem_color = get_color(mem["percent"], [(50, COLORS["green"]), (75, COLORS["yellow"]), (100, COLORS["red"])])
    lines.append(f"<span foreground='{COLORS['green']}'></span> <b>Memory:</b> {mem['used']}/{mem['total']} GB (<span foreground='{mem_color}'>{mem['percent']}%</span>)")
    lines.append(f"   Available: {mem['available']} GB")
    lines.append("")
    
    # Storage Section
    lines.append(f"<span foreground='{COLORS['yellow']}'></span> <b>Storage:</b>")
    for drive in storage:
        drive_color = get_color(drive["percent"], [(70, COLORS["green"]), (85, COLORS["yellow"]), (100, COLORS["red"])])
        lines.append(f"   {drive['name']}: {drive['used']}/{drive['total']} GB (<span foreground='{drive_color}'>{drive['percent']}%</span>)")
    lines.append("")
    
    # Network Section
    lines.append(f"<span foreground='{COLORS['cyan']}'></span> <b>Network:</b> {net['ssid']}")
    lines.append(f"   Down: {format_bytes(net['down'])} | Up: {format_bytes(net['up'])}")
    lines.append(border)
    
    # Health Score
    lines.append(f"<span foreground='{health_color}'>●</span> System Health: <span foreground='{health_color}'>{health_score}%</span>")
    lines.append("<span size='small'>🖱️ LMB: System Monitor | 🖱️ RMB: Terminal</span>")
    
    # Text display (compact)
    text = f"{SYS_ICON} <span foreground='{health_color}'>{health_score}%</span>"
    
    print(json.dumps({
        "text": text,
        "tooltip": "\n".join(lines),
        "markup": "pango",
        "class": "system-status"
    }))

if __name__ == "__main__":
    main()
