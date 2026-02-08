#!/usr/bin/env python3
# ----------------------------------------------------------------------------
# WAYBAR SYSTEM INTEGRITY MODULE
# ----------------------------------------------------------------------------
# Comprehensive system health and integrity monitoring
# Checks: systemd services, disk health, security, updates, errors, temps, etc.
# ----------------------------------------------------------------------------

import json
import psutil
import subprocess
import os
import re
import pathlib
from datetime import datetime

try:
    import tomllib
except ImportError:
    tomllib = None

# ---------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------
INTEGRITY_ICONS = {
    "OK": "󰗠",
    "WARNING": "󰞀",
    "CRITICAL": "󰍁",
    "UNKNOWN": "󰈡",
}
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
        colors = {f"color{i}": data.get(f"color{i}", defaults["black"]) for i in range(16)}
        return {
            "black": colors["color0"], "red": colors["color1"], "green": colors["color2"],
            "yellow": colors["color3"], "blue": colors["color4"], "magenta": colors["color5"],
            "cyan": colors["color6"], "white": colors["color7"],
            "bright_black": colors["color8"], "bright_red": colors["color9"],
            "bright_green": colors["color10"], "bright_yellow": colors["color11"],
            "bright_blue": colors["color12"], "bright_magenta": colors["color13"],
            "bright_cyan": colors["color14"], "bright_white": colors["color15"],
        }
    except Exception:
        return defaults

COLORS = load_theme_colors()

# ---------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------
def run_cmd(cmd, timeout=5):
    """Run command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip() if result.returncode == 0 else ""
    except:
        return ""

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

# ---------------------------------------------------
# SYSTEM CHECKS
# ---------------------------------------------------

def check_systemd_services():
    """Check for failed systemd services"""
    try:
        output = run_cmd("systemctl --failed --no-legend --quiet")
        if output:
            failed = [line.split()[0] for line in output.split('\n') if line.strip()]
            return {"status": "WARNING", "failed": failed, "count": len(failed)}
        return {"status": "OK", "failed": [], "count": 0}
    except:
        return {"status": "UNKNOWN", "failed": [], "count": 0}

def check_disk_health():
    """Check disk SMART status"""
    issues = []
    healthy = True
    
    try:
        # Get all block devices
        devices = run_cmd("lsblk -d -n -o NAME").split('\n')
        for dev in devices:
            if dev and not dev.startswith('loop'):
                # Check SMART status
                smart = run_cmd(f"sudo -n smartctl -H /dev/{dev} 2>/dev/null")
                if smart and "PASSED" not in smart and "OK" not in smart:
                    issues.append(f"{dev}: SMART warning")
                    healthy = False
    except:
        pass
    
    return {"status": "OK" if healthy else "WARNING", "issues": issues}

def check_system_updates():
    """Check for available system updates"""
    try:
        # Check pacman
        updates = run_cmd("checkupdates 2>/dev/null | wc -l")
        count = int(updates) if updates else 0
        
        if count > 50:
            return {"status": "WARNING", "count": count, "message": f"{count} updates available"}
        elif count > 0:
            return {"status": "OK", "count": count, "message": f"{count} updates available"}
        return {"status": "OK", "count": 0, "message": "System up to date"}
    except:
        return {"status": "UNKNOWN", "count": 0, "message": "Cannot check updates"}

def check_security_status():
    """Check basic security status"""
    issues = []
    
    # Check if firewall is running
    firewall = run_cmd("systemctl is-active firewalld ufw iptables 2>/dev/null")
    if not firewall:
        issues.append("No firewall detected")
    
    # Check failed login attempts
    failed_logins = run_cmd("grep 'Failed password' /var/log/auth.log 2>/dev/null | tail -5 | wc -l")
    if failed_logins and int(failed_logins) > 5:
        issues.append(f"{failed_logins} failed login attempts")
    
    # Check if SSH is running on default port
    ssh_status = run_cmd("systemctl is-active sshd 2>/dev/null")
    if ssh_status == "active":
        issues.append("SSH service active")
    
    return {"status": "WARNING" if issues else "OK", "issues": issues}

def check_system_errors():
    """Check for critical system errors"""
    errors = []
    
    # Check dmesg for errors
    dmesg_errors = run_cmd("dmesg -l err,crit,alert,emerg 2>/dev/null | tail -5")
    if dmesg_errors:
        errors.append("Kernel errors detected")
    
    # Check journal for service failures
    journal_errors = run_cmd("journalctl -p err --since '1 hour ago' --no-legend 2>/dev/null | wc -l")
    if journal_errors and int(journal_errors) > 10:
        errors.append(f"{journal_errors} errors in last hour")
    
    return {"status": "WARNING" if errors else "OK", "errors": errors}

def check_disk_space():
    """Check disk space usage"""
    warnings = []
    
    for partition in psutil.disk_partitions():
        if partition.fstype:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                percent = usage.percent
                if percent > 90:
                    warnings.append(f"{partition.mountpoint}: {percent}% full (CRITICAL)")
                elif percent > 80:
                    warnings.append(f"{partition.mountpoint}: {percent}% full (Warning)")
            except:
                pass
    
    return {"status": "WARNING" if warnings else "OK", "warnings": warnings}

def check_memory_pressure():
    """Check memory pressure"""
    mem = psutil.virtual_memory()
    
    if mem.percent > 95:
        return {"status": "CRITICAL", "percent": mem.percent, "message": "Memory critically low"}
    elif mem.percent > 85:
        return {"status": "WARNING", "percent": mem.percent, "message": "Memory usage high"}
    return {"status": "OK", "percent": mem.percent, "message": "Memory OK"}

def check_cpu_load():
    """Check CPU load"""
    try:
        load1, load5, load15 = os.getloadavg()
        cpu_count = psutil.cpu_count() or 1
        
        if load1 > cpu_count * 2:
            return {"status": "WARNING", "load": load1, "message": "High CPU load"}
        return {"status": "OK", "load": load1, "message": "CPU load normal"}
    except:
        return {"status": "UNKNOWN", "load": 0, "message": "Cannot check load"}

def check_temperatures():
    """Check system temperatures"""
    warnings = []
    
    try:
        temps = psutil.sensors_temperatures()
        for name, entries in temps.items():
            for entry in entries:
                if entry.current > 85:
                    warnings.append(f"{name}: {entry.current}°C (Hot)")
                elif entry.current > 75:
                    warnings.append(f"{name}: {entry.current}°C (Warm)")
    except:
        pass
    
    return {"status": "WARNING" if warnings else "OK", "warnings": warnings}

def check_zfs_btrfs():
    """Check ZFS/BTRFS pool status"""
    issues = []
    
    # Check ZFS
    zfs_status = run_cmd("zpool status -x 2>/dev/null")
    if zfs_status and "healthy" not in zfs_status.lower():
        issues.append("ZFS pool issues")
    
    # Check BTRFS
    btrfs_status = run_cmd("btrfs filesystem show 2>&1")
    if btrfs_status and "error" in btrfs_status.lower():
        issues.append("BTRFS issues")
    
    return {"status": "WARNING" if issues else "OK", "issues": issues}

def check_network_connectivity():
    """Check network connectivity"""
    try:
        # Check internet connectivity
        result = run_cmd("ping -c 1 -W 2 8.8.8.8 2>/dev/null")
        if result:
            return {"status": "OK", "message": "Internet connected"}
        return {"status": "WARNING", "message": "Internet unreachable"}
    except:
        return {"status": "UNKNOWN", "message": "Network check failed"}

def check_battery_health():
    """Check battery health if applicable"""
    try:
        battery = psutil.sensors_battery()
        if battery:
            if battery.percent < 10 and not battery.power_plugged:
                return {"status": "CRITICAL", "percent": battery.percent, "message": "Battery critically low"}
            elif battery.percent < 20 and not battery.power_plugged:
                return {"status": "WARNING", "percent": battery.percent, "message": "Battery low"}
        return {"status": "OK", "message": "Battery OK"}
    except:
        return {"status": "UNKNOWN", "message": "No battery detected"}

def check_audit_logs():
    """Check for security audit issues"""
    issues = []
    
    # Check for SELinux/AppArmor denials
    selinux_denials = run_cmd("ausearch -m avc -ts recent 2>/dev/null | wc -l")
    if selinux_denials and int(selinux_denials) > 0:
        issues.append(f"{selinux_denials} SELinux denials")
    
    return {"status": "WARNING" if issues else "OK", "issues": issues}

# ---------------------------------------------------
# MAIN
# ---------------------------------------------------
def main():
    # Run all checks
    checks = {
        "Systemd Services": check_systemd_services(),
        "Disk Health": check_disk_health(),
        "System Updates": check_system_updates(),
        "Security": check_security_status(),
        "System Errors": check_system_errors(),
        "Disk Space": check_disk_space(),
        "Memory": check_memory_pressure(),
        "CPU Load": check_cpu_load(),
        "Temperatures": check_temperatures(),
        "Filesystems": check_zfs_btrfs(),
        "Network": check_network_connectivity(),
        "Battery": check_battery_health(),
        "Audit": check_audit_logs(),
    }
    
    # Calculate overall status
    critical_count = sum(1 for c in checks.values() if c["status"] == "CRITICAL")
    warning_count = sum(1 for c in checks.values() if c["status"] == "WARNING")
    ok_count = sum(1 for c in checks.values() if c["status"] == "OK")
    
    # Determine overall health
    if critical_count > 0:
        overall_status = "CRITICAL"
        health_color = COLORS["red"]
        health_icon = ""
    elif warning_count > 0:
        overall_status = "WARNING"
        health_color = COLORS["yellow"]
        health_icon = ""
    else:
        overall_status = "OK"
        health_color = COLORS["green"]
        health_icon = ""

    integrity_icon = INTEGRITY_ICONS.get(overall_status, INTEGRITY_ICONS["UNKNOWN"])
    
    # Build tooltip
    lines = []
    border = f"<span foreground='{COLORS['bright_black']}'>{'─' * TOOLTIP_WIDTH}</span>"
    
    # Header
    lines.append(f"<span foreground='{health_color}'>{integrity_icon}</span> <span foreground='{COLORS['white']}'><b>System Integrity Check</b></span>")
    lines.append(f"<span foreground='{COLORS['bright_black']}'>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>")
    lines.append(border)
    
    # Overall status
    lines.append(f"<span foreground='{health_color}'>{health_icon}</span> <b>Overall Status:</b> <span foreground='{health_color}'>{overall_status}</span>")
    lines.append(f"   {ok_count} OK | {warning_count} Warnings | {critical_count} Critical")
    lines.append("")
    
    # Detailed checks
    for name, result in checks.items():
        if result["status"] == "OK":
            icon = ""
            color = COLORS["green"]
        elif result["status"] == "WARNING":
            icon = ""
            color = COLORS["yellow"]
        elif result["status"] == "CRITICAL":
            icon = ""
            color = COLORS["red"]
        else:
            icon = ""
            color = COLORS["bright_black"]
        
        lines.append(f"<span foreground='{color}'>{icon}</span> <b>{name}:</b> <span foreground='{color}'>{result['status']}</span>")
        
        # Add details for warnings/errors
        if result["status"] != "OK":
            if "issues" in result and result["issues"]:
                for issue in result["issues"][:3]:  # Limit to 3
                    lines.append(f"   <span foreground='{COLORS['bright_black']}'>└─ {issue}</span>")
            if "errors" in result and result["errors"]:
                for error in result["errors"][:3]:
                    lines.append(f"   <span foreground='{COLORS['bright_black']}'>└─ {error}</span>")
            if "warnings" in result and result["warnings"]:
                for warning in result["warnings"][:3]:
                    lines.append(f"   <span foreground='{COLORS['bright_black']}'>└─ {warning}</span>")
            if "message" in result and result["status"] != "OK":
                lines.append(f"   <span foreground='{COLORS['bright_black']}'>└─ {result['message']}</span>")
    
    lines.append(border)
    lines.append("<span size='small'>🖱️ LMB: Run detailed check</span>")
    
    # Text display
    issues = warning_count + critical_count

    if issues > 0:
        text = f"{integrity_icon} <span foreground='{health_color}'>{issues}</span>"
    else:
        text = f"{integrity_icon}"
    
    print(json.dumps({
        "text": text,
        "tooltip": f"<span size='12000'>{'\n'.join(lines)}</span>",
        "markup": "pango",
        "class": "system-integrity"
    }))

if __name__ == "__main__":
    main()
