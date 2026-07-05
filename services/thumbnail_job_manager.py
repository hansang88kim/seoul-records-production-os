"""
services/thumbnail_job_manager.py — background job queue for Thumbnail Studio
image generation (v1.0.0-alpha.38).

Mirrors services/generation_job_manager.py's pattern for Suno song
generation: create_job() (job_store) + a detached worker subprocess +
job_store polling from the UI. Reuses job_store's generic functions with
mode="thumbnail_batch", so the existing Dashboard/Settings "작업 상태"
panels (which already query job_store.get_active_jobs()/list_jobs()
generically, not filtered by mode) show thumbnail jobs automatically —
no separate progress UI needed there.

Why this exists: real image-gen engines (Nano Banana 2/Apiframe, GPT Image 2,
Midjourney) take anywhere from ~10s to a few minutes PER IMAGE. Generating a
batch of several images synchronously in the Streamlit request thread blocks
the whole UI for that entire time. This launches generation in a detached
background process instead, exactly like the existing song-generation queue.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import services.job_store as _job_store
from services.job_store import create_job, load_job, update_job, list_jobs, get_active_jobs


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _sys_platform() -> str:
    return sys.platform


def start_thumbnail_job(session_id: str, prompts: list[dict], settings: dict) -> dict:
    """
    Start a background thumbnail-generation job. Returns the job state dict
    immediately (non-blocking) — generation runs in a separate process.

    ``settings`` should include: use_real (bool), model (str | None),
    engine (str). ``session_id`` is stored alongside so the worker knows
    which thumbnail-studio session to write candidates into.
    """
    active = get_active_jobs()
    running = [j for j in active if j.get("status") == "running"]

    job = create_job(project=session_id, mode="thumbnail_batch",
                     total_tracks=len(prompts), plan=prompts)
    job_id = job["job_id"]

    jobs_dir = _job_store._jobs_dir() / job_id
    settings_path = jobs_dir / "settings.json"
    settings_path.write_text(
        json.dumps({**settings, "session_id": session_id}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if running:
        # Mark as queued — a running worker (song OR thumbnail) doesn't pick
        # this up automatically the way the song queue does; the Settings/
        # Dashboard job panel's mark_interrupted_jobs()/start_next_queued_job()
        # sweep only chains song jobs today. For thumbnails we simply queue
        # and let the user retry/start once free — avoids two heavy
        # generation processes (song + thumbnail) competing for the same
        # machine at once.
        update_job(job_id, status="queued",
                   last_message="대기열에 추가됨 — 다른 작업 완료 후 다시 시도하세요")
        result = load_job(job_id) or job
        result["queued"] = True
        result["queued_behind"] = running[0]["job_id"]
        return result

    _launch_worker_process(job_id)
    return load_job(job_id) or job


def _launch_worker_process(job_id: str) -> bool:
    """Launch the detached worker subprocess for a thumbnail job."""
    import subprocess

    python_exe = sys.executable
    if _sys_platform() == "win32":
        pythonw = Path(python_exe).with_name("pythonw.exe")
        if pythonw.exists():
            python_exe = str(pythonw)

    worker_cmd = [python_exe, "-m", "workers.thumbnail_generation_worker", job_id]

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
        update_job(job_id, status="failed", last_message=f"Worker 시작 실패: {e}")
        return False


def get_thumbnail_jobs(limit: int = 20) -> list[dict]:
    """Thumbnail-specific jobs only (mode == 'thumbnail_batch'), newest first."""
    return [j for j in list_jobs(limit=limit) if j.get("mode") == "thumbnail_batch"]
