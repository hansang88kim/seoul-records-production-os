"""
tests/test_job_store.py — Persistent Job Store tests.
"""
from __future__ import annotations
import json
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def clean_jobs(monkeypatch, tmp_path):
    """Redirect jobs dir to temp folder."""
    import services.job_store as js
    monkeypatch.setattr(js, "_jobs_dir", lambda: tmp_path)
    yield


def test_create_job():
    from services.job_store import create_job
    job = create_job(project="서울 시티팝", mode="auto_batch", total_tracks=5)
    assert job["job_id"]
    assert job["project"] == "서울 시티팝"
    assert job["status"] == "queued"
    assert job["total_tracks"] == 5


def test_job_persists_to_disk(tmp_path):
    from services.job_store import create_job, load_job
    job = create_job(project="test")
    job_id = job["job_id"]
    # Load from disk (simulating page refresh)
    loaded = load_job(job_id)
    assert loaded is not None
    assert loaded["project"] == "test"


def test_update_job():
    from services.job_store import create_job, update_job, load_job
    job = create_job(project="test")
    update_job(job["job_id"], status="running", current_track_title="밤이 지나면")
    loaded = load_job(job["job_id"])
    assert loaded["status"] == "running"
    assert loaded["current_track_title"] == "밤이 지나면"


def test_add_log_line_redacts_sensitive():
    from services.job_store import create_job, add_log_line, load_job
    job = create_job(project="test")
    add_log_line(job["job_id"], "cookie=secret123 auth success")
    loaded = load_job(job["job_id"])
    logs = loaded.get("log_lines", [])
    assert len(logs) == 1
    assert "secret123" not in logs[0]["msg"]
    assert "***" in logs[0]["msg"]


def test_complete_job():
    from services.job_store import create_job, complete_job, load_job
    job = create_job(project="test")
    complete_job(job["job_id"], "completed")
    loaded = load_job(job["job_id"])
    assert loaded["status"] == "completed"
    assert loaded["completed_at"] is not None


def test_list_jobs():
    from services.job_store import create_job, list_jobs
    create_job(project="A")
    create_job(project="B")
    jobs = list_jobs()
    assert len(jobs) >= 2
    # Newest first
    assert jobs[0]["project"] == "B"


def test_get_active_jobs():
    from services.job_store import create_job, update_job, get_active_jobs
    j1 = create_job(project="active")
    update_job(j1["job_id"], status="running")
    j2 = create_job(project="done")
    update_job(j2["job_id"], status="completed")
    active = get_active_jobs()
    assert len(active) == 1
    assert active[0]["project"] == "active"


def test_list_jobs_with_status_filter():
    from services.job_store import create_job, update_job, list_jobs
    j1 = create_job(project="A")
    update_job(j1["job_id"], status="completed")
    j2 = create_job(project="B")
    update_job(j2["job_id"], status="failed")
    completed = list_jobs(status_filter="completed")
    assert len(completed) == 1
    assert completed[0]["project"] == "A"


def test_log_lines_capped_at_50():
    from services.job_store import create_job, add_log_line, load_job
    job = create_job(project="test")
    for i in range(60):
        add_log_line(job["job_id"], f"line {i}")
    loaded = load_job(job["job_id"])
    assert len(loaded["log_lines"]) == 50


def test_job_plan_saved_to_disk(tmp_path):
    from services.job_store import create_job
    plan = [{"title": "곡1"}, {"title": "곡2"}]
    job = create_job(project="test", plan=plan)
    plan_path = tmp_path / job["job_id"] / "plan.json"
    assert plan_path.exists()
    loaded = json.loads(plan_path.read_text(encoding="utf-8"))
    assert len(loaded) == 2


# ─── Background Worker / Job Manager tests ───────────────────────────────────

def test_start_generation_job_creates_settings():
    from services.generation_job_manager import start_generation_job
    from pathlib import Path
    from unittest import mock
    import json
    plan = [{"title": "곡1", "style": "citypop", "lyrics": "가사", "status": "drafted"}]
    settings = {"model": "v5.5", "vocal_gender": "Female"}
    # Mock subprocess so we don't need suno binary
    fake_proc = mock.Mock(pid=12345)
    with mock.patch("subprocess.Popen", return_value=fake_proc):
        result = start_generation_job("test_project", plan, settings)
    assert result.get("job_id")
    import services.job_store as js
    jobs_dir = js._jobs_dir()
    settings_path = jobs_dir / result["job_id"] / "settings.json"
    assert settings_path.exists()
    loaded = json.loads(settings_path.read_text())
    assert loaded["model"] == "v5.5"


def test_duplicate_job_prevented():
    from services.job_store import create_job, update_job
    from services.generation_job_manager import start_generation_job
    # Create a running job for the same project
    j = create_job(project="dup_test")
    update_job(j["job_id"], status="running")
    # Try to start another
    result = start_generation_job("dup_test", [{"title": "곡"}], {})
    assert result.get("error") == "duplicate"
    assert "진행 중" in result.get("message", "")


def test_check_worker_alive():
    from services.generation_job_manager import check_worker_alive
    import os
    # Current process should be alive
    assert check_worker_alive(os.getpid()) is True
    # Non-existent PID
    assert check_worker_alive(99999999) is False
    assert check_worker_alive(None) is False


def test_recover_interrupted_jobs():
    from services.job_store import create_job, update_job
    from services.generation_job_manager import recover_jobs_from_disk
    # Create a "running" job with a dead PID
    j = create_job(project="recovery_test")
    update_job(j["job_id"], status="running", pid=99999999)  # dead PID
    recovered = recover_jobs_from_disk()
    assert len(recovered) >= 1
    # Check it was marked as interrupted
    from services.job_store import load_job
    loaded = load_job(j["job_id"])
    assert loaded["status"] == "interrupted"


def test_retry_failed_tracks():
    from services.job_store import create_job
    from services.generation_job_manager import retry_failed_tracks
    from unittest import mock
    import json
    import services.job_store as js
    # Create a job with a plan that has mixed results
    j = create_job(project="retry_test_proj")
    plan = [
        {"title": "성공곡", "status": "generated"},
        {"title": "실패곡", "status": "failed", "error": "captcha"},
    ]
    plan_path = js._jobs_dir() / j["job_id"] / "plan.json"
    plan_path.write_text(json.dumps(plan))
    settings_path = js._jobs_dir() / j["job_id"] / "settings.json"
    settings_path.write_text(json.dumps({"model": "v5.5"}))
    # Mock subprocess
    fake_proc = mock.Mock(pid=12345)
    with mock.patch("subprocess.Popen", return_value=fake_proc):
        result = retry_failed_tracks(j["job_id"])
    assert result is not None
    assert result.get("job_id") != j["job_id"]  # new job


def test_job_history():
    from services.generation_job_manager import list_job_history
    from services.job_store import create_job
    create_job(project="hist1")
    create_job(project="hist2")
    history = list_job_history()
    assert len(history) >= 2


def test_worker_launched_as_separate_process():
    """start_generation_job launches a detached subprocess (not a thread)."""
    from services.generation_job_manager import start_generation_job
    from unittest import mock
    captured = {}

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return mock.Mock(pid=54321)

    with mock.patch("subprocess.Popen", side_effect=fake_popen):
        result = start_generation_job("proc_test", [{"title": "곡", "status": "drafted"}], {})

    assert result.get("job_id")
    assert result.get("pid") == 54321
    # Command should invoke the worker module
    assert "workers.suno_generation_worker" in captured["cmd"]
    # Output should be detached (DEVNULL)
    import subprocess
    assert captured["kwargs"].get("stdout") == subprocess.DEVNULL
