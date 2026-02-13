#!/usr/bin/env python3
# ----------------------------------------------------------------------------
# WAYBAR CPU MODULE - Clean Version for Omarchy
# ----------------------------------------------------------------------------
# Features:
# - Real-time CPU monitoring with temperature, frequency, and power
# - Per-core visualization
# - Top processes list
# - Zombie process detection and killing (RMB)
# ----------------------------------------------------------------------------

import json
import psutil
import subprocess
import re
import os
import time
import shutil
import pickle
import signal
import argparse
from collections import deque
import math
import pathlib
import glob

try:
    import tomllib
except ImportError:
    tomllib = None

def send_notification(title, message, urgency="normal"):
    """Send desktop notification"""
    try:
        subprocess.run(
            ["notify-send", "-u", urgency, "-t", "5000", title, message],
            capture_output=True,
            check=False
        )
    except:
        pass

def find_zombie_processes():
    """Find all zombie processes"""
    zombies = []
    try:
        for proc in psutil.process_iter(['pid', 'ppid', 'name', 'status']):
            try:
                if proc.info['status'] == psutil.STATUS_ZOMBIE:
                    zombies.append({
                        'pid': proc.info['pid'],
                        'ppid': proc.info['ppid'],
                        'name': proc.info['name']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except:
        pass
    return zombies

def kill_zombie_processes():
    """Kill zombie processes by killing their parent processes"""
    zombies = find_zombie_processes()
    killed_count = 0
    failed_count = 0
    parent_pids = set()
    
    # Collect unique parent PIDs
    for zombie in zombies:
        parent_pids.add(zombie['ppid'])
    
    # Try to kill parent processes
    for ppid in parent_pids:
        try:
            parent = psutil.Process(ppid)
            # Send SIGTERM first
            parent.terminate()
            try:
                parent.wait(timeout=3)
                killed_count += 1
            except psutil.TimeoutExpired:
                # Force kill if graceful termination fails
                parent.kill()
                killed_count += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            failed_count += 1
            continue
    
    return killed_count, failed_count, len(zombies)

CPU_ICON_GENERAL = "\uf2db"
HISTORY_FILE = "/tmp/waybar_cpu_history.pkl"
TOOLTIP_WIDTH = 50

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
SECTION_COLORS = {"CPU": {"icon": COLORS["red"], "text": COLORS["red"]}}

COLOR_TABLE = [
    {"color": COLORS["blue"],           "cpu_gpu_temp": (0, 35),   "cpu_power": (0.0, 30)},
    {"color": COLORS["cyan"],           "cpu_gpu_temp": (36, 45),  "cpu_power": (31.0, 60)},
    {"color": COLORS["green"],          "cpu_gpu_temp": (46, 54),  "cpu_power": (61.0, 90)},
    {"color": COLORS["yellow"],         "cpu_gpu_temp": (55, 65),  "cpu_power": (91.0, 120)},
    {"color": COLORS["bright_yellow"],  "cpu_gpu_temp": (66, 75),  "cpu_power": (121.0,150)},
    {"color": COLORS["bright_red"],     "cpu_gpu_temp": (76, 85),  "cpu_power": (151.0,180)},
    {"color": COLORS["red"],            "cpu_gpu_temp": (86, 999), "cpu_power": (181.0,999)}
]

def get_color(value, metric_type):
    if value is None: return "#ffffff"
    try: value = float(value)
    except ValueError: return "#ffffff"
    for entry in COLOR_TABLE:
        if metric_type in entry:
            low, high = entry[metric_type]
            if low <= value <= high: 
                return entry["color"]
    return COLOR_TABLE[-1]["color"]

def get_cpu_name():
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if "model name" in line:
                    full_name = line.split(":")[1].strip()
                    short_name = re.sub(r'\s+\d+-Core\s+Processor.*$', '', full_name)
                    return short_name
    except:
        pass
    return "Unknown CPU"

def get_rapl_path():
    base = "/sys/class/powercap"
    if not os.path.exists(base): 
        return None
    paths = glob.glob(f"{base}/*/energy_uj")
    for p in paths:
        if "intel-rapl:0" in p or "package" in p:
            return p
    return paths[0] if paths else None

def load_history():
    try:
        with open(HISTORY_FILE, 'rb') as f:
            return pickle.load(f)
    except:
        return {'cpu': deque(maxlen=TOOLTIP_WIDTH), 'per_core': {}}

def save_history(cpu_hist, per_core_hist):
    try:
        with open(HISTORY_FILE, 'wb') as f:
            pickle.dump({'cpu': cpu_hist, 'per_core': per_core_hist}, f)
    except: 
        pass

def generate_output():
    """Generate waybar output"""
    history = load_history()
    cpu_history = history.get('cpu', deque(maxlen=TOOLTIP_WIDTH))
    per_core_history = history.get('per_core', {})

    cpu_name = get_cpu_name()
    max_cpu_temp = 0

    try:
        temps = psutil.sensors_temperatures() or {}
        for label in ["k10temp", "coretemp", "zenpower"]:
            if label in temps:
                for t in temps[label]:
                    if t.current > max_cpu_temp:
                        max_cpu_temp = int(t.current)
    except: 
        pass

    current_freq = max_freq = 0
    try:
        cpu_info = psutil.cpu_freq(percpu=False)
        if cpu_info:
            current_freq = cpu_info.current or 0
            max_freq = cpu_info.max or 0
    except: 
        pass

    cpu_power = 0.0
    rapl_path = get_rapl_path()
    if rapl_path:
        try:
            with open(rapl_path, "r") as f: 
                energy1 = int(f.read().strip())
            time.sleep(0.05)
            with open(rapl_path, "r") as f: 
                energy2 = int(f.read().strip())
            delta = energy2 - energy1
            if delta < 0: 
                max_f = os.path.join(os.path.dirname(rapl_path), "max_energy_range_uj")
                if os.path.exists(max_f):
                    with open(max_f, "r") as f: 
                        max_e = int(f.read().strip())
                    delta = (max_e + energy2) - energy1
                else:
                    delta = (2**32 + energy2) - energy1
            cpu_power = (delta / 1_000_000) / 0.05
        except: 
            pass

    cpu_percent = psutil.cpu_percent(interval=0.1)
    cpu_history.append(cpu_percent)

    per_core = psutil.cpu_percent(interval=0.1, percpu=True)
    decay_factor = 0.95
    for i, usage in enumerate(per_core):
        if i not in per_core_history:
            per_core_history[i] = usage
        else:
            per_core_history[i] = (per_core_history[i] * decay_factor) + (usage * (1 - decay_factor))

    def get_core_color(usage):
        if usage < 20: 
            return "#81c8be"
        elif usage < 40: 
            return "#a6d189"
        elif usage < 60: 
            return "#e5c890"
        elif usage < 80: 
            return "#ef9f76"
        elif usage < 95: 
            return "#ea999c"
        else: 
            return "#e78284"

    # Count zombies
    zombie_count = len(find_zombie_processes())

    tooltip_lines = []
    tooltip_lines.append(
        f"<span foreground='{SECTION_COLORS['CPU']['icon']}'>{CPU_ICON_GENERAL}</span> "
        f"<span foreground='{SECTION_COLORS['CPU']['text']}'>CPU</span> - {cpu_name}"
    )

    cpu_rows = [
        ("", f"Clock Speed: <span foreground='{get_color((current_freq/max_freq*100) if max_freq > 0 else 0, 'cpu_power')}'>{current_freq/1000:.2f} GHz</span> / {max_freq/1000:.2f} GHz"),
        ("\uf2c7", f"Temperature: <span foreground='{get_color(max_cpu_temp,'cpu_gpu_temp')}'>{max_cpu_temp}°C</span>"),
        ("\uf0e7", f"Power: <span foreground='{get_color(cpu_power,'cpu_power')}'>{cpu_power:.1f} W</span>"),
        ("󰓅", f"Utilization: <span foreground='{get_color(cpu_percent,'cpu_power')}'>{cpu_percent:.0f}%</span>")
    ]
    
    # Add zombie count if any
    if zombie_count > 0:
        cpu_rows.append(("󰀨", f"Zombies: <span foreground='{COLORS['red']}'>{zombie_count}</span>"))

    max_line_len = max(len(re.sub(r'<.*?>','',line_text)) for _, line_text in cpu_rows) + 5
    max_line_len = max(max_line_len, 29)
    tooltip_lines.append("─" * max_line_len)
    for icon, text_row in cpu_rows:
        tooltip_lines.append(f"{icon} | {text_row}")

    cpu_viz_width = 25
    center_padding = " " * int((max_line_len - cpu_viz_width) // 2)
    substrate_color = get_color(max_cpu_temp, 'cpu_gpu_temp')
    border_color = COLORS['white']

    tooltip_lines.append("")
    tooltip_lines.append(f"{center_padding}  <span foreground='{border_color}'>\u256d\u2500\u2500\u2518\u2514\u2500\u2500\u2500\u2500\u2518\u283f\u2514\u2500\u2500\u2500\u2500\u2500\u2518\u2514\u2500\u256e</span>")
    tooltip_lines.append(f"{center_padding}  <span foreground='{border_color}'>\u2502</span><span foreground='{substrate_color}'>\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591</span><span foreground='{border_color}'>\u2502</span>")
    tooltip_lines.append(f"{center_padding}  <span foreground='{border_color}'>\u2518</span><span foreground='{substrate_color}'>\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591</span><span foreground='{border_color}'>\u2514</span>")

    num_cores = len(per_core)
    cols = 4
    rows = math.ceil(num_cores / cols)

    for r in range(rows):
        line_parts = [f"{center_padding}  <span foreground='{border_color}'>\u2502</span><span foreground='{substrate_color}'>\u2591\u2591</span>"]
        for c in range(cols):
            idx = r * cols + c
            if idx < num_cores:
                usage = per_core[idx]
                color = get_core_color(usage)
                circle = "\u25cf" if usage >= 10 else "\u25cb"
                line_parts.append(f"<span foreground='{border_color}'>[</span><span foreground='{color}'>{circle}</span><span foreground='{border_color}'>]</span>")
            else:
                line_parts.append(f"<span foreground='{substrate_color}'>\u2591\u2591\u2591</span>")
            if c < cols - 1:
                line_parts.append(f"<span foreground='{substrate_color}'>\u2591</span>")
        line_parts.append(f"<span foreground='{substrate_color}'>\u2591\u2591</span><span foreground='{border_color}'>\u2502</span>")
        tooltip_lines.append("".join(line_parts))

    tooltip_lines.append(f"{center_padding}  <span foreground='{border_color}'>\u2510</span><span foreground='{substrate_color}'>\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591</span><span foreground='{border_color}'>\u250c</span>")
    tooltip_lines.append(f"{center_padding}  <span foreground='{border_color}'>\u2502</span><span foreground='{substrate_color}'>\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591\u2591</span><span foreground='{border_color}'>\u2502</span>")
    tooltip_lines.append(f"{center_padding}  <span foreground='{border_color}'>\u2570\u2500\u2500\u2510\u250c\u2500\u2500\u2500\u2500\u2510\u28f6\u250c\u2500\u2500\u2500\u2500\u2500\u2510\u250c\u2500\u256f</span>")

    tooltip_lines.append("")
    tooltip_lines.append("Top Current Processes:")
    try:
        ps_cmd = ["ps", "-eo", "pcpu,comm,args", "--sort=-pcpu", "--no-headers"]
        ps_output = subprocess.check_output(ps_cmd, text=True).strip()
        count = 0
        for line in ps_output.split('\n'):
            if count >= 3: 
                break
            parts = line.strip().split(maxsplit=2)
            if len(parts) >= 2:
                try:
                    usage = float(parts[0])
                    name = parts[1]
                    if "waybar" in parts[2] if len(parts)>2 else "": 
                        continue
                    if len(name) > 15: 
                        name = name[:14] + "\u2026"
                    color = get_core_color(usage)
                    tooltip_lines.append(f" \u2022 {name:<15} <span foreground='{color}'>\uf2db {usage:>5.1f}%</span>")
                    count += 1
                except: 
                    continue
    except: 
        pass

    tooltip_lines.append("")
    tooltip_lines.append(f"<span foreground='{COLORS['white']}'>{'\u2508' * max_line_len}</span>")
    tooltip_lines.append("\ud83d\uddb1\ufe0f LMB: Btop | RMB: Kill Zombie Proc.")

    save_history(cpu_history, per_core_history)

    return {
        "text": f"{CPU_ICON_GENERAL} <span foreground='{get_color(max_cpu_temp,'cpu_gpu_temp')}'>{max_cpu_temp}\u00b0C</span>",
        "tooltip": f"<span size='12000'>{'\n'.join(tooltip_lines)}</span>",
        "markup": "pango",
        "class": "cpu"
    }

def main():
    parser = argparse.ArgumentParser(description="Waybar CPU Module")
    parser.add_argument("--kill-zombies", action="store_true",
                       help="Kill zombie processes and show notification")
    args = parser.parse_args()
    
    if args.kill_zombies:
        killed, failed, total = kill_zombie_processes()
        if total > 0:
            send_notification(
                "\ud83d\udc80 Zombie Processes Killed",
                f"Killed: {killed} | Failed: {failed}\n"
                f"Total zombies eliminated: {total}",
                "normal" if killed > 0 else "critical"
            )
        else:
            send_notification(
                "\u2705 No Zombie Processes",
                "System is clean - no zombie processes found",
                "low"
            )
    else:
        output = generate_output()
        print(json.dumps(output))

if __name__ == "__main__":
    main()
