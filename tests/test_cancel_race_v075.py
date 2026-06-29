"""
tests/test_cancel_race_v075.py — Cancel race condition fix tests.

Covers the case where a cancel is requested immediately after launch, before
or during the worker's 'running' flip / FFmpeg start. No real FFmpeg.
"""
from __future__ import annotations
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def jobs_tmp(monkeypatch, tmp_path):
    import services.video.render_job_store as rjs
    monkeypatch.setattr(rjs, "_jobs_dir", lambda: tmp_path / "jobs")
    yield


# ─── update_render_state guard ───────────────────────────────────────────────

def test_worker_does_not_overwrite_cancelling_with_running():
    """A 'running' update must NOT overwrite an on-disk 'cancelling' status."""
    from services.video.render_job_store import (
        create_render_job, update_render_state, load_render_state,
    )
    s = create_render_job("/o", ["ffmpeg"], 3600, "/o/final_video.mp4")
    jid = s["render_job_id"]
    # User cancelled first
    update_render_state(jid, status="cancelling")
    # Worker (late) tries to set running
    update_render_state(jid, status="running", started_at="now")
    # Status must STILL be cancelling (running was dropped)
    assert load_render_state(jid)["status"] == "cancelling"
    # But other fields from the same call still applied
    assert load_render_state(jid)["started_at"] == "now"


def test_running_allowed_when_not_cancelling():
    """The guard only blocks running when cancel-locked; normal flips work."""
    from services.video.render_job_store import (
        create_render_job, update_render_state, load_render_state,
    )
    s = create_render_job("/o", ["ffmpeg"], 3600, "/o/v.mp4")
    jid = s["render_job_id"]
    update_render_state(jid, status="running")
    assert load_render_state(jid)["status"] == "running"


def test_cancelled_also_not_overwritten_by_running():
    from services.video.render_job_store import (
        create_render_job, update_render_state, load_render_state,
    )
    s = create_render_job("/o", ["ffmpeg"], 3600, "/o/v.mp4")
    jid = s["render_job_id"]
    update_render_state(jid, status="cancelled")
    update_render_state(jid, status="running")
    assert load_render_state(jid)["status"] == "cancelled"


# ─── Worker honors a pre-start cancel ────────────────────────────────────────

def test_cancel_requested_before_worker_starts_not_lost(monkeypatch, tmp_path):
    """If cancelling is set before the worker runs, the request is honored."""
    from services.video import render_job_store as rjs
    from workers import video_render_worker as vrw
    from unittest import mock

    s = rjs.create_render_job(str(tmp_path), ["ffmpeg"], 3600,
                              str(tmp_path / "final_video.mp4"))
    jid = s["render_job_id"]
    rjs.request_cancel(jid)  # cancel BEFORE worker starts

    popen_called = {"called": False}
    def fake_popen(*a, **k):
        popen_called["called"] = True
        raise AssertionError("FFmpeg must NOT be launched")

    with mock.patch("subprocess.Popen", side_effect=fake_popen):
        vrw.run_render_job(jid)

    state = rjs.load_render_state(jid)
    assert state["status"] == "cancelled"
    assert popen_called["called"] is False


def test_cancel_before_ffmpeg_start_does_not_launch_ffmpeg(monkeypatch, tmp_path):
    """FFmpeg Popen is never called when the job is already cancelling."""
    from services.video import render_job_store as rjs
    from workers import video_render_worker as vrw
    from unittest import mock

    s = rjs.create_render_job(str(tmp_path), ["ffmpeg"], 3600,
                              str(tmp_path / "final_video.mp4"))
    jid = s["render_job_id"]
    rjs.update_render_state(jid, status="cancelling")

    with mock.patch("subprocess.Popen") as m:
        vrw.run_render_job(jid)
        assert m.call_count == 0  # FFmpeg not launched


def test_cancel_before_start_marks_cancelled(monkeypatch, tmp_path):
    from services.video import render_job_store as rjs
    from workers import video_render_worker as vrw
    from unittest import mock

    s = rjs.create_render_job(str(tmp_path), ["ffmpeg"], 3600,
                              str(tmp_path / "final_video.mp4"))
    jid = s["render_job_id"]
    rjs.request_cancel(jid)

    with mock.patch("subprocess.Popen"):
        vrw.run_render_job(jid)

    state = rjs.load_render_state(jid)
    assert state["status"] == "cancelled"
    assert "취소" in state.get("last_message", "")


def test_immediate_cancel_after_launch_is_honored(monkeypatch, tmp_path):
    """
    Simulates: launch_render_job runs, then the user immediately cancels
    BEFORE the worker process gets scheduled. The worker must honor it and
    never start FFmpeg, never flip back to running.
    """
    from services.video import render_job_store as rjs
    from workers import video_render_worker as vrw
    from unittest import mock

    s = rjs.create_render_job(str(tmp_path), ["ffmpeg"], 3600,
                              str(tmp_path / "final_video.mp4"))
    jid = s["render_job_id"]
    # launch sets worker_pid + running (simulate), THEN user cancels instantly
    rjs.update_render_state(jid, status="running", worker_pid=111)
    rjs.request_cancel(jid)  # → cancelling (guard: running can't overwrite)

    with mock.patch("subprocess.Popen") as m:
        vrw.run_render_job(jid)
        # Worker's guard #1 catches cancelling → no FFmpeg
        assert m.call_count == 0

    assert rjs.load_render_state(jid)["status"] == "cancelled"


def test_cancel_during_running_flip_keeps_files(tmp_path):
    """A pre-start cancel must not delete output/log/plan files."""
    from services.video import render_job_store as rjs
    from workers import video_render_worker as vrw
    from unittest import mock

    out = tmp_path / "final_video.mp4"
    out.write_bytes(b"partial")
    s = rjs.create_render_job(str(tmp_path), ["ffmpeg"], 3600, str(out))
    jid = s["render_job_id"]
    rjs.append_log(jid, "queued")
    rjs.request_cancel(jid)

    with mock.patch("subprocess.Popen"):
        vrw.run_render_job(jid)

    # Files preserved
    assert out.exists()
    from services.video.render_job_store import _jobs_dir
    jd = _jobs_dir() / jid
    assert (jd / "render_log.jsonl").exists()
    assert (jd / "render_state.json").exists()
    assert (jd / "command_sanitized.txt").exists()


def test_independence_v075():
    from providers.ai.base import MOCK_SONGS
    assert len(MOCK_SONGS) >= 2
