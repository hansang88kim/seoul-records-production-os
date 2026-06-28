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
