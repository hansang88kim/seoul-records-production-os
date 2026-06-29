"""
services/youtube/upload_job_store.py — YouTube upload job persistence (v0.8.2).

Background upload jobs under:
    outputs/youtube_upload/jobs/<upload_job_id>/
      - upload_state.json
      - upload_log.jsonl
      - upload_progress.jsonl
      - upload_payload_snapshot.json   (sanitized — no secrets)
      - upload_result.json             (sanitized)
      - request_sanitized.json

All logs/snapshots are scrubbed via services.security.redaction so no token
can ever leak to disk. token.json is NEVER copied into a job folder.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from services.security.redaction import redact_dict


def _jobs_dir() -> Path:
    d = Path(__file__).resolve().parent.parent.parent / "outputs" / "youtube_upload" / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _job_path(upload_job_id: str) -> Path:
    d = _jobs_dir() / upload_job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_upload_job_id() -> str:
    return (datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            + "_" + uuid.uuid4().hex[:6] + "_upload")


def create_upload_job(package_id: str, video_path: str, thumbnail_path: str,
                      title: str, payload: dict,
                      privacy_status: str = "private") -> dict:
    """Create an upload job + persist initial state and a SANITIZED snapshot."""
    upload_job_id = new_upload_job_id()
    jd = _job_path(upload_job_id)

    state = {
        "upload_job_id": upload_job_id,
        "package_id": package_id,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "video_path": video_path,
        "thumbnail_path": thumbnail_path,
        "privacy_status": privacy_status,
        "title": title,
        "video_id": None,
        "youtube_url": None,
        "progress_percent": 0.0,
        "bytes_uploaded": 0,
        "total_bytes": 0,
        "upload_speed": "",
        "thumbnail_set_status": "pending",
        "last_message": "대기 중",
        "errors": [],
        "worker_pid": None,
    }
    (jd / "upload_state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    # Snapshot the payload — sanitized (payload has no secrets, but be safe)
    (jd / "upload_payload_snapshot.json").write_text(
        json.dumps(redact_dict(payload), ensure_ascii=False, indent=2), encoding="utf-8")

    # Sanitized request descriptor (never includes tokens)
    (jd / "request_sanitized.json").write_text(json.dumps(redact_dict({
        "package_id": package_id, "video_path": video_path,
        "thumbnail_path": thumbnail_path, "privacy_status": privacy_status,
        "title": title,
    }), ensure_ascii=False, indent=2), encoding="utf-8")

    (jd / "upload_log.jsonl").write_text("", encoding="utf-8")
    (jd / "upload_progress.jsonl").write_text("", encoding="utf-8")
    return state


def load_upload_state(upload_job_id: str) -> dict | None:
    p = _jobs_dir() / upload_job_id / "upload_state.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def update_upload_state(upload_job_id: str, **fields) -> dict | None:
    state = load_upload_state(upload_job_id)
    if state is None:
        return None
    # Defensive: never allow auto-public
    if fields.get("privacy_status") == "public" and state.get("privacy_status") != "public":
        fields.pop("privacy_status", None)
    state.update(fields)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    (_job_path(upload_job_id) / "upload_state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def append_upload_log(upload_job_id: str, message: str, level: str = "info"):
    from services.security.redaction import redact_text
    line = json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level, "message": redact_text(message),
    }, ensure_ascii=False)
    with (_job_path(upload_job_id) / "upload_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def append_upload_progress(upload_job_id: str, progress: dict):
    line = json.dumps(redact_dict(progress), ensure_ascii=False)
    with (_job_path(upload_job_id) / "upload_progress.jsonl").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def save_upload_result(upload_job_id: str, result: dict) -> str:
    """Persist upload_result.json (SANITIZED — no tokens, no raw API headers)."""
    safe = redact_dict(result)
    path = _job_path(upload_job_id) / "upload_result.json"
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def list_upload_jobs(limit: int = 20) -> list[dict]:
    jobs = []
    root = _jobs_dir()
    if not root.exists():
        return []
    for d in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if d.is_dir():
            s = load_upload_state(d.name)
            if s:
                jobs.append(s)
            if len(jobs) >= limit:
                break
    return jobs


def get_upload_log(upload_job_id: str, last_n: int = 20) -> list[dict]:
    p = _jobs_dir() / upload_job_id / "upload_log.jsonl"
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

def launch_upload_job(package_id: str, video_path: str, thumbnail_path: str,
                      title: str, payload: dict, privacy_status: str = "private",
                      use_real: bool = False) -> dict:
    """
    Create an upload job and launch the detached worker. Defaults to the mock
    client unless use_real=True. Returns the job state.
    """
    import sys
    import subprocess

    state = create_upload_job(package_id, video_path, thumbnail_path, title,
                              payload, privacy_status)
    upload_job_id = state["upload_job_id"]

    python_exe = sys.executable
    if sys.platform == "win32":
        pythonw = Path(python_exe).with_name("pythonw.exe")
        if pythonw.exists():
            python_exe = str(pythonw)

    worker_cmd = [python_exe, "-m", "workers.youtube_upload_worker", upload_job_id]
    if use_real:
        worker_cmd.append("--real")
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
        update_upload_state(upload_job_id, worker_pid=proc.pid, status="authorizing")
    except Exception as e:
        update_upload_state(upload_job_id, status="failed",
                            last_message="Worker 시작 실패",
                            errors=["worker launch failed"])

    return load_upload_state(upload_job_id) or state
