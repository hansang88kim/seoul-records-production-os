"""
services/remote_control/process_manager.py — Streamlit process control (v0.9.1).

Finds, starts, and stops the Streamlit frontend for app/main.py — and ONLY that
process. It matches the command line carefully so unrelated Python processes
(and the render/upload workers) are never touched. No outputs are deleted.
"""
from __future__ import annotations

import sys
import subprocess
from pathlib import Path


STREAMLIT_PORT = 8501
STREAMLIT_ADDRESS = "127.0.0.1"
APP_ENTRY = "app/main.py"

# Markers that identify OUR streamlit process (must all relate to this app)
_MATCH_MARKERS = ("streamlit", "app/main.py")
# Markers that must NOT be matched (never kill the workers)
_EXCLUDE_MARKERS = ("video_render_worker", "youtube_upload_worker",
                    "studio_supervisor_worker", "suno_generation_worker")


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _cmdline_is_target_streamlit(cmdline: list[str]) -> bool:
    """
    True only if this command line is the Streamlit frontend for app/main.py and
    is NOT one of the background workers.
    """
    joined = " ".join(cmdline).replace("\\", "/").lower()
    if any(x in joined for x in _EXCLUDE_MARKERS):
        return False
    return all(m in joined for m in _MATCH_MARKERS)


def find_streamlit_pids() -> list[int]:
    """Return PIDs of the Streamlit frontend (app/main.py) only."""
    pids = []
    try:
        import psutil  # optional
    except Exception:
        return _find_streamlit_pids_fallback()
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmd = proc.info.get("cmdline") or []
            if cmd and _cmdline_is_target_streamlit(cmd):
                pids.append(proc.info["pid"])
        except Exception:
            continue
    return pids


def _find_streamlit_pids_fallback() -> list[int]:
    """psutil-free fallback using ps (POSIX). On Windows without psutil → []."""
    if sys.platform == "win32":
        return []
    try:
        out = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True,
                             text=True, timeout=5)
        pids = []
        for line in out.stdout.splitlines()[1:]:
            parts = line.strip().split(None, 1)
            if len(parts) == 2:
                pid_s, args = parts
                if _cmdline_is_target_streamlit(args.split()):
                    try:
                        pids.append(int(pid_s))
                    except ValueError:
                        pass
        return pids
    except Exception:
        return []


def build_start_command(python_exe: str | None = None) -> list[str]:
    """The exact command used to start Streamlit on 127.0.0.1:8501."""
    py = python_exe or sys.executable
    return [py, "-m", "streamlit", "run", APP_ENTRY,
            "--server.address", STREAMLIT_ADDRESS,
            "--server.port", str(STREAMLIT_PORT)]


def start_streamlit(python_exe: str | None = None) -> int | None:
    """Start the Streamlit frontend detached. Returns the new PID or None."""
    cmd = build_start_command(python_exe)
    kwargs = {
        "cwd": str(_project_root()),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        CREATE_NO_WINDOW = 0x08000000
        kwargs["creationflags"] = (DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
                                   | CREATE_NO_WINDOW)
        kwargs["close_fds"] = True
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(cmd, **kwargs)
        return proc.pid
    except Exception:
        return None


def stop_streamlit(timeout: float = 10.0) -> list[int]:
    """
    Gracefully terminate the Streamlit frontend (app/main.py only). Returns the
    list of PIDs that were stopped. Never touches workers or deletes outputs.
    """
    pids = find_streamlit_pids()
    stopped = []
    try:
        import psutil
    except Exception:
        psutil = None

    for pid in pids:
        try:
            if psutil:
                p = psutil.Process(pid)
                p.terminate()
                try:
                    p.wait(timeout=timeout)
                except Exception:
                    p.kill()
            else:
                import os
                import signal
                os.kill(pid, signal.SIGTERM)
            stopped.append(pid)
        except Exception:
            continue
    return stopped


def restart_streamlit(python_exe: str | None = None) -> dict:
    """
    Stop the existing frontend and start a fresh one. Returns a summary with
    old/new pids (health check is done by the caller/supervisor).
    """
    old = stop_streamlit()
    new_pid = start_streamlit(python_exe)
    return {"old_pids": old, "new_pid": new_pid}
