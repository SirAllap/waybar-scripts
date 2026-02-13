#!/usr/bin/env python3
# ----------------------------------------------------------------------------
# WAYBAR GPU MODULE - AMD Version with Centered Layout & Border
# ----------------------------------------------------------------------------

import json
import subprocess
import os
import pathlib
import re
import psutil

# ---------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------
GPU_ICON = "󰢮"
TOOLTIP_WIDTH = 35  # Width including borders

# ---------------------------------------------------
# THEME & COLORS - UPDATED FOR OMARCHY
# ---------------------------------------------------
try:
    import tomllib
except ImportError:
    tomllib = None

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

COLOR_TABLE = [
    {"color": COLORS["blue"],           "cpu_gpu_temp": (0, 35),   "gpu_power": (0.0, 20)},
    {"color": COLORS["cyan"],           "cpu_gpu_temp": (36, 45),  "gpu_power": (21, 40)},
    {"color": COLORS["green"],          "cpu_gpu_temp": (46, 54),  "gpu_power": (41, 60)},
    {"color": COLORS["yellow"],         "cpu_gpu_temp": (55, 65),  "gpu_power": (61, 75)},
    {"color": COLORS["bright_yellow"],  "cpu_gpu_temp": (66, 75),  "gpu_power": (76, 85)},
    {"color": COLORS["bright_red"],     "cpu_gpu_temp": (76, 85),  "gpu_power": (86, 95)},
    {"color": COLORS["red"],            "cpu_gpu_temp": (86, 999), "gpu_power": (96, 999)}
]

def get_color(value, metric_type):
    try: value = float(value)
    except: return "#ffffff"
    for entry in COLOR_TABLE:
        if metric_type in entry:
            low, high = entry[metric_type]
            if low <= value <= high: 
                return entry["color"]
    return COLOR_TABLE[-1]["color"]

# ---------------------------------------------------
# AMD GPU DATA EXTRACTION
# ---------------------------------------------------
gpu_percent, gpu_temp, gpu_power, fan_speed, fan_pct = 0, 0, 0.0, 0, 0
vram_used, vram_total = 0, 0
gpu_name = "AMD GPU"
gpu_tdp = 250.0
fan_max = 3300

drm_path = "/sys/class/drm/card0/device"
if not os.path.exists(f"{drm_path}/mem_info_vram_total"):
    drm_path = "/sys/class/drm/card1/device"

try:
    try:
        with open(f"{drm_path}/device", "r") as f:
            device_id = f.read().strip()
            if "0x73bf" in device_id or "Navi 21" in device_id:
                gpu_name = "AMD Radeon RX 6800"
            elif "AMD" in device_id:
                gpu_name = "AMD Radeon GPU"
    except:
        pass

    try:
        hwmon_dirs = [d for d in os.listdir(f"{drm_path}/hwmon") if d.startswith("hwmon")]
        if hwmon_dirs:
            hwmon = hwmon_dirs[0]
            with open(f"{drm_path}/hwmon/{hwmon}/temp1_input", "r") as f:
                gpu_temp = int(f.read().strip()) // 1000
    except:
        try:
            sensors_output = subprocess.check_output(["sensors"], text=True, stderr=subprocess.DEVNULL)
            for line in sensors_output.split('\n'):
                if 'edge' in line.lower() or 'junction' in line.lower():
                    match = re.search(r'\+([\d.]+)', line)
                    if match:
                        gpu_temp = int(float(match.group(1)))
                        break
        except:
            pass

    try:
        with open(f"{drm_path}/gpu_busy_percent", "r") as f:
            gpu_percent = int(f.read().strip())
    except:
        pass

    try:
        with open(f"{drm_path}/mem_info_vram_used", "r") as f:
            vram_used = int(f.read().strip()) // 1024 // 1024
        with open(f"{drm_path}/mem_info_vram_total", "r") as f:
            vram_total = int(f.read().strip()) // 1024 // 1024
    except:
        vram_total = 16384
        vram_used = 0

    try:
        hwmon_dirs = [d for d in os.listdir(f"{drm_path}/hwmon") if d.startswith("hwmon")]
        if hwmon_dirs:
            hwmon = hwmon_dirs[0]
            with open(f"{drm_path}/hwmon/{hwmon}/power1_average", "r") as f:
                gpu_power = int(f.read().strip()) / 1000000.0
    except:
        try:
            hwmon_dirs = [d for d in os.listdir(f"{drm_path}/hwmon") if d.startswith("hwmon")]
            if hwmon_dirs:
                hwmon = hwmon_dirs[0]
                with open(f"{drm_path}/hwmon/{hwmon}/power1_input", "r") as f:
                    gpu_power = int(f.read().strip()) / 1000000.0
        except:
            pass

    try:
        hwmon_dirs = [d for d in os.listdir(f"{drm_path}/hwmon") if d.startswith("hwmon")]
        if hwmon_dirs:
            hwmon = hwmon_dirs[0]
            with open(f"{drm_path}/hwmon/{hwmon}/fan1_input", "r") as f:
                fan_speed = int(f.read().strip())
            try:
                with open(f"{drm_path}/hwmon/{hwmon}/fan1_max", "r") as f:
                    fan_max = int(f.read().strip())
            except:
                pass
            # Use PWM for percentage calculation to match corectrl
            try:
                with open(f"{drm_path}/hwmon/{hwmon}/pwm1", "r") as f:
                    pwm_val = int(f.read().strip())
                try:
                    with open(f"{drm_path}/hwmon/{hwmon}/pwm1_max", "r") as f:
                        pwm_max = int(f.read().strip())
                except:
                    pwm_max = 255
                fan_pct = (pwm_val / pwm_max * 100)
            except:
                pass
    except:
        pass

except Exception:
    pass

vram_pct = (vram_used / vram_total * 100) if vram_total > 0 else 0
pwr_pct = (gpu_power / gpu_tdp * 100) if gpu_tdp > 0 else 0
# fan_pct is already calculated from PWM above to match corectrl

# ---------------------------------------------------
# CENTERING & BORDER UTILITIES
# ---------------------------------------------------
def strip_pango_tags(text):
    """Remove Pango markup tags to calculate visible width"""
    text = re.sub(r'<span[^>]*>', '', text)
    text = re.sub(r'</span>', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    return text

def visible_len(text):
    """Get visible length of text (excluding Pango tags)"""
    return len(strip_pango_tags(text))

def center_line(line, width=TOOLTIP_WIDTH - 2, pad_char=' '):
    """Center a line with Pango markup support"""
    vlen = visible_len(line)
    if vlen >= width:
        return line
    left_pad = (width - vlen) // 2
    right_pad = width - vlen - left_pad
    return f"{pad_char * left_pad}{line}{pad_char * right_pad}"


def left_line(line, width=TOOLTIP_WIDTH - 2, pad_char=' '):
    """Left-align a line with Pango markup support"""
    vlen = visible_len(line)
    if vlen >= width:
        return line
    return f"{line}{pad_char * (width - vlen)}"

def add_border_line(line, border_color="#555555"):
    return line

# ---------------------------------------------------
# GRAPHIC GENERATOR
# ---------------------------------------------------
def get_vram_color(usage, level):
    if usage > (level - 1) * (100 / 6):
        return get_color(usage, 'gpu_power')
    return COLORS["white"]

def get_bar_segment(val, threshold):
    char_map = {80: "███", 60: "▅▅▅", 40: "▃▃▃", 20: "▂▂▂", 0: "───"}
    color = get_color(val, 'gpu_power') if val > threshold else "#555555"
    return f"<span foreground='{color}'>{char_map[threshold]}</span>"

die_temp_color = get_color(gpu_temp, 'cpu_gpu_temp')
f_c = COLORS["white"]
bg = lambda t: f"<span foreground='{die_temp_color}'>{t}</span>"

vc = [get_vram_color(vram_pct, i) for i in range(1, 7)]

bars = []
for thresh in [80, 60, 40, 20, 0]:
    bars.append(f"{get_bar_segment(gpu_percent, thresh)} {get_bar_segment(pwr_pct, thresh)} {get_bar_segment(fan_pct, thresh)}")

# Build graphic lines - carefully aligned
graphic_raw = [
    f"<span foreground='{f_c}'>╭─────────────────╮</span>",
    f"<span foreground='{f_c}'> </span><span foreground='{vc[5]}'>███</span><span foreground='{f_c}'> │</span>{bg('░░░░░░░░░░░░░░░░░')}<span foreground='{f_c}'>│ </span><span foreground='{vc[5]}'>███</span><span foreground='{f_c}'> </span>",
    f"<span foreground='{f_c}'> </span><span foreground='{vc[4]}'>███</span><span foreground='{f_c}'> │</span>{bg('░░')}  󰓅      󰈐  {bg('░░')}<span foreground='{f_c}'>│ </span><span foreground='{vc[4]}'>███</span><span foreground='{f_c}'> </span>",
    f"<span foreground='{f_c}'>  │</span>{bg('░░')} {bars[0]} {bg('░░')}<span foreground='{f_c}'>│  </span>",
    f"<span foreground='{f_c}'> </span><span foreground='{vc[3]}'>███</span><span foreground='{f_c}'> │</span>{bg('░░')} {bars[1]} {bg('░░')}<span foreground='{f_c}'>│ </span><span foreground='{vc[3]}'>███</span><span foreground='{f_c}'> </span>",
    f"<span foreground='{f_c}'> </span><span foreground='{vc[2]}'>███</span><span foreground='{f_c}'> │</span>{bg('░░')} {bars[2]} {bg('░░')}<span foreground='{f_c}'>│ </span><span foreground='{vc[2]}'>███</span><span foreground='{f_c}'> </span>",
    f"<span foreground='{f_c}'>  │</span>{bg('░░')} {bars[3]} {bg('░░')}<span foreground='{f_c}'>│  </span>",
    f"<span foreground='{f_c}'> </span><span foreground='{vc[1]}'>███</span><span foreground='{f_c}'> │</span>{bg('░░')} {bars[4]} {bg('░░')}<span foreground='{f_c}'>│ </span><span foreground='{vc[1]}'>███</span><span foreground='{f_c}'> </span>",
    f"<span foreground='{f_c}'> </span><span foreground='{vc[0]}'>███</span><span foreground='{f_c}'> │</span>{bg('░░░░░░░░░░░░░░░░░')}<span foreground='{f_c}'>│ </span><span foreground='{vc[0]}'>███</span><span foreground='{f_c}'> </span>",
    f"<span foreground='{f_c}'>╰─────────────────╯</span>"
]

# ---------------------------------------------------
# TOOLTIP CONSTRUCTION
# ---------------------------------------------------
border_color = COLORS["bright_black"]
tooltip_lines = []


# --- Header ---
header = left_line(f"<span foreground='{COLORS['yellow']}'>{GPU_ICON}</span> <span foreground='{COLORS['yellow']}'>GPU</span> - {gpu_name}")
tooltip_lines.append(add_border_line(center_line(header), border_color))


separator = "─" * (TOOLTIP_WIDTH - 2)
tooltip_lines.append(add_border_line(f"<span foreground='{border_color}'>{separator}</span>", border_color))


# Stats - aligned with proper spacing
stats = [
    f"  Temperature:  <span foreground='{die_temp_color}'>{gpu_temp}°C</span>",
    f"󰘚  V-RAM:        <span foreground='{get_color(vram_pct, 'gpu_power')}'>{vram_used} / {vram_total} MB</span>",
    f"  Power:        <span foreground='{get_color(pwr_pct, 'gpu_power')}'>{gpu_power:.1f}W / {gpu_tdp}W</span>",
    f"󰓅  Utilization:  <span foreground='{get_color(gpu_percent, 'gpu_power')}'>{gpu_percent}%</span>",
    f"󰈐  Fan Speed:    <span foreground='{get_color(fan_pct, 'gpu_power')}'>{fan_speed} RPM ({fan_pct:.0f}%)</span>"
]

for stat in stats:
    tooltip_lines.append(add_border_line(left_line(stat), border_color))

# Empty line
tooltip_lines.append(add_border_line("", border_color))

# Add graphic with borders
for line in graphic_raw:
    tooltip_lines.append(add_border_line(center_line(line), border_color))

# Empty line
tooltip_lines.append(add_border_line("", border_color))

# Process section
tooltip_lines.append(add_border_line(left_line("Top GPU Processes:"), border_color))

gpu_procs_found = False
try:
    gpu_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            name = proc.info['name'].lower()
            if any(x in name for x in ['chrome', 'firefox', 'zen', 'steam', 'proton', 'wine', 'vkcube', 'glxgears']):
                mem_mb = proc.info['memory_info'].rss // 1024 // 1024 if proc.info['memory_info'] else 0
                gpu_processes.append({'name': proc.info['name'], 'mem': mem_mb})
        except:
            continue
    
    gpu_processes.sort(key=lambda x: x['mem'], reverse=True)
    
    if gpu_processes:
        for p in gpu_processes[:3]:
            name = p['name']
            if len(name) > 15: 
                name = name[:14] + "…"
            mem_str = f"{p['mem']}MB"
            color = get_color(p['mem'] / 10, 'gpu_power')
            proc_line = f"• {name:<15} <span foreground='{color}'>󰘚 {mem_str}</span>"
            tooltip_lines.append(add_border_line(left_line(proc_line), border_color))
        gpu_procs_found = True
    
    if not gpu_procs_found:
        tooltip_lines.append(add_border_line(left_line("<span size='small'>No active GPU processes detected</span>"), border_color))
        
except:
    tooltip_lines.append(add_border_line(center_line("<span size='small'>Process detection unavailable</span>"), border_color))


# --- Footer padding ---
tooltip_lines.append(add_border_line("", border_color)) 

separator = "─" * (TOOLTIP_WIDTH - 2)
tooltip_lines.append(add_border_line(f"<span foreground='{border_color}'>{separator}</span>", border_color))

# Footer
footer_text = f"󰍽  LMB: CoreCtrl"
tooltip_lines.append(add_border_line(center_line(footer_text), border_color))


print(json.dumps({
    "text": f"{GPU_ICON} <span foreground='{die_temp_color}'>{gpu_temp}°C</span>",
    "tooltip": f"<span size='12000'>{'\n'.join(tooltip_lines)}</span>",
    "markup": "pango",
    "class": "gpu"
}))
