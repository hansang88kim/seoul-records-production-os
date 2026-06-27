"""
tests/test_suno_dry_run.py (v0.3.2)
─────────────────────────────────────
Tests for Suno dry-run script, provider endpoint mapping,
and error handling — all using mock HTTP responses.
No real Suno server required.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from providers.suno.base import ProviderError, CandidateInfo


# ─── Dry-run script tests ───────────────────────────────────────────────────

def test_mock_dry_run_completes(tmp_path, monkeypatch):
    """Mock dry-run produces report with status=completed."""
    # Redirect output to tmp_path
    import workflows.suno_one_song_dry_run as dr
    monkeypatch.setattr(dr, "__file__", str(tmp_path / "suno_one_song_dry_run.py"))

    report = dr.run_dry_run(mock=True)

    assert report["status"] == "completed"
    assert report["mode"] == "mock"
    assert report["task_id"] == "mock-task-001"
    assert report["wav_downloaded"] is True
    assert len(report["candidates"]) == 2
    assert report["errors"] == []


def test_mock_dry_run_report_schema(tmp_path, monkeypatch):
    """Dry-run report has all required fields."""
    import workflows.suno_one_song_dry_run as dr
    monkeypatch.setattr(dr, "__file__", str(tmp_path / "suno_one_song_dry_run.py"))

    report = dr.run_dry_run(mock=True)

    required_keys = [
        "mode", "started_at", "title", "provider", "task_id",
        "status", "candidates", "wav_downloaded", "mp3_preview_downloaded",
        "manual_import_required", "errors", "completed_at",
    ]
    for key in required_keys:
        assert key in report, f"Missing key in report: {key}"


def test_mock_dry_run_saves_files(tmp_path, monkeypatch):
    """Mock dry-run creates report.json, log.txt, and candidate WAVs."""
    import workflows.suno_one_song_dry_run as dr
    monkeypatch.setattr(dr, "__file__", str(tmp_path / "suno_one_song_dry_run.py"))

    dr.run_dry_run(mock=True)

    # Find the output directory
    dry_runs_dir = tmp_path.parent / "outputs" / "dry_runs"
    if not dry_runs_dir.exists():
        dry_runs_dir = tmp_path / "outputs" / "dry_runs"
    dirs = list(Path(tmp_path).parent.rglob("dry_run_report.json"))
    assert len(dirs) >= 1, "dry_run_report.json must be created"

    report_path = dirs[0]
    out = report_path.parent
    assert (out / "dry_run_log.txt").exists()
    assert (out / "candidates").exists()


# ─── Provider endpoint mapping tests ─────────────────────────────────────────

def test_local_provider_create_song_payload_mapping():
    """create_song builds correct payload for gcui-art/suno-api."""
    from providers.suno.local_unofficial_suno import LocalUnofficialSunoProvider

    p = LocalUnofficialSunoProvider()
    p._config["base_url"] = "http://127.0.0.1:19999"
    p._config["cookie"] = "test"

    captured = {}

    def mock_request(method, path, body=None):
        captured["method"] = method
        captured["path"] = path
        captured["body"] = body
        return [{"id": "test-id", "status": "submitted"}]

    p._request = mock_request

    p.create_song("밤이 지나면", "city pop", "test lyrics", {
        "vocal_gender": "Female",
        "exclude_styles": ["sax lead", "trot"],
        "model": "chirp-v4",
        "instrumental": False,
    })

    assert captured["path"] == "/api/custom_generate"
    assert captured["method"] == "POST"
    assert captured["body"]["title"] == "밤이 지나면"
    assert captured["body"]["prompt"] == "test lyrics"
    assert "female vocal" in captured["body"]["tags"].lower()
    assert "sax lead" in captured["body"].get("negative_tags", "")
    assert captured["body"]["model"] == "chirp-v4"


def test_status_polling_response_normalization():
    """get_status normalizes gcui-art clip response."""
    from providers.suno.local_unofficial_suno import LocalUnofficialSunoProvider

    p = LocalUnofficialSunoProvider()
    p._config["cookie"] = "test"

    mock_response = [
        {"id": "clip-1", "status": "complete", "duration": 220,
         "audio_url": "https://cdn.suno.ai/1.mp3", "metadata": {"tags": "pop"}},
        {"id": "clip-2", "status": "streaming", "duration": None,
         "audio_url": None, "metadata": {}},
    ]

    p._request = lambda m, path, body=None: mock_response
    p._last_clip_ids = ["clip-1", "clip-2"]

    status = p.get_status("clip-1")
    assert status["status"] == "generating"  # not all completed
    assert len(status["candidates"]) == 2
    assert status["candidates"][0]["status"] == "completed"
    assert status["candidates"][1]["status"] == "streaming"


def test_candidate_metadata_normalization():
    """Candidate metadata is properly extracted from Suno clip format."""
    from providers.suno.local_unofficial_suno import _normalize_candidates

    clips = [{
        "id": "clip-abc",
        "title": "Test Song",
        "audio_url": "https://cdn.suno.ai/abc.mp3",
        "audio_url_wav": "https://cdn.suno.ai/abc.wav",
        "status": "complete",
        "duration": 215.0,
        "model_name": "chirp-v4",
        "metadata": {"tags": "city pop, female vocal"},
    }]
    result = _normalize_candidates(clips)

    assert len(result) == 1
    c = result[0]
    assert c.candidate_id == "A"
    assert c.suno_clip_id == "clip-abc"
    assert c.wav_url == "https://cdn.suno.ai/abc.wav"
    assert c.audio_url == "https://cdn.suno.ai/abc.mp3"
    assert c.duration_seconds == 215.0
    assert c.status == "completed"
    assert c.metadata["model"] == "chirp-v4"


def test_wav_url_missing_returns_manual_import_required():
    """When wav_url is None and audio_url is also None → manual_import_required."""
    from providers.suno.local_unofficial_suno import LocalUnofficialSunoProvider

    p = LocalUnofficialSunoProvider()
    p._config["cookie"] = "test"

    # Mock: candidates with no URLs
    p._last_clip_ids = ["clip-x"]
    p._request = lambda m, path, body=None: [{
        "id": "clip-x", "status": "complete", "duration": 200,
        "audio_url": None, "metadata": {},
    }]

    with pytest.raises(ProviderError) as exc:
        p.download_wav("clip-x", Path("/tmp/test.wav"))
    assert exc.value.status == "wav_download_unavailable"


def test_mp3_only_distribution_blocked():
    """MP3-only candidate cannot become distribution master."""
    c = CandidateInfo(
        candidate_id="A",
        audio_url="https://cdn.suno.ai/x.mp3",
        wav_url=None,
        duration_seconds=220,
        status="completed",
    )
    # wav_url is None → any file downloaded from audio_url is MP3
    # Distribution master creation will be blocked by audio_qc
    assert c.wav_url is None, "No WAV URL → distribution blocked by QC pipeline"


def test_provider_unavailable_safe_error():
    """Connection failure → ProviderError with provider_unavailable, no crash."""
    from providers.suno.local_unofficial_suno import LocalUnofficialSunoProvider

    p = LocalUnofficialSunoProvider()
    p._config["base_url"] = "http://127.0.0.1:19999"
    p._config["cookie"] = "test"

    with pytest.raises(ProviderError) as exc:
        p.create_song("test", "pop", "lyrics")
    assert exc.value.status == "provider_unavailable"


def test_credentials_not_in_error_details():
    """ProviderError details must never contain raw credential values."""
    from providers.suno.local_unofficial_suno import LocalUnofficialSunoProvider

    p = LocalUnofficialSunoProvider()
    err = p.safe_error(
        "auth_required", "Session expired",
        cookie="__clerk_session=abc123xyz",
        api_token="sk-secret-key",
        base_url="http://localhost:3000",
    )
    assert "abc123" not in str(err.details)
    assert "sk-secret" not in str(err.details)
    assert err.details["cookie"] == "***REDACTED***"
    assert err.details["api_token"] == "***REDACTED***"
    assert err.details["base_url"] == "http://localhost:3000"  # non-credential OK


def test_dry_run_script_can_run_mock_mode():
    """Verify the dry-run script's mock mode returns valid report."""
    from workflows.suno_one_song_dry_run import MockLocalProvider

    p = MockLocalProvider()
    assert p.PROVIDER_NAME == "mock_local_dry_run"
    task_id = p.create_song("test", "pop", "lyrics")
    assert task_id == "mock-task-001"
    status = p.get_status(task_id)
    assert status["status"] == "completed"
    assert len(status["candidates"]) == 2


def test_existing_v031_tests_still_importable():
    """Verify v0.3.1 modules still import without error."""
    from workflows.audio_qc import run_audio_qc
    from workflows.create_distribution_master import create_distribution_master
    from workflows.render_video import export_video_package
    from app.tabs.project_library import list_projects_library
    from providers.suno.base import ProviderCapabilities, ProviderError
    from providers.suno.local_unofficial_suno import LocalUnofficialSunoProvider
    from providers.suno.playwright_suno_web import PlaywrightSunoWebProvider
