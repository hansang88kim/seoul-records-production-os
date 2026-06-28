"""
services/job_store.py — Persistent Job Store.

Each generation job (single or batch) is tracked as a persistent state file
under outputs/jobs/<job_id>/. Jobs survive page refresh, tab switches, and
even Streamlit restarts.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _jobs_dir() -> Path:
    d = Path(__file__).resolve().parent.parent / "outputs" / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def create_job(
    project: str,
    mode: str = "auto_batch",
    total_tracks: int = 1,
    plan: list[dict] | None = None,
) -> dict:
    """Create a new job and save its initial state to disk."""
    job_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    job_dir = _jobs_dir() / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    state = {
        "job_id": job_id,
        "project": project,
        "mode": mode,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "total_tracks": total_tracks,
        "completed_tracks": 0,
        "failed_tracks": 0,
        "current_track_no": 0,
        "current_track_title": "",
        "progress_percent": 0.0,
        "last_message": "생성 대기 중",
        "errors": [],
        "log_lines": [],
    }

    _save_state(job_id, state)

    # Save plan if provided
    if plan:
        (job_dir / "plan.json").write_text(
            json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return state


def update_job(job_id: str, **updates) -> dict:
    """Update a job's state and persist to disk."""
    state = load_job(job_id)
    if not state:
        return {}
    state.update(updates)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_state(job_id, state)
    return state


def add_log_line(job_id: str, message: str, level: str = "info"):
    """Append a sanitized log line to the job."""
    from services.metadata_consistency_service import redact_sensitive
    state = load_job(job_id)
    if not state:
        return
    sanitized = redact_sensitive(message)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "msg": sanitized,
    }
    log_lines = state.get("log_lines", [])
    log_lines.append(entry)
    # Keep only last 50 lines
    if len(log_lines) > 50:
        log_lines = log_lines[-50:]
    state["log_lines"] = log_lines
    state["last_message"] = sanitized
    _save_state(job_id, state)


def complete_job(job_id: str, status: str = "completed"):
    """Mark a job as completed/failed."""
    update_job(
        job_id,
        status=status,
        completed_at=datetime.now(timezone.utc).isoformat(),
        progress_percent=100.0 if status == "completed" else None,
    )


def load_job(job_id: str) -> dict | None:
    """Load a job's state from disk."""
    path = _jobs_dir() / job_id / "job_state.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def list_jobs(status_filter: str | None = None, limit: int = 20) -> list[dict]:
    """List jobs, newest first. Optionally filter by status."""
    jobs = []
    jdir = _jobs_dir()
    if not jdir.exists():
        return []
    for d in sorted(jdir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        state = load_job(d.name)
        if state:
            if status_filter and state.get("status") != status_filter:
                continue
            jobs.append(state)
            if len(jobs) >= limit:
                break
    return jobs


def get_active_jobs() -> list[dict]:
    """Get currently running/queued jobs."""
    return [j for j in list_jobs() if j.get("status") in ("queued", "running")]


def _save_state(job_id: str, state: dict):
    path = _jobs_dir() / job_id / "job_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
