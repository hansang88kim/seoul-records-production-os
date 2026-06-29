"""
services/remote_control/health_check.py — Streamlit/Tailscale health (v0.9.1).

Checks whether the Streamlit frontend is responding on the configured port and
(optionally) whether Tailscale is available. No secrets involved.
"""
from __future__ import annotations

import socket


DEFAULT_PORT = 8501
DEFAULT_ADDRESS = "127.0.0.1"


def is_port_open(host: str = DEFAULT_ADDRESS, port: int = DEFAULT_PORT,
                 timeout: float = 2.0) -> bool:
    """Quick TCP check — is something listening on the port?"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def http_status(host: str = DEFAULT_ADDRESS, port: int = DEFAULT_PORT,
                timeout: float = 3.0) -> int | None:
    """
    Return the HTTP status code from http://host:port/ or None if unreachable.
    Uses urllib (stdlib) so there is no extra dependency.
    """
    import urllib.request
    import urllib.error
    url = f"http://{host}:{port}/"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def check_streamlit(host: str = DEFAULT_ADDRESS, port: int = DEFAULT_PORT) -> dict:
    """Combined health snapshot for Streamlit."""
    port_open = is_port_open(host, port)
    code = http_status(host, port) if port_open else None
    running = bool(port_open and code == 200)
    return {
        "running": running,
        "port_open": port_open,
        "http_status": code,
        "host": host,
        "port": port,
    }


def tailscale_status() -> dict:
    """
    Optional Tailscale availability check. Never required. Returns availability
    only — no account data is read.
    """
    import shutil
    import subprocess
    exe = shutil.which("tailscale")
    if not exe:
        return {"available": False, "status": None}
    try:
        out = subprocess.run([exe, "status"], capture_output=True, text=True, timeout=5)
        ok = out.returncode == 0
        return {"available": True, "status": "up" if ok else "down"}
    except Exception:
        return {"available": True, "status": "unknown"}
