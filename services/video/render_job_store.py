"""
services/video/render_job_store.py — Video render job persistence (v0.7.3).

Stores background video-render jobs under:
    outputs/video_renderer/jobs/<render_job_id>/
      - render_state.json        (status, progress, timings, output path)
      - render_log.jsonl         (human-readable log lines)
      - ffmpeg_progress.jsonl    (parsed FFmpeg -progress key/values)
      - command_sanitized.txt    (the FFmpeg command, no secrets)

Mirrors the music job store pattern but is independent.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _jobs_dir() -> Path:
    d = Path(__file__).resolve().parent.parent.parent / "outputs" / "video_renderer" / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _job_path(render_job_id: str) -> Path:
    d = _jobs_dir() / render_job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def create_render_job(out_dir: str, command: list[str], total_seconds: float,
                      output_path: str) -> dict:
    """Create a new render job and persist its initial state + sanitized command."""
    render_job_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_render"
    jd = _job_path(render_job_id)

    state = {
        "render_job_id": render_job_id,
        "status": "queued",
        "out_dir": out_dir,
        "output_path": output_path,
        "total_seconds": float(total_seconds),
        "progress_percent": 0.0,
        "current_time_sec": 0.0,
        "speed": "",
        "elapsed_sec": 0.0,
        "eta_sec": None,
        "pid": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": None,
        "finished_at": None,
        "last_message": "대기 중",
    }
    (jd / "render_state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    # Sanitized command (no secrets in a render command, but keep the contract)
    (jd / "command_sanitized.txt").write_text(" ".join(command), encoding="utf-8")

    # Touch the log files
    (jd / "render_log.jsonl").write_text("", encoding="utf-8")
    (jd / "ffmpeg_progress.jsonl").write_text("", encoding="utf-8")

    return state


def load_render_state(render_job_id: str) -> dict | None:
    path = _jobs_dir() / render_job_id / "render_state.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def update_render_state(render_job_id: str, **fields) -> dict | None:
    state = load_render_state(render_job_id)
    if state is None:
        return None
    state.update(fields)
    (_job_path(render_job_id) / "render_state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def append_log(render_job_id: str, message: str, level: str = "info"):
    line = json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level, "message": message,
    }, ensure_ascii=False)
    p = _job_path(render_job_id) / "render_log.jsonl"
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def append_progress(render_job_id: str, progress: dict):
    """Append one parsed FFmpeg progress record."""
    line = json.dumps(progress, ensure_ascii=False)
    p = _job_path(render_job_id) / "ffmpeg_progress.jsonl"
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def list_render_jobs(limit: int = 20) -> list[dict]:
    jobs = []
    root = _jobs_dir()
    if not root.exists():
        return []
    for d in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if d.is_dir():
            s = load_render_state(d.name)
            if s:
                jobs.append(s)
            if len(jobs) >= limit:
                break
    return jobs


def get_render_log(render_job_id: str, last_n: int = 50) -> list[dict]:
    p = _jobs_dir() / render_job_id / "render_log.jsonl"
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    out = []
    for ln in lines[-last_n:]:
        try:
            out.append(json.loads(ln))
        except Exception:
            pass
    return out

def launch_render_job(out_dir: str, command: list[str], total_seconds: float,
                      output_path: str) -> dict:
    """
    Create a render job and launch the detached worker process.
    Returns the job state (with render_job_id).
    Uses the same Windows-safe detached-process pattern as the music worker.
    """
    import sys
    import subprocess

    state = create_render_job(out_dir, command, total_seconds, output_path)
    render_job_id = state["render_job_id"]

    # Store the full command for the worker to read
    jd = _job_path(render_job_id)
    (jd / "command.json").write_text(json.dumps(command, ensure_ascii=False), encoding="utf-8")

    # Launch detached worker
    python_exe = sys.executable
    if sys.platform == "win32":
        pythonw = Path(python_exe).with_name("pythonw.exe")
        if pythonw.exists():
            python_exe = str(pythonw)

    worker_cmd = [python_exe, "-m", "workers.video_render_worker", render_job_id]
    project_root = Path(__file__).resolve().parent.parent.parent

    popen_kwargs = {
        "cwd": str(project_root),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
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
        update_render_state(render_job_id, pid=proc.pid, status="running")
    except Exception as e:
        update_render_state(render_job_id, status="failed",
                            last_message=f"Worker 시작 실패: {e}")

    return load_render_state(render_job_id) or state
