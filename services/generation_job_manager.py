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
import signal
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


def _sys_platform() -> str:
    return sys.platform


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
    # If a job is already running, QUEUE this one instead of blocking.
    # The running job's worker will pick up queued jobs when it finishes.
    active = get_active_jobs()
    running = [j for j in active if j.get("status") == "running"]

    # Create the job
    job = create_job(project=project, mode=mode, total_tracks=len(plan), plan=plan)
    job_id = job["job_id"]

    # Save settings (needed whether we run now or queue)
    jobs_dir = _job_store._jobs_dir() / job_id
    settings_path = jobs_dir / "settings.json"
    settings_path.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if running:
        # Mark as queued — a running worker will pick it up
        update_job(job_id, status="queued",
                   last_message=f"대기열에 추가됨 — 현재 작업 완료 후 자동 시작")
        result = load_job(job_id) or job
        result["queued"] = True
        result["queued_behind"] = running[0]["job_id"]
        return result

    # Launch worker as a fully detached process (no running job → start now)
    _launch_worker_process(job_id)
    return load_job(job_id) or job


def check_worker_alive(pid: int | None) -> bool:
    """Check if a worker process is still alive (cross-platform)."""
    if not pid:
        return False
    if _sys_platform() == "win32":
        # On Windows, os.kill(pid, 0) is unreliable for detached processes.
        # Use OpenProcess via ctypes to check existence accurately.
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                # Could not open — fall back to assuming alive if recently started
                return False
            exit_code = ctypes.c_ulong()
            ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            kernel32.CloseHandle(handle)
            if ok and exit_code.value == STILL_ACTIVE:
                return True
            return False
        except Exception:
            # If the check itself fails, assume alive (don't false-kill)
            return True
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


# ── Job Recovery ─────────────────────────────────────────────────────────────

def recover_jobs_from_disk() -> list[dict]:
    """
    Scan all jobs on disk. If any are marked 'running' but their worker
    PID is dead, mark them as 'interrupted' so the user can retry.

    QUEUED jobs are NEVER touched here — they have no worker yet (they're
    waiting for a running job to finish), so checking their PID would
    wrongly mark them interrupted and break the queue.

    A grace period protects freshly-started jobs whose worker process
    may not be observable yet.
    """
    import time as _t
    from datetime import datetime as _dt, timezone as _tz

    recovered = []
    all_jobs = list_jobs(limit=50)
    GRACE_SECONDS = 30  # don't touch jobs started within the last 30s

    for job in all_jobs:
        status = job.get("status", "")
        # Only RUNNING jobs can be interrupted. Queued jobs have no worker.
        if status != "running":
            continue

        # Grace period: skip very recently started jobs
        started = job.get("started_at") or job.get("created_at")
        if started:
            try:
                started_dt = _dt.fromisoformat(started)
                if started_dt.tzinfo is None:
                    started_dt = started_dt.replace(tzinfo=_tz.utc)
                age = (_dt.now(_tz.utc) - started_dt).total_seconds()
                if age < GRACE_SECONDS:
                    continue  # too fresh — worker may not be visible yet
            except Exception:
                pass

        pid = job.get("pid")
        if not check_worker_alive(pid):
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

def _launch_worker_process(job_id: str) -> bool:
    """Launch the detached worker subprocess for a job. Returns True on success."""
    import subprocess

    python_exe = sys.executable
    if _sys_platform() == "win32":
        pythonw = Path(python_exe).with_name("pythonw.exe")
        if pythonw.exists():
            python_exe = str(pythonw)

    worker_cmd = [python_exe, "-m", "workers.suno_generation_worker", job_id]

    popen_kwargs = {
        "cwd": str(PROJECT_ROOT),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if _sys_platform() == "win32":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        CREATE_NO_WINDOW = 0x08000000
        CREATE_BREAKAWAY_FROM_JOB = 0x01000000
        popen_kwargs["creationflags"] = (
            DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            | CREATE_NO_WINDOW | CREATE_BREAKAWAY_FROM_JOB
        )
        popen_kwargs["close_fds"] = True
    else:
        popen_kwargs["start_new_session"] = True

    try:
        proc = subprocess.Popen(worker_cmd, **popen_kwargs)
        update_job(job_id, pid=proc.pid, status="running",
                   started_at=datetime.now(timezone.utc).isoformat())
        return True
    except Exception as e:
        update_job(job_id, status="failed",
                   last_message=f"Worker 시작 실패: {e}")
        return False


def get_queued_jobs() -> list[dict]:
    """Get all jobs waiting in the queue (status=queued), oldest first."""
    queued = [j for j in list_jobs(limit=50) if j.get("status") == "queued"]
    queued.sort(key=lambda j: j.get("created_at", ""))
    return queued


def start_next_queued_job() -> dict | None:
    """
    Start the oldest queued job IF no job is currently running.
    Called by a finishing worker (or the UI) to chain the queue.
    Returns the started job, or None if nothing to start / one is running.
    """
    # Don't start if something is already running
    active = get_active_jobs()
    if any(j.get("status") == "running" for j in active):
        return None

    queued = get_queued_jobs()
    if not queued:
        return None

    next_job = queued[0]
    job_id = next_job["job_id"]
    if _launch_worker_process(job_id):
        return load_job(job_id)
    return None

def stop_job(job_id: str) -> bool:
    """
    Stop a running job by terminating its worker process.
    Completed tracks are preserved; the job is marked 'cancelled'.
    """
    job = load_job(job_id)
    if not job:
        return False

    pid = job.get("pid")
    if pid and check_worker_alive(pid):
        try:
            if _sys_platform() == "win32":
                import ctypes
                PROCESS_TERMINATE = 0x0001
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
                if handle:
                    kernel32.TerminateProcess(handle, 1)
                    kernel32.CloseHandle(handle)
            else:
                os.kill(pid, signal.SIGTERM)
        except Exception:
            pass

    update_job(job_id, status="cancelled",
               last_message="사용자가 중단함 — 완료된 곡은 보관됩니다.")
    return True


def restart_job(job_id: str) -> dict | None:
    """
    Restart a stopped/interrupted/failed job — re-runs only the
    incomplete tracks as a NEW job (completed tracks preserved).
    """
    return retry_failed_tracks(job_id)
