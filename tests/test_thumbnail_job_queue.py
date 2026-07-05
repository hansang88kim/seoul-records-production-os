"""
tests/test_thumbnail_job_queue.py — background job queue for Thumbnail
Studio image generation (v1.0.0-alpha.38).

Covers services/thumbnail_job_manager.py (job creation + detached-process
launch, mocked — no real subprocess spawned) and
workers/thumbnail_generation_worker.py (the actual generation loop, run
directly against the mock image provider — fast, no network).
"""
from __future__ import annotations

import json
from unittest import mock

import pytest

import services.job_store as job_store
import services.thumbnail.session_store as ss
import services.thumbnail_job_manager as tjm
import workers.thumbnail_generation_worker as worker
from services.thumbnail.prompt_generator import generate_prompt_batch


@pytest.fixture(autouse=True)
def isolated_dirs(monkeypatch, tmp_path):
    monkeypatch.setattr(job_store, "_jobs_dir", lambda: tmp_path / "jobs")
    monkeypatch.setattr(ss, "_studio_root", lambda: tmp_path / "studio")
    yield


# ─── start_thumbnail_job ──────────────────────────────────────────────────────

def test_start_thumbnail_job_creates_job_and_writes_plan_settings(tmp_path):
    sess = ss.create_session("korea", "night", "T", 1)
    prompts = generate_prompt_batch("korea", "night", 3)

    with mock.patch("subprocess.Popen") as popen:
        popen.return_value.pid = 12345
        job = tjm.start_thumbnail_job(
            sess["session_id"], prompts,
            settings={"use_real": False, "model": None, "engine": "gemini"},
        )

    assert job["mode"] == "thumbnail_batch"
    assert job["total_tracks"] == 3
    assert job["status"] == "running"
    popen.assert_called_once()
    cmd = popen.call_args[0][0]
    assert "workers.thumbnail_generation_worker" in cmd
    assert job["job_id"] in cmd

    jobs_dir = job_store._jobs_dir() / job["job_id"]
    plan = json.loads((jobs_dir / "plan.json").read_text(encoding="utf-8"))
    settings = json.loads((jobs_dir / "settings.json").read_text(encoding="utf-8"))
    assert len(plan) == 3
    assert settings["session_id"] == sess["session_id"]
    assert settings["engine"] == "gemini"


def test_start_thumbnail_job_queues_behind_a_running_job(tmp_path):
    sess = ss.create_session("japan", "night", "T", 1)
    prompts = generate_prompt_batch("japan", "night", 2)

    # A song-generation job (or another thumbnail job) is already running.
    running = job_store.create_job(project="other", mode="auto_batch", total_tracks=5)
    job_store.update_job(running["job_id"], status="running")

    with mock.patch("subprocess.Popen") as popen:
        job = tjm.start_thumbnail_job(
            sess["session_id"], prompts,
            settings={"use_real": False, "model": None, "engine": "gemini"},
        )

    popen.assert_not_called()  # must NOT launch a second process
    assert job["queued"] is True
    assert job["queued_behind"] == running["job_id"]
    assert job_store.load_job(job["job_id"])["status"] == "queued"


def test_get_thumbnail_jobs_filters_by_mode(tmp_path):
    sess = ss.create_session("korea", "night", "T", 1)
    prompts = generate_prompt_batch("korea", "night", 1)
    with mock.patch("subprocess.Popen"):
        tjm.start_thumbnail_job(sess["session_id"], prompts,
                                settings={"use_real": False, "model": None, "engine": "gemini"})
    job_store.create_job(project="song-proj", mode="auto_batch", total_tracks=3)

    thumb_jobs = tjm.get_thumbnail_jobs()
    assert len(thumb_jobs) == 1
    assert thumb_jobs[0]["mode"] == "thumbnail_batch"


# ─── worker.main() — the actual generation loop ──────────────────────────────

def test_worker_runs_full_batch_against_mock_provider_and_reports_progress(tmp_path):
    sess = ss.create_session("korea", "night", "T", 1)
    prompts = generate_prompt_batch("korea", "night", 3)

    job = job_store.create_job(project=sess["session_id"], mode="thumbnail_batch",
                               total_tracks=3, plan=prompts)
    jobs_dir = job_store._jobs_dir() / job["job_id"]
    (jobs_dir / "settings.json").write_text(
        json.dumps({"session_id": sess["session_id"], "use_real": False,
                   "model": None, "engine": "gemini"}),
        encoding="utf-8",
    )

    worker.main(job["job_id"])

    final = job_store.load_job(job["job_id"])
    assert final["status"] == "completed"
    assert final["completed_tracks"] == 3
    assert final["failed_tracks"] == 0
    assert final["progress_percent"] == 100.0
    # add_log_line (called last) also updates last_message, so the final
    # value is the completion log line, not the earlier update_job() call —
    # both are informative; assert on the part that matters.
    assert "3/3" in final["last_message"]

    # The images were actually written to disk via the real generate_images path.
    cands = ss.load_candidates(sess["session_id"])
    assert len(cands) == 3
    assert all(c["status"] == "image_generated" for c in cands)


def test_worker_missing_job_is_a_noop():
    # Should not raise even if the job_id doesn't exist.
    worker.main("nonexistent_job_id_xyz")


def test_worker_missing_plan_marks_job_failed(tmp_path):
    job = job_store.create_job(project="p", mode="thumbnail_batch", total_tracks=1)
    # No plan.json/settings.json written -> should fail cleanly, not crash.
    worker.main(job["job_id"])
    final = job_store.load_job(job["job_id"])
    assert final["status"] == "failed"


def test_worker_partial_failure_status(tmp_path, monkeypatch):
    """If some images fail and some succeed, job status is partially_failed."""
    sess = ss.create_session("korea", "night", "T", 1)
    prompts = generate_prompt_batch("korea", "night", 2)
    job = job_store.create_job(project=sess["session_id"], mode="thumbnail_batch",
                               total_tracks=2, plan=prompts)
    jobs_dir = job_store._jobs_dir() / job["job_id"]
    (jobs_dir / "settings.json").write_text(
        json.dumps({"session_id": sess["session_id"], "use_real": False,
                   "model": None, "engine": "gemini"}),
        encoding="utf-8",
    )

    # Force the first image to "fail" by making the mock provider error once.
    from services.thumbnail.image_provider import MockImageGenProvider
    real_generate = MockImageGenProvider.generate
    call_count = {"n": 0}

    def flaky_generate(self, *args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"ok": False, "provider": "mock", "model": None,
                    "path": None, "error": "forced failure"}
        return real_generate(self, *args, **kwargs)

    monkeypatch.setattr(MockImageGenProvider, "generate", flaky_generate)

    worker.main(job["job_id"])
    final = job_store.load_job(job["job_id"])
    assert final["status"] == "partially_failed"
    assert final["completed_tracks"] == 1
    assert final["failed_tracks"] == 1
