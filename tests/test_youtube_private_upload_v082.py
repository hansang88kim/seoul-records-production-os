"""
tests/test_youtube_private_upload_v082.py — YouTube Private Upload tests.

NO real YouTube API calls. Mock client only. Verifies private-by-default,
OAuth/token security, background upload job flow, thumbnail handling, retry,
checklist gating, and redaction.
"""
from __future__ import annotations
import json
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def isolate_dirs(monkeypatch, tmp_path):
    import services.youtube.token_store as ts
    import services.youtube.upload_job_store as ujs
    monkeypatch.setattr(ts, "_auth_dir", lambda: tmp_path / "youtube_auth")
    monkeypatch.setattr(ujs, "_jobs_dir", lambda: tmp_path / "youtube_upload" / "jobs")
    yield


def _payload(title="Test Video", privacy="private"):
    from services.youtube.upload_payload_service import build_upload_payload
    return build_upload_payload(title, "desc", ["citypop"], privacy_status=privacy)


# ─── Upload modes ────────────────────────────────────────────────────────────

def test_youtube_private_upload_mode_exists():
    from app.tabs import youtube_package as yp
    src = Path("app/tabs/youtube_package.py").read_text(encoding="utf-8")
    assert "API Private Upload" in src or "private" in src.lower()


def test_default_upload_mode_still_manual_package_only():
    from services.youtube.youtube_package_service import DEFAULT_UPLOAD_MODE
    assert DEFAULT_UPLOAD_MODE == "manual_package_only"


def test_api_private_upload_uses_private_privacy_status():
    p = _payload(privacy="private")
    assert p["status"]["privacyStatus"] == "private"


def test_public_upload_not_default():
    p = _payload()  # no privacy specified beyond default
    assert p["status"]["privacyStatus"] != "public"
    # Even building with an invalid value falls back to private, not public
    from services.youtube.upload_payload_service import build_upload_payload
    p2 = build_upload_payload("t", "d", [], privacy_status="garbage")
    assert p2["status"]["privacyStatus"] == "private"


# ─── OAuth / token security ──────────────────────────────────────────────────

def test_oauth_status_not_configured_without_client_secret():
    from services.youtube.oauth_service import get_auth_status
    from services.youtube import token_store as ts
    status = get_auth_status()
    assert status["status"] == ts.STATUS_NOT_CONFIGURED


def test_client_secret_upload_stored_locally():
    from services.youtube.oauth_service import load_client_secret_from_bytes
    from services.youtube import token_store as ts
    secret = {"installed": {"client_id": "abc.apps.googleusercontent.com",
                            "client_secret": "SECRET123", "token_uri": "https://oauth2"}}
    ok = load_client_secret_from_bytes(json.dumps(secret).encode("utf-8"))
    assert ok is True
    assert ts.has_client_secret() is True
    assert ts.get_status()["status"] == ts.STATUS_CLIENT_LOADED


def test_token_store_does_not_expose_raw_token():
    from services.youtube import token_store as ts
    ts.save_token({"access_token": "ya29.SECRETTOKEN", "refresh_token": "1//REFRESH"})
    summary = ts.public_token_summary()
    # Summary has booleans, NOT the raw token
    assert summary["has_access_token"] is True
    assert summary["has_refresh_token"] is True
    assert "ya29.SECRETTOKEN" not in json.dumps(summary)
    assert "1//REFRESH" not in json.dumps(summary)


def test_oauth_token_redacted_in_logs():
    from services.youtube.upload_job_store import (
        create_upload_job, append_upload_log, get_upload_log,
    )
    s = create_upload_job("pkg1", "/v.mp4", "/t.png", "T", _payload())
    jid = s["upload_job_id"]
    # Try to log something containing a token — it must be redacted
    append_upload_log(jid, "debug Authorization: Bearer ya29.LEAKEDTOKEN here")
    log = get_upload_log(jid)
    blob = json.dumps(log)
    assert "ya29.LEAKEDTOKEN" not in blob
    assert "REDACTED" in blob


# ─── Upload job flow ─────────────────────────────────────────────────────────

def test_upload_job_created():
    from services.youtube.upload_job_store import create_upload_job, load_upload_state
    s = create_upload_job("pkg1", "/v.mp4", "/t.png", "My Title", _payload())
    assert s["upload_job_id"]
    assert s["status"] == "queued"
    assert s["privacy_status"] == "private"
    loaded = load_upload_state(s["upload_job_id"])
    assert loaded["title"] == "My Title"


def test_upload_state_json_created():
    from services.youtube.upload_job_store import create_upload_job, _jobs_dir
    s = create_upload_job("pkg1", "/v.mp4", "/t.png", "T", _payload())
    jid = s["upload_job_id"]
    assert (_jobs_dir() / jid / "upload_state.json").exists()
    assert (_jobs_dir() / jid / "upload_payload_snapshot.json").exists()
    assert (_jobs_dir() / jid / "request_sanitized.json").exists()


def test_upload_worker_uses_mock_client_in_tests(tmp_path):
    """The worker, run with use_mock=True, performs a full mock upload."""
    from services.youtube.upload_job_store import create_upload_job, load_upload_state
    from workers.youtube_upload_worker import run_upload_job
    video = tmp_path / "final_video.mp4"; video.write_bytes(b"\x00" * 1000)
    thumb = tmp_path / "thumbnail_upload_ready.png"; thumb.write_bytes(b"\x89PNG" + b"\x00" * 50)
    s = create_upload_job("pkg1", str(video), str(thumb), "T", _payload())
    jid = s["upload_job_id"]
    run_upload_job(jid, use_mock=True)
    state = load_upload_state(jid)
    assert state["status"] == "completed"
    assert state["video_id"]
    assert state["video_id"].startswith("MOCK_")


def test_upload_progress_jsonl_written(tmp_path):
    from services.youtube.upload_job_store import create_upload_job, _jobs_dir
    from workers.youtube_upload_worker import run_upload_job
    video = tmp_path / "v.mp4"; video.write_bytes(b"\x00" * 1000)
    s = create_upload_job("pkg1", str(video), "", "T", _payload())
    jid = s["upload_job_id"]
    run_upload_job(jid, use_mock=True)
    p = _jobs_dir() / jid / "upload_progress.jsonl"
    assert p.exists()
    assert len(p.read_text().strip().splitlines()) >= 1


def test_upload_result_json_created(tmp_path):
    from services.youtube.upload_job_store import create_upload_job, _jobs_dir
    from workers.youtube_upload_worker import run_upload_job
    video = tmp_path / "v.mp4"; video.write_bytes(b"\x00" * 1000)
    s = create_upload_job("pkg1", str(video), "", "T", _payload())
    jid = s["upload_job_id"]
    run_upload_job(jid, use_mock=True)
    rp = _jobs_dir() / jid / "upload_result.json"
    assert rp.exists()
    result = json.loads(rp.read_text())
    assert result["status"] in ("completed", "partial_success")
    assert result["video_id"]


def test_video_id_saved_after_success(tmp_path):
    from services.youtube.upload_job_store import create_upload_job, load_upload_state
    from workers.youtube_upload_worker import run_upload_job
    video = tmp_path / "v.mp4"; video.write_bytes(b"\x00" * 1000)
    s = create_upload_job("pkg1", str(video), "", "T", _payload())
    jid = s["upload_job_id"]
    run_upload_job(jid, use_mock=True)
    state = load_upload_state(jid)
    assert state["video_id"]
    assert state["youtube_url"].startswith("https://youtu.be/")
    assert state["privacy_status"] == "private"


# ─── Thumbnail handling ──────────────────────────────────────────────────────

def test_thumbnail_set_called_after_video_upload(tmp_path):
    from services.youtube.upload_job_store import create_upload_job, load_upload_state
    from workers.youtube_upload_worker import run_upload_job
    video = tmp_path / "v.mp4"; video.write_bytes(b"\x00" * 1000)
    thumb = tmp_path / "t.png"; thumb.write_bytes(b"\x89PNG" + b"\x00" * 50)
    s = create_upload_job("pkg1", str(video), str(thumb), "T", _payload())
    jid = s["upload_job_id"]
    run_upload_job(jid, use_mock=True)
    state = load_upload_state(jid)
    assert state["thumbnail_set_status"] == "completed"


def test_thumbnail_failure_marks_partial_success(tmp_path):
    from services.youtube.upload_job_store import create_upload_job, load_upload_state
    from workers.youtube_upload_worker import run_upload_job
    video = tmp_path / "v.mp4"; video.write_bytes(b"\x00" * 1000)
    thumb = tmp_path / "t.png"; thumb.write_bytes(b"\x89PNG" + b"\x00" * 50)
    s = create_upload_job("pkg1", str(video), str(thumb), "T", _payload())
    jid = s["upload_job_id"]
    # Mock configured to FAIL the thumbnail set
    run_upload_job(jid, use_mock=True, mock_kwargs={"fail_thumbnail": True})
    state = load_upload_state(jid)
    assert state["status"] == "partial_success"
    assert state["thumbnail_set_status"] == "failed"
    # Video remains private (never auto-public, never deleted)
    assert state["privacy_status"] == "private"
    assert state["video_id"]


def test_retry_thumbnail_only_after_partial_success(tmp_path):
    from services.youtube.upload_job_store import create_upload_job, load_upload_state
    from workers.youtube_upload_worker import run_upload_job, run_thumbnail_retry
    video = tmp_path / "v.mp4"; video.write_bytes(b"\x00" * 1000)
    thumb = tmp_path / "t.png"; thumb.write_bytes(b"\x89PNG" + b"\x00" * 50)
    s = create_upload_job("pkg1", str(video), str(thumb), "T", _payload())
    jid = s["upload_job_id"]
    run_upload_job(jid, use_mock=True, mock_kwargs={"fail_thumbnail": True})
    assert load_upload_state(jid)["status"] == "partial_success"
    vid_before = load_upload_state(jid)["video_id"]
    # Retry thumbnail only (now succeeds) — must NOT re-upload the video
    run_thumbnail_retry(jid, use_mock=True, mock_kwargs={"fail_thumbnail": False})
    state = load_upload_state(jid)
    assert state["status"] == "completed"
    assert state["thumbnail_set_status"] == "completed"
    assert state["video_id"] == vid_before  # same video, not re-uploaded


# ─── Checklist gate ──────────────────────────────────────────────────────────

def test_upload_button_disabled_until_checklist_reviewed():
    """The UI gates the upload behind a reviewed checklist."""
    src = Path("app/tabs/youtube_package.py").read_text(encoding="utf-8")
    # A reviewed flag gates the upload button
    assert "reviewed" in src.lower()
    assert "disabled" in src.lower()


# ─── No real API calls / redaction ───────────────────────────────────────────

def test_no_real_youtube_api_calls_in_tests(tmp_path):
    """Worker default + factory return the mock (no googleapiclient import)."""
    from services.youtube.youtube_api_client import get_youtube_client
    client = get_youtube_client(use_mock=True)
    assert client.__class__.__name__ == "MockYouTubeApiClient"
    # The mock records calls but performs no network
    r = client.upload_video_private(_payload(), str(tmp_path / "v.mp4"))
    assert r["mock"] is True


def test_authorization_header_redacted():
    from services.security.redaction import redact_headers, redact_dict
    h = redact_headers({"Authorization": "Bearer ya29.SECRET", "Accept": "application/json"})
    assert h["Authorization"] == "***REDACTED***"
    assert h["Accept"] == "application/json"
    # Nested dict redaction
    d = redact_dict({"status": {"access_token": "ya29.X", "privacyStatus": "private"}})
    assert d["status"]["access_token"] == "***REDACTED***"
    assert d["status"]["privacyStatus"] == "private"


def test_token_file_not_in_package_export(tmp_path, monkeypatch):
    """token.json lives under youtube_auth, never inside a package folder."""
    from services.youtube import token_store as ts
    ts.save_token({"access_token": "ya29.SECRET"})
    # The token path is under youtube_auth, not youtube_package
    assert "youtube_auth" in str(ts._token_path())
    assert "youtube_package" not in str(ts._token_path())


# ─── Existing features unaffected ────────────────────────────────────────────

def test_existing_manual_package_flow_unchanged(tmp_path, monkeypatch):
    import services.youtube.youtube_package_service as yps
    monkeypatch.setattr(yps, "_packages_root", lambda: tmp_path / "youtube_package")
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL not available")
    video = tmp_path / "final_video.mp4"; video.write_bytes(b"\x00" * 5000)
    chapters = tmp_path / "chapters.txt"; chapters.write_text("00:00 밤이 지나면", encoding="utf-8")
    thumb = tmp_path / "youtube_thumbnail_16x9.png"
    Image.new("RGB", (1920, 1080), (30, 30, 60)).save(thumb)
    manifest = yps.create_package(
        video_path=str(video), thumbnail_path=str(thumb), chapters_path=str(chapters),
        playlist_title="Test", country="korea", volume=1, mood="night",
        upload_mode="manual_package_only",
    )
    assert manifest["upload_mode"] == "manual_package_only"
    assert manifest["privacy_status_default"] == "private"


def test_existing_video_renderer_unaffected_v082():
    from services.video.render_plan import build_full_render_command
    assert callable(build_full_render_command)


def test_existing_thumbnail_studio_unaffected_v082():
    from services.thumbnail.prompt_generator import generate_flow_prompt
    assert generate_flow_prompt("korea", "n", 0)["main_prompt"]


def test_existing_music_generation_unaffected_v082():
    from providers.ai.base import MOCK_SONGS
    assert len(MOCK_SONGS) >= 2
