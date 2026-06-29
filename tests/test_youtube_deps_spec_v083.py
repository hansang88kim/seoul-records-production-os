"""
tests/test_youtube_deps_spec_v083.py — v0.8.3 spec dependency tests.

Covers the spec's exact function names, the worker-stage guard, and the
security guarantee that dependency-missing errors never expose secrets.
No real API calls.
"""
from __future__ import annotations
import json
import pytest
from pathlib import Path
from unittest import mock


GOOGLE_PKGS = [
    "google-api-python-client",
    "google-auth",
    "google-auth-oauthlib",
    "google-auth-httplib2",
]


# ─── Declared dependencies ───────────────────────────────────────────────────

def test_youtube_real_upload_dependencies_declared():
    req = Path("requirements.txt").read_text(encoding="utf-8")
    pp = Path("pyproject.toml").read_text(encoding="utf-8")
    for pkg in GOOGLE_PKGS:
        assert pkg in req and pkg in pp


def test_requirements_include_google_api_client():
    req = Path("requirements.txt").read_text(encoding="utf-8")
    assert "google-api-python-client" in req


def test_requirements_include_google_auth_oauthlib():
    req = Path("requirements.txt").read_text(encoding="utf-8")
    assert "google-auth-oauthlib" in req


def test_pyproject_includes_google_api_dependencies():
    pp = Path("pyproject.toml").read_text(encoding="utf-8")
    for pkg in GOOGLE_PKGS:
        assert pkg in pp


# ─── Spec-named dependency functions ─────────────────────────────────────────

def test_dependency_check_reports_available_when_imports_exist():
    import services.youtube.dependency_check as dep
    with mock.patch.object(dep.importlib.util, "find_spec", return_value=object()):
        report = dep.check_youtube_api_dependencies()
        assert report["available"] is True
        assert report["missing"] == []
        assert dep.is_real_youtube_upload_available() is True
        assert dep.get_missing_youtube_api_dependencies() == []


def test_dependency_check_reports_missing_when_imports_missing():
    import services.youtube.dependency_check as dep
    with mock.patch.object(dep.importlib.util, "find_spec", return_value=None):
        report = dep.check_youtube_api_dependencies()
        assert report["available"] is False
        assert "google-api-python-client" in report["missing"]
        assert "설치" in report["message"] or "install" in report["message"].lower()
        assert dep.is_real_youtube_upload_available() is False


def test_real_upload_disabled_when_google_libs_missing():
    src = Path("app/tabs/youtube_package.py").read_text(encoding="utf-8")
    assert "check_youtube_api_dependencies" in src
    assert "disabled=not libs_ok" in src
    assert "pip install -r requirements.txt" in src


def test_oauth_button_warns_when_google_auth_oauthlib_missing():
    import services.youtube.dependency_check as dep

    def fake_find_spec(name):
        return None if name == "google_auth_oauthlib" else object()

    with mock.patch.object(dep.importlib.util, "find_spec", side_effect=fake_find_spec):
        hint = dep.oauth_install_hint()
        assert "google-auth-oauthlib" in hint
    src = Path("app/tabs/youtube_package.py").read_text(encoding="utf-8")
    assert "disabled=bool(oauth_hint)" in src


# ─── Worker-stage guard ──────────────────────────────────────────────────────

@pytest.fixture
def upload_tmp(monkeypatch, tmp_path):
    import services.youtube.upload_job_store as ujs
    monkeypatch.setattr(ujs, "_jobs_dir", lambda: tmp_path / "jobs")
    return tmp_path


def _make_job(tmp_path):
    from services.youtube.upload_job_store import create_upload_job
    from services.youtube.upload_payload_service import build_upload_payload
    video = tmp_path / "final_video.mp4"; video.write_bytes(b"\x00" * 1000)
    payload = build_upload_payload("T", "d", ["citypop"], privacy_status="private")
    return create_upload_job("pkg", str(video), "", "T", payload)


def test_worker_fails_gracefully_when_real_api_dependencies_missing(upload_tmp):
    """real mode + missing deps → status=failed with sanitized message + missing list."""
    from services.youtube.upload_job_store import load_upload_state, _jobs_dir
    from workers.youtube_upload_worker import run_upload_job
    import services.youtube.dependency_check as dep

    s = _make_job(upload_tmp)
    jid = s["upload_job_id"]
    # Force deps missing
    with mock.patch.object(dep.importlib.util, "find_spec", return_value=None):
        run_upload_job(jid, use_mock=False)  # real mode

    state = load_upload_state(jid)
    assert state["status"] == "failed"
    assert "dependencies are missing" in state["last_message"].lower()
    assert any("google-api-python-client" in e for e in state["errors"])
    # Result file written with the missing list
    result = json.loads((_jobs_dir() / jid / "upload_result.json").read_text(encoding="utf-8"))
    assert result["status"] == "failed"
    assert "google-api-python-client" in result["errors"]


def test_mock_upload_works_even_if_real_api_dependencies_missing(upload_tmp):
    """Mock upload must succeed regardless of the Google libs being absent."""
    from services.youtube.upload_job_store import load_upload_state
    from workers.youtube_upload_worker import run_upload_job
    import services.youtube.dependency_check as dep

    s = _make_job(upload_tmp)
    jid = s["upload_job_id"]
    with mock.patch.object(dep.importlib.util, "find_spec", return_value=None):
        run_upload_job(jid, use_mock=True)  # mock mode — deps irrelevant

    state = load_upload_state(jid)
    assert state["status"] == "completed"
    assert state["privacy_status"] == "private"


# ─── Security: dependency errors never expose secrets ────────────────────────

def test_missing_dependency_error_does_not_expose_client_secret(upload_tmp, monkeypatch):
    from services.youtube.upload_job_store import _jobs_dir
    from workers.youtube_upload_worker import run_upload_job
    import services.youtube.dependency_check as dep
    import services.youtube.token_store as ts
    monkeypatch.setattr(ts, "_auth_dir", lambda: upload_tmp / "auth")
    # Store a client secret + token that must NOT leak into the failure output
    ts.save_client_secret({"installed": {"client_id": "id",
                                         "client_secret": "SUPERSECRET123",
                                         "token_uri": "https://oauth2"}})
    ts.save_token({"access_token": "ya29.LEAKTOKEN", "refresh_token": "1//LEAKREFRESH"})

    s = _make_job(upload_tmp)
    jid = s["upload_job_id"]
    with mock.patch.object(dep.importlib.util, "find_spec", return_value=None):
        run_upload_job(jid, use_mock=False)

    jd = _jobs_dir() / jid
    blob = ""
    for f in jd.iterdir():
        blob += f.read_text(encoding="utf-8")
    assert "SUPERSECRET123" not in blob
    assert "ya29.LEAKTOKEN" not in blob
    assert "1//LEAKREFRESH" not in blob


def test_missing_dependency_error_does_not_expose_token(upload_tmp, monkeypatch):
    from services.youtube.upload_job_store import get_upload_log
    from workers.youtube_upload_worker import run_upload_job
    import services.youtube.dependency_check as dep
    import services.youtube.token_store as ts
    monkeypatch.setattr(ts, "_auth_dir", lambda: upload_tmp / "auth")
    ts.save_token({"access_token": "ya29.SECRETTOKEN", "refresh_token": "1//SECRET"})

    s = _make_job(upload_tmp)
    jid = s["upload_job_id"]
    with mock.patch.object(dep.importlib.util, "find_spec", return_value=None):
        run_upload_job(jid, use_mock=False)

    log = get_upload_log(jid, last_n=50)
    blob = json.dumps(log)
    assert "ya29.SECRETTOKEN" not in blob
    assert "1//SECRET" not in blob


# ─── Existing flows unchanged ────────────────────────────────────────────────

def test_existing_manual_package_flow_unchanged(tmp_path, monkeypatch):
    import services.youtube.youtube_package_service as yps
    monkeypatch.setattr(yps, "_packages_root", lambda: tmp_path / "youtube_package")
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL not available")
    video = tmp_path / "final_video.mp4"; video.write_bytes(b"\x00" * 5000)
    chapters = tmp_path / "chapters.txt"; chapters.write_text("00:00 a", encoding="utf-8")
    thumb = tmp_path / "youtube_thumbnail_16x9.png"
    Image.new("RGB", (1920, 1080), (30, 30, 60)).save(thumb)
    manifest = yps.create_package(
        video_path=str(video), thumbnail_path=str(thumb), chapters_path=str(chapters),
        playlist_title="T", country="korea", volume=1, mood="n",
        upload_mode="manual_package_only")
    assert manifest["upload_mode"] == "manual_package_only"
    assert manifest["privacy_status_default"] == "private"


def test_existing_mock_upload_flow_unchanged(upload_tmp):
    from services.youtube.upload_job_store import load_upload_state
    from workers.youtube_upload_worker import run_upload_job
    s = _make_job(upload_tmp)
    run_upload_job(s["upload_job_id"], use_mock=True)
    assert load_upload_state(s["upload_job_id"])["status"] == "completed"


def test_existing_music_generation_unaffected():
    from providers.ai.base import MOCK_SONGS
    assert len(MOCK_SONGS) >= 2


def test_existing_thumbnail_studio_unaffected():
    from services.thumbnail.prompt_generator import generate_flow_prompt
    assert generate_flow_prompt("korea", "n", 0)["main_prompt"]


def test_existing_video_renderer_unaffected():
    from services.video.render_plan import build_full_render_command
    assert callable(build_full_render_command)
