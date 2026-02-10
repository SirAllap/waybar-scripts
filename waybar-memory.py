#!/usr/bin/env python3
# ----------------------------------------------------------------------------
# WAYBAR MEMORY MODULE
# ----------------------------------------------------------------------------
# A dynamic memory monitor for Waybar with cache clearing capability.
# Features:
# - Real-time RAM usage with color-coded states
# - Tooltip with detailed breakdown (Used, Cached, Buffers)
# - Auto-detects memory modules via dmidecode (requires sudo permissions)
# - Temperature monitoring (requires lm_sensors)
# - LMB: Clear RAM cache
# ----------------------------------------------------------------------------

import json
import psutil
import subprocess
import re
import pathlib
import sys
import argparse

# ---------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------
MEM_ICON = ""
TOOLTIP_WIDTH = 48

# ---------------------------------------------------
# THEME & COLORS
# ---------------------------------------------------
# Attempts to load colors from a TOML theme file.
# Defaults to a standard palette if the file is missing.
try:
    import tomllib
except ImportError:
    tomllib = None

def load_theme_colors():
    # UPDATE THIS PATH to your specific theme file if you have one
    theme_path = pathlib.Path.home() / ".config/waybar/colors.toml"
    
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
        colors = data.get("colors", {})
        normal = colors.get("normal", {})
        bright = colors.get("bright", {})
        
        # Merge loaded colors with defaults
        return {**defaults, **normal, **{f"bright_{k}": v for k, v in bright.items()}}
    except Exception:
        return defaults

COLORS = load_theme_colors()

SECTION_COLORS = {
    "Memory":  {"icon": COLORS["green"],  "text": COLORS["green"]},
}

# Color thresholds for metrics
COLOR_TABLE = [
    {"color": COLORS["blue"],           "mem_storage": (0.0, 10), "mem_temp": (0, 40)},
    {"color": COLORS["cyan"],           "mem_storage": (10.0, 20), "mem_temp": (41, 50)},
    {"color": COLORS["green"],          "mem_storage": (20.0, 40), "mem_temp": (51, 60)},
    {"color": COLORS["yellow"],         "mem_storage": (40.0, 60), "mem_temp": (61, 70)},
    {"color": COLORS["bright_yellow"],  "mem_storage": (60.0, 80), "mem_temp": (71, 75)},
    {"color": COLORS["bright_red"],     "mem_storage": (80.0, 90), "mem_temp": (76, 80)},
    {"color": COLORS["red"],            "mem_storage": (90.0,100), "mem_temp": (81, 999)}
]

def get_color(value, metric_type):
    if value is None: return "#ffffff"
    try:
        value = float(value)
    except ValueError: return "#ffffff"
    
    for entry in COLOR_TABLE:
        if metric_type in entry:
            low, high = entry[metric_type]
            if low <= value <= high:
                return entry["color"]
    return COLOR_TABLE[-1]["color"]

# ---------------------------------------------------
# UTILITY FUNCTIONS
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

# ---------------------------------------------------
# CACHE CLEARING
# ---------------------------------------------------
def clear_ram_cache():
    """Clear RAM cache and send notification with results"""
    try:
        # Get cache size before clearing
        mem_before = psutil.virtual_memory()
        cached_before = getattr(mem_before, 'cached', 0) / (1024**3)
        
        # Use sudo directly (NOPASSWD should be configured in sudoers)
        # Clear caches: sync writes cached writes to persistent storage
        # drop_caches=3 clears pagecache, dentries and inodes
        # Run sync first
        sync_result = subprocess.run(
            ["sudo", "-n", "/usr/bin/sync"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Then drop caches
        result = subprocess.run(
            ["sudo", "-n", "/usr/bin/sh", "-c", "echo 3 > /proc/sys/vm/drop_caches"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            # Get cache size after clearing
            mem_after = psutil.virtual_memory()
            cached_after = getattr(mem_after, 'cached', 0) / (1024**3)
            cleared_amount = max(0, cached_before - cached_after)
            
            send_notification(
                "✅ RAM Cache Cleared",
                f"Freed {cleared_amount:.2f} GB of cache\n"
                f"Cached: {cached_before:.2f} GB → {cached_after:.2f} GB",
                "normal"
            )
        else:
            error_msg = result.stderr.strip() if result.stderr else "Permission denied"
            if "password" in error_msg.lower() or "sorry" in error_msg.lower():
                send_notification(
                    "❌ Cache Clear Failed",
                    "Sudo password required.\n\n"
                    "Please ensure NOPASSWD is configured:\n"
                    "sudo visudo -f /etc/sudoers.d/waybar-cache-clear\n\n"
                    "Add:\n"
                    "serallap ALL=(root) NOPASSWD: /usr/bin/sync\n"
                    "serallap ALL=(root) NOPASSWD: /usr/bin/sh",
                    "critical"
                )
            else:
                send_notification(
                    "❌ Cache Clear Failed",
                    f"Error: {error_msg}",
                    "critical"
                )
    except subprocess.TimeoutExpired:
        send_notification("❌ Cache Clear Failed", "Operation timed out", "critical")
    except Exception as e:
        send_notification("❌ Cache Clear Error", str(e), "critical")

# ---------------------------------------------------
# HARDWARE DETECTION
# ---------------------------------------------------
def get_memory_temps():
    """
    Reads memory temperatures from lm_sensors.
    Requires: lm_sensors installed and sensors-detect run.
    """
    temps = []
    try:
        output = subprocess.check_output(["sensors", "-j"], text=True, stderr=subprocess.DEVNULL)
        data = json.loads(output)
        for chip, content in data.items():
            if any(x in chip for x in ["jc42", "spd", "dram"]):
                for feature, subfeatures in content.items():
                    if isinstance(subfeatures, dict):
                        for key, val in subfeatures.items():
                            if "input" in key:
                                temps.append(int(val))
    except Exception:
        pass
    return temps

def get_memory_modules_from_dmidecode():
    """
    Fetches RAM stick details.
    NOTE: Requires sudo permissions for dmidecode without password.
    Add this to sudoers: user ALL=(root) NOPASSWD: /usr/sbin/dmidecode
    """
    detected_modules = []
    real_temps = get_memory_temps()
    try:
        output = subprocess.check_output(["sudo", "/usr/sbin/dmidecode", "--type", "memory"], text=True, stderr=subprocess.PIPE)
        
        current_module = {}
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Memory Device"):
                if current_module and current_module.get("size") and current_module["size"] != "No Module Installed":
                    detected_modules.append(current_module)
                
                t_val = real_temps[len(detected_modules)] if len(detected_modules) < len(real_temps) else 0
                current_module = {"temp": t_val}
            elif current_module:
                if line.startswith("Locator:"):
                    current_module["label"] = line.split(":", 1)[1].strip()
                elif line.startswith("Size:"):
                    size_str = line.split(":", 1)[1].strip()
                    if "MB" in size_str:
                        try:
                            size_mb = int(size_str.replace("MB", "").strip())
                            if size_mb >= 1024:
                                current_module["size"] = f"{size_mb // 1024} GB"
                            else:
                                current_module["size"] = size_str
                        except ValueError:
                            current_module["size"] = size_str
                    else:
                        current_module["size"] = size_str
                elif line.startswith("Type:"):
                    current_module["type"] = line.split(":", 1)[1].strip()
                elif line.startswith("Speed:"):
                    speed_str = line.split(":", 1)[1].strip()
                    if "MT/s" in speed_str:
                        current_module["speed"] = speed_str.replace("MT/s", "MHz")
                    else:
                        current_module["speed"] = speed_str
        
        if current_module and current_module.get("size") and current_module["size"] != "No Module Installed":
            detected_modules.append(current_module)

    except Exception:
        # Fail silently or return empty if sudo not configured
        return []
    
    return detected_modules

# ---------------------------------------------------
# OUTPUT GENERATION
# ---------------------------------------------------
def generate_output():
    """Generate waybar output"""
    mem = psutil.virtual_memory()
    mem_used_gb = mem.used / (1024**3)
    mem_total_gb = mem.total / (1024**3)
    mem_percent = mem.percent
    mem_available_gb = mem.available / (1024**3)
    mem_cached_gb = mem.cached / (1024**3) if hasattr(mem, 'cached') else 0
    mem_buffers_gb = mem.buffers / (1024**3) if hasattr(mem, 'buffers') else 0

    tooltip_lines = []
    border_color = COLORS["bright_black"]

    # Full width separator
    separator = "─" * TOOLTIP_WIDTH

    # --- Header (left-aligned) ---
    header = f"<span foreground='{SECTION_COLORS['Memory']['icon']}'>{MEM_ICON}</span> <span foreground='{SECTION_COLORS['Memory']['text']}'>Memory:</span>"
    tooltip_lines.append(left_line(header))

    # --- Separator ---
    tooltip_lines.append(f"<span foreground='{border_color}'>{separator}</span>")

    # --- Single Usage Line ---
    mem_color_val = get_color(mem_percent, 'mem_storage')
    usage_line = f"󰓅 | Usage: <span foreground='{mem_color_val}'>{mem_used_gb:.0f} GB</span> used <span foreground='{COLORS['white']}'>{mem_total_gb:.0f} GB</span> Total"
    tooltip_lines.append(left_line(usage_line))

    # Empty line before modules
    tooltip_lines.append("")

    # Calculate max temp for connectors
    memory_modules = get_memory_modules_from_dmidecode()
    max_mem_temp = 0
    if memory_modules:
        max_mem_temp = max(m.get('temp', 0) for m in memory_modules)

    connector_color = get_color(max_mem_temp, 'mem_temp')
    frame_color = COLORS['white']

    # Calculate percentages
    used_pct = (mem.used / mem.total) * 100
    cached_pct = (mem.cached / mem.total) * 100 if hasattr(mem, 'cached') else 0
    buffers_pct = (mem.buffers / mem.total) * 100 if hasattr(mem, 'buffers') else 0
    free_pct = max(0, 100.0 - used_pct - cached_pct - buffers_pct)

    # --- Memory Modules Section ---
    if memory_modules:
        for mod in memory_modules:
            t_val = mod.get('temp', 0)
            temp_colored = f"<span foreground='{get_color(t_val, 'mem_temp')}'>{t_val}°C</span>"
            mod_line = (
                f"| {mod.get('label', 'DIMM'):<8} | "
                f"{mod.get('size', 'N/A'):<8} | "
                f"{mod.get('type', 'DDR4'):<6} | "
                f"{mod.get('speed', 'N/A'):<8} | "
                f"{temp_colored}"
            )
            tooltip_lines.append(left_line(mod_line))
        tooltip_lines.append("")
    # If no modules, don't show anything (clean look)

    # Graphic Dimensions (matching GPU module centered approach)
    graph_width = TOOLTIP_WIDTH - 4  # Account for borders
    inner_width = graph_width - 4
    bar_len = inner_width - 2

    # Center the graphic
    padding = " " * int((TOOLTIP_WIDTH - graph_width) // 2)

    def c(text, color):
        return f"<span foreground='{color}'>{text}</span>"

    # Build the ORIGINAL ASCII visualization but centered
    # Line 1
    tooltip_lines.append(f"{padding} {c('╭' + '─'*inner_width + '╮', frame_color)}")
    # Line 2
    tooltip_lines.append(f"{padding}{c('╭╯', frame_color)}{c('░'*inner_width, connector_color)}{c('╰╮', frame_color)}")
    # Line 3 (Bar)
    c_used = int((used_pct / 100.0) * bar_len)
    c_cached = int((cached_pct / 100.0) * bar_len)
    c_buffers = int((buffers_pct / 100.0) * bar_len)
    c_free = bar_len - c_used - c_cached - c_buffers
    if c_free < 0: c_free = 0

    bar_str = (
        f"<span foreground='{COLORS['red']}'>{'█' * c_used}</span>"
        f"<span foreground='{COLORS['yellow']}'>{'█' * c_cached}</span>"
        f"<span foreground='{COLORS['cyan']}'>{'█' * c_buffers}</span>"
        f"<span foreground='{COLORS['bright_black']}'>{'█' * c_free}</span>"
    )
    tooltip_lines.append(f"{padding}{c('╰╮', frame_color)}{c('░', connector_color)}{bar_str}{c('░', connector_color)}{c('╭╯', frame_color)}")
    # Line 4
    tooltip_lines.append(f"{padding} {c('│', frame_color)}{c('░'*inner_width, connector_color)}{c('│', frame_color)}")
    # Line 5
    tooltip_lines.append(f"{padding}{c('╭╯', frame_color)}{c('┌' + '┬'*bar_len + '┐', frame_color)}{c('╰╮', frame_color)}")
    # Line 6
    tooltip_lines.append(f"{padding}{c('└─', frame_color)}{c('┴'*inner_width, frame_color)}{c('─┘', frame_color)}")

    # Empty line after graphic
    tooltip_lines.append("")

    legend = (
        f"<span size='11000'>"
        f"<span foreground='{COLORS['red']}'>█</span> Used {used_pct:.1f}%  "
        f"<span foreground='{COLORS['yellow']}'>█</span> Cached {cached_pct:.1f}%  "
        f"<span foreground='{COLORS['cyan']}'>{''.join(['█']*2)}</span> Buffers {buffers_pct:.1f}%  "
        f"<span foreground='{COLORS['bright_black']}'>█</span> Free {free_pct:.1f}%"
        f"</span>"
    )
    tooltip_lines.append(center_line(legend))

    # --- Action hint ---
    tooltip_lines.append("")
    tooltip_lines.append(f"<span foreground='{COLORS['bright_black']}' size='10000'>🖱️ LMB: Clear RAM Cache</span>")

    return {
        "text": f"{MEM_ICON} <span foreground='{get_color(mem_percent,'mem_storage')}'>{int(mem_percent)}%</span>",
        "tooltip": f"<span size='12000'>{'\n'.join(tooltip_lines)}</span>",
        "markup": "pango",
        "class": "memory",
    }

# ---------------------------------------------------
# MAIN
# ---------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Waybar Memory Module")
    parser.add_argument("--clear-cache", action="store_true",
                       help="Clear RAM cache and show notification")
    args = parser.parse_args()
    
    if args.clear_cache:
        clear_ram_cache()
    else:
        output = generate_output()
        print(json.dumps(output))

if __name__ == "__main__":
    main()
