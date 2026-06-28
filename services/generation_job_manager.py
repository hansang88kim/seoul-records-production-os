"""
services/generation_job_manager.py — Launch + manage background generation workers.

The UI calls start_generation_job() which:
1. Creates a persistent job with plan + settings
2. Launches workers/suno_generation_worker.py in a SUBPROCESS
3. Returns the job_id immediately (non-blocking)
4. The UI polls job_state.json for live progress

Also handles job recovery on app restart.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import services.job_store as _job_store
from services.job_store import (
    create_job,
    load_job,
    update_job,
    list_jobs,
    get_active_jobs,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def start_generation_job(
    project: str,
    plan: list[dict],
    settings: dict,
    mode: str = "auto_batch",
) -> dict:
    """
    Start a background generation job.
    Returns the job state dict immediately (non-blocking).
    The actual generation runs in a separate process.
    """
    # Check for duplicate — don't start if same project already running
    active = get_active_jobs()
    for j in active:
        if j.get("project") == project and j.get("status") == "running":
            return {
                "error": "duplicate",
                "message": f"이미 '{project}'에 대한 생성 작업이 진행 중입니다.",
                "existing_job_id": j["job_id"],
            }

    # Create job
    job = create_job(project=project, mode=mode, total_tracks=len(plan), plan=plan)
    job_id = job["job_id"]

    # Save settings
    jobs_dir = _job_store._jobs_dir() / job_id
    settings_path = jobs_dir / "settings.json"
    settings_path.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Launch worker in a background THREAD (more reliable than subprocess on Windows).
    # The thread survives Streamlit page reruns (same Python process).
    # It writes progress to job_state.json which the UI polls.
    import threading

    def _run_worker():
        try:
            from workers.suno_generation_worker import run_job
            run_job(job_id)
        except Exception as e:
            update_job(job_id, status="failed",
                       last_message=f"Worker 오류: {e}")

    try:
        t = threading.Thread(target=_run_worker, daemon=True, name=f"worker_{job_id}")
        t.start()
        update_job(job_id, pid=os.getpid(), status="running",
                   started_at=datetime.now(timezone.utc).isoformat())
    except Exception as e:
        update_job(job_id, status="failed",
                   last_message=f"Worker 시작 실패: {e}")
        return load_job(job_id) or job

    return load_job(job_id) or job


def check_worker_alive(pid: int | None) -> bool:
    """Check if a worker process is still alive."""
    if not pid:
        return False
    try:
        os.kill(pid, 0)  # signal 0 = just check if alive
        return True
    except (OSError, ProcessLookupError):
        return False


# ── Job Recovery ─────────────────────────────────────────────────────────────

def recover_jobs_from_disk() -> list[dict]:
    """
    Scan all jobs on disk. If any are marked 'running' but their worker
    PID is dead, mark them as 'interrupted' so the user can retry.
    Returns list of recovered/interrupted jobs.
    """
    recovered = []
    all_jobs = list_jobs(limit=50)

    for job in all_jobs:
        status = job.get("status", "")
        if status in ("running", "queued"):
            pid = job.get("pid")
            if not check_worker_alive(pid):
                # Worker died — mark as interrupted
                update_job(
                    job["job_id"],
                    status="interrupted",
                    last_message="작업이 중단되었습니다. 완료된 곡은 유지되며, 실패/미완료 곡만 다시 시도할 수 있습니다.",
                )
                recovered.append(job)

    return recovered


def mark_interrupted_jobs():
    """Called on app startup to mark any orphaned running jobs."""
    return recover_jobs_from_disk()


def get_job_progress(job_id: str) -> dict | None:
    """Get the current progress of a job (for UI polling)."""
    return load_job(job_id)


def retry_failed_tracks(job_id: str, settings: dict | None = None) -> dict | None:
    """
    Retry only the failed/incomplete tracks in a job.
    Creates a NEW job with only the unfinished tracks.
    """
    old_job = load_job(job_id)
    if not old_job:
        return None

    # Load old plan
    plan_path = _job_store._jobs_dir() / job_id / "plan.json"
    if not plan_path.exists():
        return None
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    # Filter to only failed/incomplete tracks
    retry_plan = []
    for track in plan:
        if track.get("status") not in ("generated",):
            track["status"] = "drafted"  # reset for retry
            track.pop("error", None)
            retry_plan.append(track)

    if not retry_plan:
        return None  # nothing to retry

    # Load settings from old job or use provided
    if not settings:
        old_settings_path = _job_store._jobs_dir() / job_id / "settings.json"
        if old_settings_path.exists():
            settings = json.loads(old_settings_path.read_text(encoding="utf-8"))
        else:
            settings = {}

    # Start new job with only failed tracks
    return start_generation_job(
        project=old_job.get("project", "기본"),
        plan=retry_plan,
        settings=settings,
        mode=old_job.get("mode", "auto_batch"),
    )


def list_job_history(limit: int = 20) -> list[dict]:
    """List all jobs with their current status for the history panel."""
    return list_jobs(limit=limit)
