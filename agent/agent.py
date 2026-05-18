#!/usr/bin/env python3
"""
AssetManager Agent
Collects hardware/software inventory and reports to the AssetManager server.

Usage:
    assetmanager-agent [--config agent.ini] [--once]

Config file (agent.ini):
    [server]
    url = http://your-server:5000
    api_key = YOUR_API_KEY

    [agent]
    interval = 3600     ; seconds between check-ins
    verify_ssl = true   ; set false for self-signed certs
"""

import os
import sys
import json
import time
import socket
import ssl
import hashlib
import logging
import platform
import argparse
import configparser
import urllib.request
import urllib.error

try:
    import psutil
except ImportError:
    print("ERROR: psutil is required. Run: pip install psutil")
    sys.exit(1)

__version__ = "1.0.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("assetmanager-agent")


# ── Hardware collection ───────────────────────────────────────────────────────

def _collect_cpu():
    try:
        freq = psutil.cpu_freq()
        return {
            "model": platform.processor() or "Unknown",
            "cores_physical": psutil.cpu_count(logical=False),
            "cores_logical": psutil.cpu_count(logical=True),
            "frequency_mhz": round(freq.current) if freq else None,
        }
    except Exception:
        return {}


def _collect_memory():
    try:
        m = psutil.virtual_memory()
        return {
            "total_gb": round(m.total / 1024 ** 3, 2),
            "available_gb": round(m.available / 1024 ** 3, 2),
            "percent_used": m.percent,
        }
    except Exception:
        return {}


def _collect_disks():
    disks = []
    try:
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "filesystem": part.fstype,
                    "total_gb": round(usage.total / 1024 ** 3, 2),
                    "used_gb": round(usage.used / 1024 ** 3, 2),
                    "free_gb": round(usage.free / 1024 ** 3, 2),
                    "percent_used": usage.percent,
                })
            except (PermissionError, OSError):
                pass
    except Exception:
        pass
    return disks


def _collect_network():
    interfaces = []
    try:
        for name, addrs in psutil.net_if_addrs().items():
            ip4 = next(
                (a.address for a in addrs
                 if str(a.family) in ("AddressFamily.AF_INET", "2")),
                None,
            )
            mac = next(
                (a.address for a in addrs
                 if str(a.family) in ("AddressFamily.AF_PACKET", "AddressFamily.AF_LINK", "17", "18")),
                None,
            )
            if ip4 and ip4 != "127.0.0.1":
                interfaces.append({"interface": name, "ip": ip4, "mac": mac})
    except Exception:
        pass
    return interfaces


def collect_hardware():
    return {
        "cpu": _collect_cpu(),
        "memory": _collect_memory(),
        "disks": _collect_disks(),
        "network": _collect_network(),
    }


# ── Software collection ───────────────────────────────────────────────────────

def _collect_software_windows():
    software = []
    try:
        import winreg
        hives = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        seen = set()
        for hive, path in hives:
            try:
                reg = winreg.OpenKey(hive, path)
                count = winreg.QueryInfoKey(reg)[0]
                for i in range(count):
                    try:
                        sub_name = winreg.EnumKey(reg, i)
                        sub = winreg.OpenKey(reg, sub_name)
                        try:
                            name = winreg.QueryValueEx(sub, "DisplayName")[0].strip()
                        except OSError:
                            continue
                        if not name or name in seen:
                            continue
                        seen.add(name)
                        version = publisher = ""
                        try: version   = winreg.QueryValueEx(sub, "DisplayVersion")[0]
                        except OSError: pass
                        try: publisher = winreg.QueryValueEx(sub, "Publisher")[0]
                        except OSError: pass
                        software.append({"name": name, "version": version, "publisher": publisher})
                    except Exception:
                        pass
            except Exception:
                pass
    except ImportError:
        pass
    return sorted(software, key=lambda x: x["name"].lower())


def _collect_software_linux():
    import subprocess
    software = []

    # dpkg (Debian / Ubuntu)
    try:
        out = subprocess.check_output(
            ["dpkg-query", "-W", "-f=${Package}\t${Version}\t${Maintainer}\n"],
            stderr=subprocess.DEVNULL, text=True,
        )
        for line in out.strip().splitlines():
            parts = line.split("\t")
            software.append({
                "name": parts[0],
                "version": parts[1] if len(parts) > 1 else "",
                "publisher": parts[2] if len(parts) > 2 else "",
            })
        if software:
            return sorted(software, key=lambda x: x["name"].lower())
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # rpm (RHEL / CentOS / Fedora)
    try:
        out = subprocess.check_output(
            ["rpm", "-qa", "--queryformat", "%{NAME}\t%{VERSION}\t%{VENDOR}\n"],
            stderr=subprocess.DEVNULL, text=True,
        )
        for line in out.strip().splitlines():
            parts = line.split("\t")
            software.append({
                "name": parts[0],
                "version": parts[1] if len(parts) > 1 else "",
                "publisher": parts[2] if len(parts) > 2 else "",
            })
        if software:
            return sorted(software, key=lambda x: x["name"].lower())
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return software


def collect_software():
    system = platform.system()
    if system == "Windows":
        return _collect_software_windows()
    if system == "Linux":
        return _collect_software_linux()
    return []


# ── Network helpers ───────────────────────────────────────────────────────────

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


# ── Check-in ──────────────────────────────────────────────────────────────────

def checkin(server_url, api_key, verify_ssl=True):
    log.info("Collecting inventory…")
    hardware = collect_hardware()
    software = collect_software()
    log.info("Found %d software packages.", len(software))

    payload = json.dumps({
        "hostname": socket.gethostname(),
        "ip_address": get_local_ip(),
        "os_name": platform.system(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "hardware": hardware,
        "software": software,
    }).encode("utf-8")

    url = server_url.rstrip("/") + "/api/agent/checkin"

    ctx = ssl.create_default_context()
    if not verify_ssl:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": f"AssetManager-Agent/{__version__}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            body = json.loads(resp.read().decode())
            log.info("Check-in OK: %s", body.get("status", "ok"))
            return True
    except urllib.error.HTTPError as exc:
        log.error("Check-in failed: HTTP %d %s", exc.code, exc.reason)
    except urllib.error.URLError as exc:
        log.error("Check-in failed: %s", exc.reason)
    except Exception as exc:
        log.error("Check-in error: %s", exc)
    return False


# ── Config ────────────────────────────────────────────────────────────────────

def load_config(path):
    if not os.path.exists(path):
        log.error("Config file not found: %s", path)
        sys.exit(1)
    cfg = configparser.ConfigParser()
    cfg.read(path)
    server_url = cfg.get("server", "url", fallback="").strip()
    api_key    = cfg.get("server", "api_key", fallback="").strip()
    interval   = cfg.getint("agent", "interval", fallback=3600)
    verify_ssl = cfg.getboolean("agent", "verify_ssl", fallback=True)
    if not server_url or not api_key:
        log.error("Config is missing server.url or server.api_key")
        sys.exit(1)
    return server_url, api_key, interval, verify_ssl


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AssetManager Agent")
    parser.add_argument("--config", default="agent.ini", help="Path to config file (default: agent.ini)")
    parser.add_argument("--once", action="store_true", help="Run a single check-in and exit")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    server_url, api_key, interval, verify_ssl = load_config(args.config)

    log.info("AssetManager Agent v%s", __version__)
    log.info("Server : %s", server_url)
    log.info("Interval: %ds | SSL verify: %s", interval, verify_ssl)

    checkin(server_url, api_key, verify_ssl)

    if args.once:
        return

    while True:
        log.info("Sleeping %ds until next check-in…", interval)
        time.sleep(interval)
        checkin(server_url, api_key, verify_ssl)


if __name__ == "__main__":
    main()
