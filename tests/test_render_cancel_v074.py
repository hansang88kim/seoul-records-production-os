"""
tests/test_render_cancel_v074.py — Render Cancel + PID split + history tests.

No real FFmpeg. Worker subprocess mocked.
"""
from __future__ import annotations
import json
import time
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def jobs_tmp(monkeypatch, tmp_path):
    import services.video.render_job_store as rjs
    monkeypatch.setattr(rjs, "_jobs_dir", lambda: tmp_path / "jobs")
    yield


# ─── Cancel ──────────────────────────────────────────────────────────────────

def test_cancel_render_sets_cancelling():
    from services.video.render_job_store import create_render_job, request_cancel, load_render_state
    s = create_render_job("/out", ["ffmpeg"], 3600, "/out/final_video.mp4")
    jid = s["render_job_id"]
    from services.video.render_job_store import update_render_state
    update_render_state(jid, status="running")
    request_cancel(jid)
    assert load_render_state(jid)["status"] == "cancelling"


def test_worker_terminates_ffmpeg_on_cancel(monkeypatch, tmp_path):
    """
    The worker polls is_cancelling and calls terminate_ffmpeg, then marks
    cancelled. Cancellation is requested DURING the render loop (realistic:
    the worker first flips status to 'running', then a cancel arrives).
    """
    from services.video import render_job_store as rjs
    from workers import video_render_worker as vrw
    from unittest import mock

    s = rjs.create_render_job(str(tmp_path), ["ffmpeg", "-i", "x"], 3600,
                              str(tmp_path / "final_video.mp4"))
    jid = s["render_job_id"]

    terminated = {"called": False, "pid": None}

    # A stdout iterator that requests a cancel after the first line is read,
    # so the worker's next poll detects 'cancelling' mid-render.
    def streaming_lines():
        yield "frame=1"
        rjs.request_cancel(jid)  # user clicks cancel now
        yield "frame=2"
        yield "progress=continue"

    class FakeProc:
        pid = 7777
        returncode = 0
        def __init__(self):
            self.stdout = streaming_lines()
        def wait(self):
            return 0

    def fake_terminate(pid):
        terminated["called"] = True
        terminated["pid"] = pid
        return True

    with mock.patch("subprocess.Popen", return_value=FakeProc()), \
         mock.patch("services.video.render_job_store.terminate_ffmpeg", side_effect=fake_terminate):
        vrw.run_render_job(jid)

    state = rjs.load_render_state(jid)
    assert state["status"] == "cancelled"
    assert terminated["called"] is True
    assert terminated["pid"] == 7777


def test_cancel_does_not_delete_output_files(tmp_path):
    """Cancelling must NOT delete the output file."""
    from services.video.render_job_store import create_render_job, update_render_state, request_cancel
    out = tmp_path / "final_video.mp4"
    out.write_bytes(b"partial video data")
    s = create_render_job(str(tmp_path), ["ffmpeg"], 3600, str(out))
    jid = s["render_job_id"]
    update_render_state(jid, status="running")
    request_cancel(jid)
    update_render_state(jid, status="cancelled")
    # File still there
    assert out.exists()
    assert out.read_bytes() == b"partial video data"


def test_cancel_does_not_delete_logs(tmp_path):
    """Cancelling must NOT delete log/plan files."""
    from services.video.render_job_store import (
        create_render_job, append_log, append_progress, request_cancel,
        update_render_state, _jobs_dir,
    )
    s = create_render_job(str(tmp_path), ["ffmpeg"], 3600, "/out.mp4")
    jid = s["render_job_id"]
    append_log(jid, "started")
    append_progress(jid, {"speed": "2x", "progress": "continue"})
    update_render_state(jid, status="running")
    request_cancel(jid)
    update_render_state(jid, status="cancelled")
    jd = _jobs_dir() / jid
    assert (jd / "render_log.jsonl").exists()
    assert (jd / "ffmpeg_progress.jsonl").exists()
    assert (jd / "command_sanitized.txt").exists()
    assert (jd / "render_state.json").exists()
    # Logs retain content
    assert (jd / "render_log.jsonl").read_text().strip() != ""


# ─── PID separation ──────────────────────────────────────────────────────────

def test_render_state_has_worker_pid_and_ffmpeg_pid():
    from services.video.render_job_store import create_render_job
    s = create_render_job("/out", ["ffmpeg"], 3600, "/out.mp4")
    assert "worker_pid" in s
    assert "ffmpeg_pid" in s
    # Not a single generic 'pid' field anymore
    assert "pid" not in s


def test_worker_sets_both_pids(monkeypatch, tmp_path):
    from services.video import render_job_store as rjs
    from workers import video_render_worker as vrw
    from unittest import mock

    s = rjs.create_render_job(str(tmp_path), ["ffmpeg"], 3600,
                              str(tmp_path / "final_video.mp4"))
    jid = s["render_job_id"]
    (tmp_path / "final_video.mp4").write_bytes(b"done")

    class FakeProc:
        pid = 9999
        returncode = 0
        def __init__(self):
            self.stdout = iter([])
        def wait(self):
            return 0

    with mock.patch("subprocess.Popen", return_value=FakeProc()):
        vrw.run_render_job(jid)

    state = rjs.load_render_state(jid)
    assert state["ffmpeg_pid"] == 9999
    assert state["worker_pid"] is not None  # this process


# ─── Unique job id ───────────────────────────────────────────────────────────

def test_render_job_id_unique_within_same_second():
    from services.video.render_job_store import create_render_job
    ids = set()
    for _ in range(20):
        s = create_render_job("/out", ["ffmpeg"], 60, "/out.mp4")
        ids.add(s["render_job_id"])
    # All unique even though created in the same second
    assert len(ids) == 20


# ─── Job history ─────────────────────────────────────────────────────────────

def test_render_job_history_lists_cancelled_completed_running():
    from services.video.render_job_store import create_render_job, update_render_state, list_render_jobs
    j1 = create_render_job("/o", ["f"], 60, "/o/1.mp4")
    update_render_state(j1["render_job_id"], status="running")
    j2 = create_render_job("/o", ["f"], 60, "/o/2.mp4")
    update_render_state(j2["render_job_id"], status="completed")
    j3 = create_render_job("/o", ["f"], 60, "/o/3.mp4")
    update_render_state(j3["render_job_id"], status="cancelled")
    j4 = create_render_job("/o", ["f"], 60, "/o/4.mp4")
    update_render_state(j4["render_job_id"], status="failed")

    jobs = list_render_jobs(20)
    statuses = {j["status"] for j in jobs}
    assert "running" in statuses
    assert "completed" in statuses
    assert "cancelled" in statuses
    assert "failed" in statuses
    assert len(jobs) >= 4


# ─── Recovery after rerun ────────────────────────────────────────────────────

def test_rerun_recovers_active_render_job():
    """
    After a 'rerun' (no session state), the panel can recover the active job
    from disk via list_render_jobs.
    """
    from services.video.render_job_store import create_render_job, update_render_state, list_render_jobs
    j = create_render_job("/o", ["f"], 3600, "/o/final_video.mp4")
    update_render_state(j["render_job_id"], status="running", progress_percent=33.0)

    # Simulate a fresh rerun: only disk is available
    active = [x for x in list_render_jobs(20)
              if x.get("status") in ("running", "cancelling", "queued")]
    assert len(active) >= 1
    recovered = active[0]
    assert recovered["render_job_id"] == j["render_job_id"]
    assert recovered["progress_percent"] == 33.0


# ─── Long render: no timeout ─────────────────────────────────────────────────

def test_worker_has_no_subprocess_timeout():
    """The worker must NOT impose a subprocess timeout (long renders)."""
    src = Path("workers/video_render_worker.py").read_text()
    # No 'timeout=' kwarg in the worker's subprocess usage
    assert "timeout=" not in src


def test_independence_v074():
    from providers.ai.base import MOCK_SONGS
    assert len(MOCK_SONGS) >= 2
