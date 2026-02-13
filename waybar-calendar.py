#!/usr/bin/env python3
# ----------------------------------------------------------------------------
# WAYBAR CALENDAR MODULE - Stylish Calendar with Date/Time
# ----------------------------------------------------------------------------
# Features:
# - Shows current time and date in waybar
# - Beautiful calendar tooltip on hover
# - Matches styling of other waybar modules (CPU, GPU, Memory, Storage)
# - Omarchy theme integration
# ----------------------------------------------------------------------------

import json
from datetime import datetime
import calendar
import pathlib
import subprocess

try:
    import tomllib
except ImportError:
    tomllib = None

# ---------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------
CLOCK_ICON = ""
TOOLTIP_WIDTH = 35

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
# MOON PHASE CALCULATION
# ---------------------------------------------------
def get_moon_phase(date):
    """Calculate moon phase for a given date
    Returns: (phase_name, emoji, illumination_percentage)
    """
    # Known new moon: January 6, 2000
    new_moon = datetime(2000, 1, 6, 18, 14)
    
    # Calculate days since known new moon
    diff = date - new_moon
    days = diff.total_seconds() / 86400
    
    # Moon cycle is 29.53058867 days
    lunar_cycle = 29.53058867
    
    # Calculate current age of moon (0 to 29.53)
    moon_age = days % lunar_cycle
    
    # Calculate phase (0 to 1)
    phase = moon_age / lunar_cycle
    
    # Determine phase name and emoji
    if phase < 0.03 or phase > 0.97:
        return ("New Moon", "🌑", phase * 100)
    elif phase < 0.22:
        return ("Waxing Crescent", "🌒", phase * 100)
    elif phase < 0.28:
        return ("First Quarter", "🌓", phase * 100)
    elif phase < 0.47:
        return ("Waxing Gibbous", "🌔", phase * 100)
    elif phase < 0.53:
        return ("Full Moon", "🌕", phase * 100)
    elif phase < 0.72:
        return ("Waning Gibbous", "🌖", phase * 100)
    elif phase < 0.78:
        return ("Last Quarter", "🌗", phase * 100)
    else:
        return ("Waning Crescent", "🌘", phase * 100)

def get_next_moon_phase(date, target_phase="full"):
    """Calculate next full moon or new moon date"""
    new_moon = datetime(2000, 1, 6, 18, 14)
    lunar_cycle = 29.53058867
    
    if target_phase == "full":
        # Full moon is at ~14.77 days in the cycle
        offset = 14.765
    else:
        # New moon is at 0 days
        offset = 0
    
    # Calculate days since reference new moon
    diff = date - new_moon
    days = diff.total_seconds() / 86400
    
    # Find next occurrence
    cycles = (days - offset) / lunar_cycle
    next_cycle = int(cycles) + 1
    next_days = new_moon.timestamp() + ((next_cycle * lunar_cycle) + offset) * 86400
    
    return datetime.fromtimestamp(next_days)

# ---------------------------------------------------
# CALENDAR GENERATION
# ---------------------------------------------------
def generate_calendar(year, month):
    """Generate a styled calendar for the tooltip with proper alignment"""
    cal = calendar.Calendar(firstweekday=calendar.MONDAY)
    month_days = cal.monthdayscalendar(year, month)
    
    # Month and year header
    month_name = calendar.month_name[month]
    lines = []
    border_color = COLORS["bright_black"]
    
    # Header with month/year
    header = f"{month_name} {year}"
    lines.append(f"<span foreground='{COLORS['cyan']}'>{CLOCK_ICON}</span> <span foreground='{COLORS['white']}'><b>{header}</b></span>")
    lines.append(f"<span foreground='{border_color}'>{'─' * TOOLTIP_WIDTH}</span>")
    
    # Weekday headers - use monospace and fixed spacing (3 chars + 2 spaces = 5)
    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekday_line = ""
    for i, day in enumerate(weekdays):
        if i >= 5:  # Weekend
            color = COLORS["red"]
        else:
            color = COLORS["yellow"]
        weekday_line += f"<span foreground='{color}'>{day}</span>  "
    lines.append(f"<span font_family='monospace'>{weekday_line}</span>")
    lines.append(f"<span foreground='{border_color}'>{'─' * TOOLTIP_WIDTH}</span>")
    
    # Calendar days - use monospace for alignment
    today = datetime.now()
    for week in month_days:
        week_line = ""
        for day in week:
            if day == 0:
                week_line += "     "  # 5 spaces for empty days (to match XX   format)
            else:
                day_str = f"{day:2d}"
                # Check if it's today
                if day == today.day and month == today.month and year == today.year:
                    # Highlight today
                    week_line += f"<span foreground='{COLORS['black']}' background='{COLORS['cyan']}'><b>{day_str}</b></span>   "
                else:
                    # Regular day
                    day_of_week = week.index(day)
                    if day_of_week >= 5:  # Weekend
                        week_line += f"<span foreground='{COLORS['red']}'>{day_str}</span>   "
                    else:
                        week_line += f"<span foreground='{COLORS['white']}'>{day_str}</span>   "
        lines.append(f"<span font_family='monospace'>{week_line}</span>")
    
    # Add divider before next month preview
    lines.append(f"<span foreground='{border_color}'>{'─' * TOOLTIP_WIDTH}</span>")
    
    # Add next month preview
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    next_month_name = calendar.month_name[next_month][:3]
    lines.append(f"<span foreground='{COLORS['bright_black']}'>{CLOCK_ICON} Next: {next_month_name} {next_year}</span>")
    
    return "\n".join(lines)

def get_upcoming_events():
    """Get upcoming events/system info"""
    events = []
    
    # Check if any timers are running
    try:
        result = subprocess.run(
            ["systemctl", "list-timers", "--all", "--no-pager", "--no-legend"],
            capture_output=True, text=True, timeout=2
        )
        if result.stdout:
            lines = result.stdout.strip().split("\n")
            if lines and lines[0]:
                events.append(("󰔟", "Timers active", COLORS["green"]))
    except:
        pass
    
    # Check uptime
    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.readline().split()[0])
            uptime_hours = int(uptime_seconds / 3600)
            uptime_days = uptime_hours // 24
            if uptime_days > 0:
                events.append(("󰔚", f"Uptime: {uptime_days}d {uptime_hours % 24}h", COLORS["cyan"]))
            else:
                events.append(("󰔚", f"Uptime: {uptime_hours}h", COLORS["cyan"]))
    except:
        pass
    
    return events

# ---------------------------------------------------
# MAIN
# ---------------------------------------------------
def main():
    now = datetime.now()
    
    # Format for waybar text (time and date)
    time_str = now.strftime("%I:%M %p")
    date_str = now.strftime("%a, %b %d")
    
    # Generate calendar tooltip
    calendar_tooltip = generate_calendar(now.year, now.month)
    
    # Get moon phase info
    moon_name, moon_emoji, illumination = get_moon_phase(now)
    next_full = get_next_moon_phase(now, "full")
    next_new = get_next_moon_phase(now, "new")
    
    # Build full tooltip with additional info
    tooltip_lines = [calendar_tooltip]
    
    # Add moon phase section
    tooltip_lines.append(f"<span foreground='{COLORS['bright_black']}'>{'─' * TOOLTIP_WIDTH}</span>")
    tooltip_lines.append(f"<span foreground='{COLORS['magenta']}'>{moon_emoji}</span> <span foreground='{COLORS['white']}'><b>{moon_name}</b></span>")
    tooltip_lines.append(f"   <span foreground='{COLORS['bright_black']}'>Illumination: {illumination:.0f}%</span>")
    
    # Show next full/new moon
    days_to_full = (next_full - now).days
    days_to_new = (next_new - now).days
    tooltip_lines.append(f"   🌕 Full Moon in {days_to_full} days")
    tooltip_lines.append(f"   🌑 New Moon in {days_to_new} days")
    
    # Add separator
    tooltip_lines.append(f"<span foreground='{COLORS['bright_black']}'>{'─' * TOOLTIP_WIDTH}</span>")
    
    # Add system info
    events = get_upcoming_events()
    if events:
        for icon, text, color in events:
            tooltip_lines.append(f"{icon} <span foreground='{color}'>{text}</span>")
    
    # Output JSON for waybar
    output = {
        "text": f"{CLOCK_ICON} <span foreground='{COLORS['cyan']}'>{time_str}</span> | <span foreground='{COLORS['white']}'>{date_str}</span>",
        "tooltip": f"<span size='12000'>{'\n'.join(tooltip_lines)}</span>",
        "markup": "pango",
        "class": "calendar"
    }
    
    print(json.dumps(output, ensure_ascii=False))

if __name__ == "__main__":
    main()
