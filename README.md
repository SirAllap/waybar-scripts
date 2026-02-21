# Waybar Custom Scripts Collection

A comprehensive collection of custom Python and Bash scripts for [Waybar](https://github.com/Alexays/Waybar) status bar. These scripts provide detailed system monitoring with beautiful visualizations using Pango markup.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)

## 📁 Scripts Overview

| Script | Purpose | Dependencies |
|--------|---------|--------------|
| `waybar-clock-weather.py` | Clock, weather, calendar, moon phase — all in one | Nerd Font |
| `waybar-cpu.py` | CPU monitoring with per-core visualization | `psutil` |
| `waybar-gpu.py` | AMD GPU monitoring with VRAM/power stats | `psutil` |
| `waybar-memory.py` | RAM usage with module detection | `psutil`, `dmidecode` (optional) |
| `waybar-storage.py` | Drive monitoring with SMART data | `psutil`, `smartmontools` (optional) |
| `waybar-system-integrity.py` | System health checks | `psutil` |
| `waybar-claude-usage.py` | Claude Code usage % and reset countdown | `claude` CLI |
| `cava.sh` | Audio visualizer bars | `cava` |

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Arch Linux
sudo pacman -S python python-psutil smartmontools dmidecode lm_sensors

# Python packages
pip install requests psutil

# For audio visualizer
sudo pacman -S cava
```

### 2. Copy Scripts

```bash
mkdir -p ~/.config/waybar/scripts
cp *.py *.sh ~/.config/waybar/scripts/
chmod +x ~/.config/waybar/scripts/*
```

### 3. Configure Waybar

Add modules to your `~/.config/waybar/config.jsonc`:

```jsonc
{
  "modules-center": [
    "custom/weather",
    "custom/cpu",
    "custom/gpu", 
    "custom/memory",
    "custom/storage",
    "custom/system-integrity"
  ],
  
  "custom/weather": {
    "format": "{}",
    "tooltip": true,
    "interval": 600,
    "exec": "~/.config/waybar/scripts/weather.py",
    "return-type": "json",
    "escape": false,
    "markup": "pango"
  },
  
  "custom/cpu": {
    "format": "{}",
    "return-type": "json",
    "interval": 5,
    "exec": "~/.config/waybar/scripts/waybar-cpu.py",
    "on-click": "$TERMINAL -e btop"
  },
  
  "custom/gpu": {
    "format": "{}",
    "return-type": "json",
    "interval": 5,
    "exec": "~/.config/waybar/scripts/waybar-gpu.py",
    "on-click": "corectrl"
  },
  
  "custom/memory": {
    "format": "{}",
    "return-type": "json",
    "interval": 5,
    "exec": "~/.config/waybar/scripts/waybar-memory.py"
  },
  
  "custom/storage": {
    "format": "{}",
    "return-type": "json",
    "interval": 5,
    "exec": "~/.config/waybar/scripts/waybar-storage.py"
  },
  
  "custom/system-integrity": {
    "format": "{}",
    "return-type": "json",
    "interval": 30,
    "exec": "~/.config/waybar/scripts/waybar-system-integrity.py",
    "on-click": "$TERMINAL -e 'watch -n 2 ~/.config/waybar/scripts/waybar-system-integrity.py'"
  },
  
  "custom/visualizer": {
    "format": "{}",
    "exec": "~/.config/waybar/scripts/cava.sh",
    "tooltip": false
  }
}
```

### 4. Restart Waybar

```bash
# For Omarchy
omarchy-restart-waybar

# Or manually
killall waybar && waybar
```

## 📊 Detailed Script Documentation

### 🕐🌤️ Clock + Weather Module (`waybar-clock-weather.py`)

Merged module combining clock, weather, calendar, moon phase and system info into a single bar entry and tooltip.

**Bar:** `HH:MM │ Fri, Feb 21  │  ⛅ 18°C`

**Tooltip sections (top → bottom):**
- Current weather conditions (temp, feels-like, humidity, wind, UV, fire danger)
- Hourly forecast (next 12 hours, 24h times)
- 7-day extended forecast
- Calendar grid (current month, centered day numbers, today highlighted)
- Moon phase with illumination bar and next full/new moon
- System uptime and load average

**Features:**
- Open-Meteo API (no API key required)
- Auto-caching (15-minute intervals) — shared with `weather.py`
- Color-coded temperatures, severity-based coloring for UV/wind/fire
- Calendar with centered weekday headers and day numbers
- Omarchy theme integration

**Configuration via environment variables:**

| Variable | Description | Example |
|----------|-------------|---------|
| `WAYBAR_WEATHER_LAT` | Your latitude | `48.8566` |
| `WAYBAR_WEATHER_LON` | Your longitude | `2.3522` |
| `WAYBAR_WEATHER_CITY` | Label shown in the bar | `Paris` |

Find your coordinates at [latlong.net](https://www.latlong.net/).

Set them once in your environment (see [Environment Setup](#-environment-setup) below).

**Waybar config:**
```jsonc
"custom/clock-weather": {
  "format": "{}",
  "return-type": "json",
  "interval": 60,
  "exec": "~/.config/waybar/scripts/waybar-clock-weather.py",
  "tooltip": true,
  "markup": "pango"
}
```

---

### 🖥️ CPU Module (`waybar-cpu.py`)

Advanced CPU monitoring with per-core visualization.

**Features:**
- Real-time CPU temperature (color-coded)
- Clock speed and power consumption (via RAPL)
- Per-core usage with visual CPU "chip" graphic
- Top processes list
- Historical data tracking
- Omarchy theme integration

**Visual Elements:**
- CPU die graphic with colored substrate
- Individual core indicators (●/○)
- Temperature-based color coding

---

### 🎮 GPU Module (`waybar-gpu.py`)

AMD GPU monitoring with artistic visualization.

**Features:**
- GPU temperature, usage, power draw
- VRAM utilization
- Fan speed monitoring
- Visual GPU representation with bars
- Top GPU processes

**Requirements:** AMD GPU with sysfs access (`/sys/class/drm/card*/`)

**Visual Elements:**
- Styled GPU graphic with VRAM indicators
- Utilization/Power/Fan bar charts

---

### 💾 Memory Module (`waybar-memory.py`)

RAM monitoring with detailed breakdown.

**Features:**
- Total/Used/Available memory
- Cached and buffers visualization
- Memory module detection (via dmidecode)
- Memory temperature monitoring (if sensors available)
- ASCII memory bar graphic

**Optional:** Configure sudo for dmidecode to see memory module details:
```bash
sudo visudo
# Add: your_username ALL=(root) NOPASSWD: /usr/sbin/dmidecode
```

---

### 💿 Storage Module (`waybar-storage.py`)

Multi-drive monitoring with health stats.

**Features:**
- Auto-detects all mounted drives
- Per-drive temperature monitoring
- SMART health status
- NVMe lifespan/TBW estimates
- Real-time read/write speeds
- Custom drive name mapping

**Configuration via environment variables:**

Set `WAYBAR_STORAGE_NAMES` as a comma-separated list of `device=Label` pairs.
Run `lsblk -d -o NAME` to find your device names.

| Variable | Format | Example |
|----------|--------|---------|
| `WAYBAR_STORAGE_NAMES` | `device=Label,...` | `nvme0n1=Omarchy,sda=Tank,nvme1n1=Games` |

Set it once in your environment (see [Environment Setup](#-environment-setup) below).

**Optional:** Configure sudo for smartctl:
```bash
sudo visudo
# Add: your_username ALL=(root) NOPASSWD: /usr/sbin/smartctl
```

---

### 🔒 System Integrity (`waybar-system-integrity.py`)

Comprehensive system health monitoring.

**Checks:**
- Systemd failed services
- Disk SMART status
- Available system updates
- Security status (firewall, failed logins)
- System errors (dmesg, journalctl)
- Disk space usage
- Memory pressure
- CPU load
- Temperatures
- ZFS/BTRFS pool status
- Network connectivity
- Battery health (laptops)
- Audit logs (SELinux/AppArmor)

**Display:** Shows overall health status with issue counts.

---

### 🤖 Claude Code Usage (`waybar-claude-usage.py` + `waybar-claude-fetch.py`)

Real-time Claude Code usage limits displayed in Waybar. Shows session (5h rolling window) and weekly usage as percentages with color-coded warnings.

**Features:**
- Bar shows session usage % and time remaining until reset (e.g. `󰧿 16% ↺59m`)
- Tooltip with progress bars for session, weekly (all models), weekly (Sonnet), and extra spend
- Reset times displayed in 24h with date (e.g. `Feb 21, 02:00`)
- Auto-hides when Claude Code hasn't been used in the last hour — zero resource use on non-coding days
- Background fetcher (~8s) so Waybar never blocks
- Click to force-refresh
- Lock file prevents concurrent fetches

**How it works:**

`/usage` is a TUI-only command in Claude Code. `waybar-claude-fetch.py` spawns a PTY session, waits for the prompt, sends `/usage`, captures and parses the output, then writes a cache file. `waybar-claude-usage.py` reads that cache instantly and is what Waybar actually calls.

**Requirements:**
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated
- Default install path: `~/.local/bin/claude` (edit `CLAUDE_PATH` in `waybar-claude-fetch.py` if different)

**Waybar config:**
```jsonc
"custom/claude-usage": {
  "format": "{}",
  "return-type": "json",
  "interval": 5,
  "exec": "~/.config/waybar/scripts/waybar-claude-usage.py",
  "on-click": "~/.config/waybar/scripts/waybar-claude-usage.py --refresh",
  "tooltip": true,
  "markup": "pango"
}
```

**CSS (add to `style.css`):**
```css
#custom-claude-usage {
  background-color: @background;
  border-radius: 10px;
  padding: 0 10px;
  margin: 0 0 0 5px;
}

#custom-claude-usage.inactive {
  min-width: 0;
  padding: 0;
  margin: 0;
  background: transparent;
}
```

**Tunable constants in `waybar-claude-usage.py`:**

| Constant | Default | Description |
|----------|---------|-------------|
| `CACHE_TTL` | `90` | Seconds between background fetches |
| `ACTIVITY_TTL` | `3600` | Seconds of inactivity before module hides |

---

### 🎵 Audio Visualizer (`cava.sh`)

Real-time audio spectrum bars.

**Requirements:**
- `cava` installed and configured
- Pipewire or PulseAudio

**Setup:**
```bash
# Create cava config for waybar
mkdir -p ~/.config/cava
cat > ~/.config/cava/waybar.conf << 'EOF'
[general]
framerate = 30
bars = 8
bar_spacing = 1

[output]
method = raw
raw_target = /home/your_username/.cache/cava.fifo
data_format = ascii
ascii_max_range = 7
EOF
```

Replace `your_username` with your actual username (`echo $USER`).

## 🔧 Environment Setup

Scripts that require personal configuration read values from environment variables. Set them once and all scripts pick them up automatically.

### Hyprland (Omarchy / `~/.config/hypr/env.conf`)

```bash
# Weather
env = WAYBAR_WEATHER_LAT,48.8566
env = WAYBAR_WEATHER_LON,2.3522
env = WAYBAR_WEATHER_CITY,Paris

# Storage — run `lsblk -d -o NAME` to find your device names
env = WAYBAR_STORAGE_NAMES,nvme0n1=System,sda=Storage
```

Then reload Hyprland: `hyprctl reload`.

### Shell profile (`~/.bashrc` or `~/.zshrc`)

```bash
export WAYBAR_WEATHER_LAT="48.8566"
export WAYBAR_WEATHER_LON="2.3522"
export WAYBAR_WEATHER_CITY="Paris"
export WAYBAR_STORAGE_NAMES="nvme0n1=System,sda=Storage"
```

### systemd user environment (`~/.config/environment.d/waybar.conf`)

```ini
WAYBAR_WEATHER_LAT=48.8566
WAYBAR_WEATHER_LON=2.3522
WAYBAR_WEATHER_CITY=Paris
WAYBAR_STORAGE_NAMES=nvme0n1=System,sda=Storage
```

After editing, run `systemctl --user daemon-reload` and restart Waybar.

---

## 🎨 Theming

All scripts support dynamic theming:

### Omarchy Theme Integration
Scripts automatically load colors from:
```
~/.config/omarchy/current/theme/colors.toml
```

### Custom Theme
Create `~/.config/waybar/colors.toml`:
```toml
[colors]
normal = { red = "#ff0000", green = "#00ff00", blue = "#0000ff" }
bright = { red = "#ff5555", green = "#55ff55", blue = "#5555ff" }
```

### Default Fallback Colors
If no theme is found, scripts use a standard palette that works with any setup.

## ⚙️ Requirements

### Required
- Python 3.11+
- `psutil` Python package
- Nerd Font (for icons)

### Optional (for full functionality)
- `requests` (for weather)
- `smartmontools` (for drive health)
- `dmidecode` (for memory module info)
- `lm_sensors` (for temperature monitoring)
- `cava` (for audio visualizer)

### System Permissions
Some features require sudo access without password:

```bash
# Edit sudoers
sudo visudo

# Add these lines:
your_username ALL=(root) NOPASSWD: /usr/sbin/dmidecode
your_username ALL=(root) NOPASSWD: /usr/sbin/smartctl
```

## 🐛 Troubleshooting

### Scripts not showing up
- Check script permissions: `chmod +x ~/.config/waybar/scripts/*`
- Test manually: `~/.config/waybar/scripts/weather.py`
- Check waybar logs: `waybar -l debug`

### Missing icons
- Install a Nerd Font: `sudo pacman -S ttf-jetbrains-mono-nerd`
- Set font in waybar CSS

### Weather not working
- Check `requests` is installed: `pip install requests`
- Verify coordinates in script
- Check internet connection

### GPU module not working
- Only supports AMD GPUs via sysfs
- Intel/NVIDIA require different approaches
- Check `/sys/class/drm/card*/` exists

### Permission errors
- Add sudo rules as shown above
- Or run scripts with sudo (not recommended)

## 🤝 Contributing

Feel free to submit issues and pull requests. These scripts are designed for Omarchy but should work on any Linux system with Waybar.

## 📄 License

MIT License - Feel free to use and modify as needed.

## 🙏 Acknowledgments

- [Waybar](https://github.com/Alexays/Waybar) - Highly customizable Wayland bar
- [Open-Meteo](https://open-meteo.com/) - Free weather API
- [Omarchy](https://omarchy.org/) - Opinionated Arch Linux distribution

---

**Created for personal use, shared for the community.**
