"""
services/remote_control/remote_status_models.py — supervisor status vocab (v0.9.1).

Plain-dict status models for the supervisor + telegram control plane.
"""
from __future__ import annotations

from datetime import datetime, timezone


# Supervisor statuses
SUP_STARTING = "starting"
SUP_HEALTHY = "healthy"
SUP_RESTARTING = "restarting"
SUP_DEGRADED = "degraded"
SUP_STOPPED = "stopped"

# Streamlit health
APP_RUNNING = "running"
APP_DOWN = "down"
APP_UNKNOWN = "unknown"


def empty_supervisor_status() -> dict:
    return {
        "status": SUP_STARTING,
        "streamlit_running": False,
        "streamlit_pid": None,
        "streamlit_port": 8501,
        "streamlit_http_status": None,
        "last_health_check_at": None,
        "last_restart_at": None,
        "restart_count_last_hour": 0,
        "tailscale_status": None,
        "active_jobs_summary": {},
        "last_error": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
