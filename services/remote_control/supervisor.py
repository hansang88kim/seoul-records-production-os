"""
services/remote_control/supervisor.py — local supervisor core (v0.9.1).

Watches the Streamlit frontend, restarts it when it's down (with a restart-loop
guard), summarizes active jobs, and writes supervisor_status.json +
supervisor_log.jsonl. Runs as a SEPARATE process from Streamlit so it survives
a frontend crash. No secrets are ever written.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from services.remote_control import health_check as HC
from services.remote_control import process_manager as PM
from services.remote_control import remote_status_models as RS
from services.security.redaction import redact_text


# Config defaults (overridable via env in the worker)
MAX_RESTARTS_PER_HOUR = 5
HEALTH_CHECK_INTERVAL_SECONDS = 30
AUTO_RESTART_STREAMLIT = True


def _rc_dir() -> Path:
    d = Path(__file__).resolve().parent.parent.parent / "outputs" / "remote_control"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _status_path() -> Path:
    return _rc_dir() / "supervisor_status.json"


def _log_path() -> Path:
    return _rc_dir() / "supervisor_log.jsonl"


def log(message: str, level: str = "info"):
    """Append a SANITIZED supervisor log line."""
    line = json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level, "message": redact_text(message),
    }, ensure_ascii=False)
    with _log_path().open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_status() -> dict:
    p = _status_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return RS.empty_supervisor_status()


def write_status(status: dict) -> dict:
    status["updated_at"] = datetime.now(timezone.utc).isoformat()
    _status_path().write_text(json.dumps(status, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    return status


def _restart_times_path() -> Path:
    return _rc_dir() / "_restart_times.json"


def _recent_restart_count() -> int:
    """How many restarts happened in the last hour (loop guard)."""
    p = _restart_times_path()
    if not p.exists():
        return 0
    try:
        times = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        times = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    recent = [t for t in times
              if datetime.fromisoformat(t) > cutoff]
    return len(recent)


def _record_restart():
    p = _restart_times_path()
    try:
        times = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    except Exception:
        times = []
    times.append(datetime.now(timezone.utc).isoformat())
    # keep only last 50
    p.write_text(json.dumps(times[-50:]), encoding="utf-8")


def can_restart(max_per_hour: int = MAX_RESTARTS_PER_HOUR) -> bool:
    """Restart-loop guard: allow only up to max_per_hour restarts."""
    return _recent_restart_count() < max_per_hour


def active_jobs_summary() -> dict:
    """Summarize active video-render and youtube-upload jobs (no secrets)."""
    summary = {"video_render": "idle", "youtube_upload": "idle", "suno": "idle"}
    # Video render jobs
    try:
        from services.video.render_job_store import _jobs_dir as _vjobs
        vroot = _vjobs()
        if vroot.exists():
            for d in vroot.iterdir():
                sp = d / "render_state.json"
                if sp.exists():
                    st = json.loads(sp.read_text(encoding="utf-8"))
                    if st.get("status") in ("running", "rendering"):
                        pct = st.get("progress_percent", 0)
                        summary["video_render"] = f"running {pct:.0f}%"
                        break
    except Exception:
        pass
    # YouTube upload jobs
    try:
        from services.youtube.upload_job_store import _jobs_dir as _yjobs
        yroot = _yjobs()
        if yroot.exists():
            for d in yroot.iterdir():
                sp = d / "upload_state.json"
                if sp.exists():
                    st = json.loads(sp.read_text(encoding="utf-8"))
                    if st.get("status") in ("uploading", "thumbnail_setting",
                                            "authorizing", "queued"):
                        summary["youtube_upload"] = st.get("status")
                        break
    except Exception:
        pass
    return summary


def health_and_maybe_restart(auto_restart: bool = AUTO_RESTART_STREAMLIT,
                             max_per_hour: int = MAX_RESTARTS_PER_HOUR) -> dict:
    """
    One supervisor tick: check Streamlit, restart if down (and allowed), update
    and persist status. Returns the status dict.
    """
    status = load_status()
    health = HC.check_streamlit()
    status["streamlit_running"] = health["running"]
    status["streamlit_http_status"] = health["http_status"]
    status["streamlit_port"] = health["port"]
    status["last_health_check_at"] = datetime.now(timezone.utc).isoformat()

    if health["running"]:
        status["status"] = RS.SUP_HEALTHY
        pids = PM.find_streamlit_pids()
        status["streamlit_pid"] = pids[0] if pids else None
    else:
        log("Streamlit down detected", "warning")
        if auto_restart and can_restart(max_per_hour):
            status["status"] = RS.SUP_RESTARTING
            result = PM.restart_streamlit()
            _record_restart()
            status["streamlit_pid"] = result.get("new_pid")
            status["last_restart_at"] = datetime.now(timezone.utc).isoformat()
            log(f"Restarted Streamlit (new pid {result.get('new_pid')})")
        elif not can_restart(max_per_hour):
            status["status"] = RS.SUP_DEGRADED
            status["last_error"] = "restart loop guard: too many restarts in the last hour"
            log("Restart loop guard tripped — not restarting", "error")
        else:
            status["status"] = RS.SUP_DEGRADED

    status["restart_count_last_hour"] = _recent_restart_count()
    status["active_jobs_summary"] = active_jobs_summary()
    try:
        status["tailscale_status"] = HC.tailscale_status().get("status")
    except Exception:
        status["tailscale_status"] = None
    return write_status(status)


def tail_logs(last_n: int = 20) -> list[str]:
    """Return the last N SANITIZED supervisor log lines as plain strings."""
    out = []
    p = _log_path()
    if not p.exists():
        return out
    for ln in p.read_text(encoding="utf-8").strip().splitlines()[-last_n:]:
        try:
            d = json.loads(ln)
            out.append(f"[{d.get('level','info')}] {d.get('message','')}")
        except Exception:
            out.append(redact_text(ln))
    return out
