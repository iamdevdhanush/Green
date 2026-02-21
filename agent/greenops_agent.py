#!/usr/bin/env python3
"""
GreenOps Agent v1.0
Enterprise Energy Intelligence — Device Daemon

Runs on monitored machines. Reports telemetry every 60 seconds.
Handles idle-only remote shutdown commands with local validation.

Usage:
    python greenops_agent.py --server https://your-server.com
    python greenops_agent.py --server http://localhost:8000 --debug
"""
import argparse
import json
import logging
import os
import platform
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

# ── Config ───────────────────────────────────────────────────────────────────

HEARTBEAT_INTERVAL = 60       # seconds between heartbeats
COMMAND_POLL_INTERVAL = 30    # seconds between command polls
IDLE_THRESHOLD_MINUTES = 15   # default idle threshold before shutdown allowed
CONFIG_FILE = Path.home() / ".greenops" / "agent.json"
API_VERSION = "v1"

# ── Logging ───────────────────────────────────────────────────────────────────

def setup_logging(debug: bool = False):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )

log = logging.getLogger("greenops-agent")

# ── System Detection ──────────────────────────────────────────────────────────

def get_mac_address() -> str:
    """Get primary network interface MAC address."""
    mac = uuid.getnode()
    if mac >> 40 == 0xFF:
        # Random MAC — not reliable
        raise RuntimeError("Could not determine a stable MAC address")
    return ":".join(
        f"{(mac >> (5 - i) * 8) & 0xFF:02X}" for i in range(6)
    )


def get_cpu_info() -> str:
    """Get CPU model string."""
    system = platform.system()
    if system == "Linux":
        try:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        return line.split(":")[1].strip()
        except Exception:
            pass
    elif system == "Darwin":
        try:
            out = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"], text=True
            )
            return out.strip()
        except Exception:
            pass
    return platform.processor() or "Unknown"


def get_ram_gb() -> float:
    """Get total RAM in GB."""
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024 ** 3), 2)
    except ImportError:
        pass
    system = platform.system()
    if system == "Linux":
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return round(kb / (1024 ** 2), 2)
        except Exception:
            pass
    return 0.0


def get_ip_address() -> str:
    """Get primary IP address."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_system_info() -> dict:
    return {
        "mac_address": get_mac_address(),
        "hostname": platform.node(),
        "os_version": f"{platform.system()} {platform.release()}",
        "cpu_info": get_cpu_info(),
        "ram_gb": get_ram_gb(),
        "ip_address": get_ip_address(),
    }


# ── Idle Detection ────────────────────────────────────────────────────────────

def get_idle_minutes() -> int:
    """Get system idle time in minutes."""
    system = platform.system()

    if system == "Linux":
        # Try xprintidle for desktop systems
        try:
            out = subprocess.check_output(["xprintidle"], stderr=subprocess.DEVNULL, text=True)
            ms = int(out.strip())
            return ms // 60000
        except Exception:
            pass
        # For servers: check who output for last activity
        try:
            out = subprocess.check_output(["who", "-u"], stderr=subprocess.DEVNULL, text=True)
            if not out.strip():
                # Nobody logged in — consider idle
                return 999
        except Exception:
            pass

    elif system == "Darwin":
        try:
            out = subprocess.check_output(
                ["ioreg", "-c", "IOHIDSystem"], text=True
            )
            for line in out.split("\n"):
                if "HIDIdleTime" in line:
                    ns = int(line.split("=")[1].strip())
                    return ns // 60_000_000_000
        except Exception:
            pass

    elif system == "Windows":
        try:
            import ctypes
            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(lii)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
            idle_ms = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
            return idle_ms // 60000
        except Exception:
            pass

    return 0


def get_cpu_percent() -> float:
    """Get CPU usage percentage."""
    try:
        import psutil
        return psutil.cpu_percent(interval=1)
    except ImportError:
        pass

    if platform.system() == "Linux":
        try:
            with open("/proc/stat") as f:
                line = f.readline()
            vals = list(map(int, line.split()[1:]))
            idle1 = vals[3]
            total1 = sum(vals)
            time.sleep(0.5)
            with open("/proc/stat") as f:
                line = f.readline()
            vals = list(map(int, line.split()[1:]))
            idle2 = vals[3]
            total2 = sum(vals)
            return round(100 * (1 - (idle2 - idle1) / (total2 - total1)), 1)
        except Exception:
            pass
    return 0.0


def get_ram_percent() -> float:
    """Get RAM usage percentage."""
    try:
        import psutil
        return psutil.virtual_memory().percent
    except ImportError:
        pass
    return 0.0


# ── Shutdown ──────────────────────────────────────────────────────────────────

def perform_shutdown():
    """Execute system shutdown."""
    system = platform.system()
    log.warning("Executing system shutdown per GreenOps command")

    if system == "Linux" or system == "Darwin":
        os.system("shutdown -h now")
    elif system == "Windows":
        os.system("shutdown /s /f /t 0")
    else:
        log.error(f"Unsupported OS for shutdown: {system}")


# ── API Client ────────────────────────────────────────────────────────────────

class GreenOpsClient:
    def __init__(self, server_url: str, api_key: Optional[str] = None):
        self.base = server_url.rstrip("/") + f"/api/{API_VERSION}"
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "GreenOps-Agent/1.0",
        })

    def _headers(self) -> dict:
        h = {}
        if self.api_key:
            h["X-API-Key"] = self.api_key
        return h

    def register(self, info: dict) -> dict:
        resp = self.session.post(
            f"{self.base}/agents/register",
            json=info,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def heartbeat(self, idle_minutes: int, cpu_percent: float, ram_percent: float, ip: str) -> dict:
        resp = self.session.post(
            f"{self.base}/agents/heartbeat",
            json={
                "idle_minutes": idle_minutes,
                "cpu_percent": cpu_percent,
                "ram_percent": ram_percent,
                "ip_address": ip,
            },
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def poll_command(self) -> dict:
        resp = self.session.get(
            f"{self.base}/agents/commands/poll",
            headers=self._headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def report_command(
        self, command_id: str, executed: bool, reason: Optional[str] = None, idle_minutes: Optional[int] = None
    ) -> None:
        self.session.post(
            f"{self.base}/agents/commands/result",
            json={
                "command_id": command_id,
                "executed": executed,
                "reason": reason,
                "idle_minutes_at_execution": idle_minutes,
            },
            headers=self._headers(),
            timeout=10,
        )


# ── Config persistence ────────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {}


def save_config(data: dict):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


# ── Agent Main Loop ───────────────────────────────────────────────────────────

class GreenOpsAgent:
    def __init__(self, server_url: str, debug: bool = False):
        self.server_url = server_url
        self.debug = debug
        self.running = False
        self.config = load_config()
        self.client: Optional[GreenOpsClient] = None

        signal.signal(signal.SIGINT, self._shutdown_handler)
        signal.signal(signal.SIGTERM, self._shutdown_handler)

    def _shutdown_handler(self, signum, frame):
        log.info("Agent stopping...")
        self.running = False

    def register(self) -> bool:
        """Register or re-register with the GreenOps server."""
        log.info("Collecting system information...")
        try:
            info = get_system_info()
        except Exception as e:
            log.error(f"Failed to collect system info: {e}")
            return False

        log.info(f"Registering machine: {info['hostname']} ({info['mac_address']})")

        try:
            client = GreenOpsClient(self.server_url)
            result = client.register(info)

            self.config["machine_id"] = str(result["machine_id"])
            self.config["api_key"] = result["api_key"]
            self.config["server_url"] = self.server_url
            save_config(self.config)

            log.info(f"✓ Registered: machine_id={result['machine_id']}")
            log.info(f"✓ API Key saved to {CONFIG_FILE}")
            return True

        except requests.RequestException as e:
            log.error(f"Registration failed: {e}")
            return False

    def run(self):
        """Main agent loop."""
        # Check config
        if not self.config.get("api_key"):
            log.info("No credentials found. Registering...")
            if not self.register():
                log.error("Cannot start without registration. Exiting.")
                sys.exit(1)

        api_key = self.config["api_key"]
        self.client = GreenOpsClient(self.server_url, api_key)

        log.info(f"GreenOps Agent started. Server: {self.server_url}")
        log.info(f"Machine ID: {self.config['machine_id']}")
        self.running = True

        last_heartbeat = 0
        last_command_poll = 0

        while self.running:
            now = time.time()

            # Heartbeat
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                try:
                    idle = get_idle_minutes()
                    cpu = get_cpu_percent()
                    ram = get_ram_percent()
                    ip = get_ip_address()

                    result = self.client.heartbeat(idle, cpu, ram, ip)
                    log.debug(f"Heartbeat: idle={idle}m cpu={cpu}% ram={ram}%")
                    last_heartbeat = now

                    # If server flagged a command, poll immediately
                    if result.get("has_pending_command"):
                        last_command_poll = 0

                except requests.RequestException as e:
                    log.warning(f"Heartbeat failed: {e}")

            # Command poll
            if now - last_command_poll >= COMMAND_POLL_INTERVAL:
                try:
                    cmd = self.client.poll_command()
                    last_command_poll = now

                    if cmd.get("has_command"):
                        self._handle_command(cmd)

                except requests.RequestException as e:
                    log.warning(f"Command poll failed: {e}")

            time.sleep(5)

    def _handle_command(self, cmd: dict):
        """
        Handle a remote shutdown command.
        CRITICAL: Re-validates idle threshold locally before executing.
        """
        command_id = cmd["command_id"]
        threshold = cmd.get("idle_threshold_minutes", IDLE_THRESHOLD_MINUTES)
        command_type = cmd.get("command_type", "shutdown")

        log.info(f"Received command: {command_type} (id={command_id}, threshold={threshold}m)")

        if command_type != "shutdown":
            log.warning(f"Unknown command type: {command_type}. Rejecting.")
            try:
                self.client.report_command(command_id, False, f"Unknown command type: {command_type}")
            except Exception:
                pass
            return

        # ── Local idle re-validation (SECURITY CRITICAL) ──────────────────
        current_idle = get_idle_minutes()
        log.info(f"Local idle check: {current_idle}m (threshold: {threshold}m)")

        if current_idle < threshold:
            reason = f"Machine not idle. Current idle: {current_idle}m, required: {threshold}m"
            log.warning(f"Shutdown REJECTED — {reason}")
            try:
                self.client.report_command(command_id, False, reason, current_idle)
            except Exception:
                pass
            return

        # Idle threshold met — execute
        log.warning(f"Executing shutdown (idle={current_idle}m >= threshold={threshold}m)")
        try:
            self.client.report_command(command_id, True, None, current_idle)
        except Exception as e:
            log.error(f"Failed to report command result: {e}")
            # Continue with shutdown anyway

        time.sleep(2)  # Allow report to transmit
        perform_shutdown()


# ── Entry Point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="GreenOps Agent — Enterprise Energy Intelligence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python greenops_agent.py --server http://localhost:8000
  python greenops_agent.py --server https://greenops.company.com --debug
  python greenops_agent.py --register-only --server http://localhost:8000
        """,
    )
    parser.add_argument("--server", required=True, help="GreenOps server URL")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--register-only", action="store_true", help="Register and exit")
    args = parser.parse_args()

    setup_logging(args.debug)

    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    log.info("  GreenOps Agent v1.0 — Energy Intelligence")
    log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    agent = GreenOpsAgent(args.server, args.debug)

    if args.register_only:
        success = agent.register()
        sys.exit(0 if success else 1)
    else:
        agent.run()


if __name__ == "__main__":
    main()
