#!/usr/bin/env python3
"""
GreenOps Agent v2.0.0
Cross-platform agent for Windows and Linux/macOS.
Monitors idle time, CPU, memory and reports to GreenOps server.

Supports:
  - Windows 10+ (uses Win32 API for idle detection)
  - Linux (X11/Wayland idle detection)
  - macOS 10.14+

Configuration (priority order):
  1. Environment variables (GREENOPS_*)
  2. Config file: C:\\ProgramData\\GreenOps\\config.json (Windows)
               or ~/.greenops/config.json (Linux/macOS)
  3. Defaults
"""
import ctypes
import hashlib
import json
import logging
import math
import os
import platform
import queue
import re
import signal
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

# ─────────────────────────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────────────────────────

def _get_log_dir() -> Path:
    if platform.system() == "Windows":
        base = Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData"))
        return base / "GreenOps"
    return Path.home() / ".greenops"


def setup_logging(log_dir: Path, log_level: str = "INFO") -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "agent.log"
    level = getattr(logging, log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    handlers = [
        logging.StreamHandler(sys.stdout),
    ]
    try:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    except (PermissionError, OSError):
        pass  # Log only to stdout if file not writable

    for h in handlers:
        h.setFormatter(formatter)

    logger = logging.getLogger("greenops.agent")
    logger.setLevel(level)
    for h in handlers:
        logger.addHandler(h)
    logger.propagate = False
    return logger


# ─────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────

DEFAULTS = {
    "server_url": "http://localhost:8000",
    "heartbeat_interval": 60,
    "idle_threshold": 300,
    "log_level": "INFO",
    "retry_max_attempts": 5,
    "retry_base_delay": 10,
    "offline_queue_max": 100,
    "agent_version": "2.0.0",
}


def _get_config_path() -> Path:
    if platform.system() == "Windows":
        base = Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData"))
        return base / "GreenOps" / "config.json"
    return Path.home() / ".greenops" / "config.json"


def load_config() -> Dict[str, Any]:
    config = dict(DEFAULTS)

    # Load from config file
    config_path = _get_config_path()
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_config = json.load(f)
            config.update(file_config)
        except (json.JSONDecodeError, OSError) as e:
            pass  # Use defaults

    # Environment variables override everything
    env_map = {
        "GREENOPS_SERVER_URL": "server_url",
        "GREENOPS_HEARTBEAT_INTERVAL": "heartbeat_interval",
        "GREENOPS_IDLE_THRESHOLD": "idle_threshold",
        "GREENOPS_LOG_LEVEL": "log_level",
        "GREENOPS_AGENT_TOKEN": "agent_token",
        "GREENOPS_MACHINE_ID": "machine_id",
    }
    for env_key, config_key in env_map.items():
        val = os.environ.get(env_key)
        if val:
            if config_key in ("heartbeat_interval", "idle_threshold", "machine_id"):
                try:
                    val = int(val)
                except ValueError:
                    pass
            config[config_key] = val

    # Normalize server URL (remove trailing slash)
    config["server_url"] = config["server_url"].rstrip("/")

    return config


def save_config(config: Dict[str, Any], config_path: Path):
    """Save config to file (only persisted keys)."""
    persist_keys = {"server_url", "heartbeat_interval", "idle_threshold", "log_level",
                    "agent_token", "machine_id"}
    to_save = {k: v for k, v in config.items() if k in persist_keys}
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=2)


# ─────────────────────────────────────────────────────────────────
# System Information
# ─────────────────────────────────────────────────────────────────

def get_mac_address() -> str:
    """Get primary MAC address - cross-platform."""
    system = platform.system()

    if system == "Windows":
        try:
            result = subprocess.run(
                ["getmac", "/fo", "csv", "/nh"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.strip().splitlines():
                # getmac output: "MAC","Transport Name"
                parts = line.strip().strip('"').split('","')
                if parts and re.match(r"[0-9A-Fa-f]{2}(-[0-9A-Fa-f]{2}){5}", parts[0]):
                    mac = parts[0].replace("-", ":").upper()
                    return mac
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass

        # Fallback: use uuid module
        mac_int = uuid.getnode()
        mac_str = ":".join(f"{(mac_int >> (i * 8)) & 0xFF:02X}" for i in range(5, -1, -1))
        return mac_str

    elif system == "Linux":
        # Try /sys/class/net for reliable MAC
        try:
            net_dir = Path("/sys/class/net")
            for iface in sorted(net_dir.iterdir()):
                if iface.name.startswith(("eth", "ens", "enp", "em", "eno")):
                    addr_file = iface / "address"
                    if addr_file.exists():
                        mac = addr_file.read_text().strip().upper()
                        if re.match(r"[0-9A-F]{2}(:[0-9A-F]{2}){5}", mac):
                            return mac
        except (PermissionError, OSError):
            pass

    elif system == "Darwin":
        try:
            result = subprocess.run(
                ["networksetup", "-getmacaddress", "en0"],
                capture_output=True, text=True, timeout=10,
            )
            match = re.search(r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", result.stdout)
            if match:
                return match.group(0).upper()
        except Exception:
            pass

    # Last resort: uuid-based
    mac_int = uuid.getnode()
    return ":".join(f"{(mac_int >> (i * 8)) & 0xFF:02X}" for i in range(5, -1, -1))


def get_hostname() -> str:
    """Get machine hostname."""
    return socket.gethostname()


def get_os_info() -> tuple:
    """Returns (os_type, os_version)."""
    system = platform.system()
    if system == "Windows":
        version = platform.version()
        release = platform.release()
        return "Windows", f"Windows {release} ({version})"
    elif system == "Linux":
        try:
            with open("/etc/os-release", "r") as f:
                info = {}
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        info[k] = v.strip('"')
            return "Linux", info.get("PRETTY_NAME", f"Linux {platform.release()}")
        except (FileNotFoundError, Exception):
            return "Linux", f"Linux {platform.release()}"
    elif system == "Darwin":
        return "macOS", f"macOS {platform.mac_ver()[0]}"
    else:
        return system, platform.version()


def get_local_ip() -> Optional[str]:
    """Get local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────
# Idle Detection - Platform Specific
# ─────────────────────────────────────────────────────────────────

def get_idle_seconds_windows() -> int:
    """Get idle time on Windows using Win32 LASTINPUTINFO."""
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_uint),
            ("dwTime", ctypes.c_uint),
        ]

    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
        millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return max(0, millis // 1000)
    return 0


def get_idle_seconds_linux() -> int:
    """Get idle time on Linux using xprintidle or dbus."""
    # Try xprintidle (X11)
    try:
        result = subprocess.run(
            ["xprintidle"], capture_output=True, text=True, timeout=5,
            env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")},
        )
        if result.returncode == 0:
            return int(result.stdout.strip()) // 1000
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass

    # Try xssstate
    try:
        result = subprocess.run(
            ["xssstate", "-i"], capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return int(result.stdout.strip()) // 1000
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass

    # Headless/server: use /proc/stat cpu idle time as approximation
    try:
        with open("/proc/uptime", "r") as f:
            uptime = float(f.read().split()[0])
        # On server, assume always idle if no display
        return int(uptime)
    except Exception:
        return 0


def get_idle_seconds_macos() -> int:
    """Get idle time on macOS using HID."""
    try:
        result = subprocess.run(
            ["ioreg", "-c", "IOHIDSystem"],
            capture_output=True, text=True, timeout=10,
        )
        match = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', result.stdout)
        if match:
            nanoseconds = int(match.group(1))
            return nanoseconds // 1_000_000_000
    except Exception:
        pass
    return 0


def get_idle_seconds() -> int:
    """Get system idle seconds - cross-platform."""
    system = platform.system()
    try:
        if system == "Windows":
            return get_idle_seconds_windows()
        elif system == "Linux":
            return get_idle_seconds_linux()
        elif system == "Darwin":
            return get_idle_seconds_macos()
    except Exception:
        pass
    return 0


# ─────────────────────────────────────────────────────────────────
# CPU/Memory - Platform Specific
# ─────────────────────────────────────────────────────────────────

def get_cpu_percent() -> Optional[float]:
    """Get CPU usage percentage."""
    try:
        import psutil
        return psutil.cpu_percent(interval=1)
    except ImportError:
        pass

    # Fallback without psutil
    system = platform.system()
    if system == "Windows":
        try:
            result = subprocess.run(
                ["wmic", "cpu", "get", "loadpercentage", "/value"],
                capture_output=True, text=True, timeout=10,
            )
            match = re.search(r"LoadPercentage=(\d+)", result.stdout)
            if match:
                return float(match.group(1))
        except Exception:
            pass
    elif system == "Linux":
        try:
            with open("/proc/stat") as f:
                line = f.readline()
            vals = [int(x) for x in line.split()[1:]]
            idle = vals[3]
            total = sum(vals)
            time.sleep(0.1)
            with open("/proc/stat") as f:
                line = f.readline()
            vals2 = [int(x) for x in line.split()[1:]]
            idle2 = vals2[3]
            total2 = sum(vals2)
            return round((1 - (idle2 - idle) / (total2 - total)) * 100, 1)
        except Exception:
            pass
    return None


def get_memory_percent() -> Optional[float]:
    """Get memory usage percentage."""
    try:
        import psutil
        return psutil.virtual_memory().percent
    except ImportError:
        pass

    system = platform.system()
    if system == "Linux":
        try:
            with open("/proc/meminfo") as f:
                lines = f.readlines()
            info = {}
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    info[parts[0].rstrip(":")] = int(parts[1])
            total = info.get("MemTotal", 0)
            available = info.get("MemAvailable", info.get("MemFree", 0))
            if total > 0:
                return round((1 - available / total) * 100, 1)
        except Exception:
            pass
    return None


# ─────────────────────────────────────────────────────────────────
# HTTP Client
# ─────────────────────────────────────────────────────────────────

class GreenOpsHTTPClient:
    """Simple HTTP client using stdlib urllib - no external dependencies."""

    def __init__(self, server_url: str, token: Optional[str] = None, timeout: int = 30):
        self.server_url = server_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        data: Optional[dict] = None,
        token: Optional[str] = None,
    ) -> dict:
        url = f"{self.server_url}{path}"
        body = json.dumps(data).encode("utf-8") if data else None

        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"GreenOps-Agent/{DEFAULTS['agent_version']} ({platform.system()})",
            "Accept": "application/json",
        }

        auth_token = token or self.token
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        req = UrlRequest(url, data=body, headers=headers, method=method)
        resp = urlopen(req, timeout=self.timeout)
        response_body = resp.read().decode("utf-8")
        return json.loads(response_body) if response_body else {}

    def post(self, path: str, data: dict, token: Optional[str] = None) -> dict:
        return self._request("POST", path, data, token)

    def get(self, path: str, token: Optional[str] = None) -> dict:
        return self._request("GET", path, None, token)


# ─────────────────────────────────────────────────────────────────
# Offline Queue
# ─────────────────────────────────────────────────────────────────

class OfflineQueue:
    """Persistent queue for heartbeats when server is unreachable."""

    def __init__(self, queue_file: Path, max_size: int = 100):
        self.queue_file = queue_file
        self.max_size = max_size
        self._queue: list = self._load()

    def _load(self) -> list:
        if self.queue_file.exists():
            try:
                with open(self.queue_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save(self):
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.queue_file, "w", encoding="utf-8") as f:
            json.dump(self._queue, f)

    def push(self, heartbeat: dict):
        if len(self._queue) >= self.max_size:
            self._queue.pop(0)  # Drop oldest
        self._queue.append(heartbeat)
        self._save()

    def flush(self) -> list:
        items = list(self._queue)
        self._queue = []
        self._save()
        return items

    def size(self) -> int:
        return len(self._queue)


# ─────────────────────────────────────────────────────────────────
# Main Agent
# ─────────────────────────────────────────────────────────────────

class GreenOpsAgent:
    def __init__(self):
        self.config = load_config()
        self.log_dir = _get_log_dir()
        self.logger = setup_logging(self.log_dir, self.config.get("log_level", "INFO"))
        self.config_path = _get_config_path()
        self.client = GreenOpsHTTPClient(self.config["server_url"])
        self.offline_queue = OfflineQueue(
            self.log_dir / "offline_queue.json",
            self.config.get("offline_queue_max", 100),
        )
        self._running = False
        self._consecutive_failures = 0

    def register(self) -> bool:
        """Register this machine with the server."""
        # Check if already registered
        if self.config.get("agent_token") and self.config.get("machine_id"):
            self.logger.info("Already registered, machine_id=%s", self.config["machine_id"])
            return True

        os_type, os_version = get_os_info()
        mac = get_mac_address()
        hostname = get_hostname()

        payload = {
            "mac_address": mac,
            "hostname": hostname,
            "os_type": os_type,
            "os_version": os_version,
            "agent_version": self.config.get("agent_version", DEFAULTS["agent_version"]),
        }

        self.logger.info(
            "Registering: hostname=%s mac=%s os=%s %s",
            hostname, mac, os_type, os_version,
        )

        for attempt in range(1, 6):
            try:
                resp = self.client.post("/api/agents/register", payload)
                token = resp.get("token")
                machine_id = resp.get("machine_id")

                if not token or not machine_id:
                    raise ValueError("Invalid registration response")

                self.config["agent_token"] = token
                self.config["machine_id"] = machine_id
                self.client.token = token
                save_config(self.config, self.config_path)

                self.logger.info("Registered successfully, machine_id=%s", machine_id)
                return True

            except HTTPError as e:
                body = e.read().decode("utf-8", errors="replace") if e.fp else ""
                self.logger.error("Registration failed HTTP %d: %s", e.code, body)
                if e.code in (400, 422):
                    # Bad request - don't retry
                    return False
            except (URLError, OSError) as e:
                self.logger.warning("Registration attempt %d/%d failed: %s", attempt, 5, e)
            except Exception as e:
                self.logger.error("Unexpected registration error: %s", e)

            if attempt < 5:
                delay = min(self.config["retry_base_delay"] * (2 ** (attempt - 1)), 300)
                self.logger.info("Retrying in %ds...", delay)
                time.sleep(delay)

        self.logger.error("Registration failed after 5 attempts")
        return False

    def send_heartbeat(self, idle_seconds: int, cpu: Optional[float], memory: Optional[float]) -> bool:
        """Send heartbeat to server. Returns True on success."""
        payload = {
            "idle_seconds": idle_seconds,
            "cpu_usage": cpu,
            "memory_usage": memory,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ip_address": get_local_ip(),
        }

        token = self.config.get("agent_token")
        if not token:
            self.logger.error("No agent token - need to re-register")
            return False

        try:
            resp = self.client.post("/api/agents/heartbeat", payload, token=token)
            status = resp.get("status", "")
            machine_status = resp.get("machine_status", "")
            energy = resp.get("energy_wasted_kwh", 0)

            self.logger.info(
                "Heartbeat OK | status=%s idle=%ds cpu=%s%% mem=%s%% energy=%.4f kWh",
                machine_status,
                idle_seconds,
                f"{cpu:.1f}" if cpu is not None else "N/A",
                f"{memory:.1f}" if memory is not None else "N/A",
                energy,
            )
            self._consecutive_failures = 0
            return True

        except HTTPError as e:
            if e.code == 401:
                self.logger.warning("Token unauthorized - clearing for re-registration")
                self.config.pop("agent_token", None)
                self.config.pop("machine_id", None)
                save_config(self.config, self.config_path)
            else:
                self.logger.warning("Heartbeat HTTP error %d", e.code)
        except (URLError, OSError) as e:
            self.logger.warning("Heartbeat failed (offline): %s", e)
            self.offline_queue.push(payload)
        except Exception as e:
            self.logger.error("Heartbeat unexpected error: %s", e)

        self._consecutive_failures += 1
        return False

    def flush_offline_queue(self):
        """Send queued heartbeats when connection is restored."""
        queued = self.offline_queue.flush()
        if not queued:
            return

        self.logger.info("Flushing %d queued heartbeats", len(queued))
        token = self.config.get("agent_token")
        failed = []

        for payload in queued:
            try:
                self.client.post("/api/agents/heartbeat", payload, token=token)
            except Exception:
                failed.append(payload)

        if failed:
            self.logger.warning("Failed to flush %d heartbeats, re-queuing", len(failed))
            for p in failed:
                self.offline_queue.push(p)

    def run(self):
        """Main agent loop."""
        self.logger.info("GreenOps Agent v%s starting on %s", DEFAULTS["agent_version"], platform.system())

        # Register
        if not self.register():
            self.logger.error("Could not register. Exiting.")
            sys.exit(1)

        self._running = True
        interval = self.config.get("heartbeat_interval", 60)
        self.logger.info("Heartbeat interval: %ds", interval)

        # Signal handlers for graceful shutdown
        def _shutdown(sig, frame):
            self.logger.info("Received signal %s, shutting down...", sig)
            self._running = False

        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)

        while self._running:
            try:
                idle_seconds = get_idle_seconds()
                cpu = get_cpu_percent()
                memory = get_memory_percent()

                # Try to flush offline queue if we have items
                if self.offline_queue.size() > 0:
                    self.flush_offline_queue()

                # Check if we need to re-register
                if not self.config.get("agent_token"):
                    self.logger.info("Re-registering...")
                    if not self.register():
                        time.sleep(60)
                        continue

                self.send_heartbeat(idle_seconds, cpu, memory)

            except Exception as e:
                self.logger.error("Unexpected error in main loop: %s", e, exc_info=True)

            # Sleep in small increments to allow clean shutdown
            elapsed = 0
            while elapsed < interval and self._running:
                time.sleep(min(5, interval - elapsed))
                elapsed += 5

        self.logger.info("GreenOps Agent stopped.")


# ─────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    agent = GreenOpsAgent()
    agent.run()
