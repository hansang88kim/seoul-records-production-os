"""
tests/test_youtube_deps_v083.py — Google API dependency declaration + guards.

Verifies the Google libraries are declared in requirements/pyproject and that
the app degrades clearly (not silently) when they are missing. No real API.
"""
from __future__ import annotations
import sys
import pytest
from pathlib import Path
from unittest import mock


GOOGLE_PKGS = [
    "google-api-python-client",
    "google-auth",
    "google-auth-oauthlib",
    "google-auth-httplib2",
]


# ─── Declared in requirements / pyproject ────────────────────────────────────

def test_requirements_include_google_api_client():
    req = Path("requirements.txt").read_text(encoding="utf-8")
    for pkg in GOOGLE_PKGS:
        assert pkg in req, f"{pkg} missing from requirements.txt"


def test_pyproject_includes_google_api_dependencies():
    pp = Path("pyproject.toml").read_text(encoding="utf-8")
    for pkg in GOOGLE_PKGS:
        assert pkg in pp, f"{pkg} missing from pyproject.toml"


def test_youtube_real_upload_dependencies_declared():
    """All four libs appear in BOTH requirements and pyproject."""
    req = Path("requirements.txt").read_text(encoding="utf-8")
    pp = Path("pyproject.toml").read_text(encoding="utf-8")
    for pkg in GOOGLE_PKGS:
        assert pkg in req and pkg in pp


# ─── Dependency-check helper ─────────────────────────────────────────────────

def test_dependency_check_reports_missing():
    """When find_spec returns None, the libs are reported missing."""
    import services.youtube.dependency_check as dep
    with mock.patch.object(dep.importlib.util, "find_spec", return_value=None):
        assert dep.google_libs_available() is False
        missing = dep.missing_google_libs()
        assert "google-api-python-client" in missing
        assert dep.install_hint() != ""
        assert "pip install" in dep.install_hint()


def test_dependency_check_reports_available():
    import services.youtube.dependency_check as dep
    fake_spec = object()
    with mock.patch.object(dep.importlib.util, "find_spec", return_value=fake_spec):
        assert dep.google_libs_available() is True
        assert dep.missing_google_libs() == []
        assert dep.install_hint() == ""


def test_real_upload_disabled_when_google_libs_missing():
    """The UI gates real upload on the dependency check."""
    src = Path("app/tabs/youtube_package.py").read_text(encoding="utf-8")
    # The UI checks lib availability (structured report) and disables the toggle
    assert "check_youtube_api_dependencies" in src
    assert "disabled=not libs_ok" in src


def test_oauth_button_warns_when_google_auth_oauthlib_missing():
    import services.youtube.dependency_check as dep

    def fake_find_spec(name):
        # Everything present EXCEPT google_auth_oauthlib
        if name == "google_auth_oauthlib":
            return None
        return object()

    with mock.patch.object(dep.importlib.util, "find_spec", side_effect=fake_find_spec):
        hint = dep.oauth_install_hint()
        assert hint != ""
        assert "google-auth-oauthlib" in hint
    # And the UI shows the oauth hint + disables the button
    src = Path("app/tabs/youtube_package.py").read_text(encoding="utf-8")
    assert "oauth_install_hint" in src
    assert "disabled=bool(oauth_hint)" in src


# ─── Authorize gives a clear message when libs missing (no silent fail) ──────

def test_authorize_clear_message_when_oauthlib_missing(monkeypatch, tmp_path):
    import services.youtube.token_store as ts
    import services.youtube.oauth_service as oauth
    monkeypatch.setattr(ts, "_auth_dir", lambda: tmp_path / "auth")
    # Provide a client secret so we get past the not_configured check
    ts.save_client_secret({"installed": {"client_id": "x", "client_secret": "y",
                                         "token_uri": "https://oauth2"}})
    # Force the oauthlib import to fail
    real_import = __import__

    def fake_import(name, *a, **k):
        if name.startswith("google_auth_oauthlib"):
            raise ImportError("no module")
        return real_import(name, *a, **k)

    with mock.patch("builtins.__import__", side_effect=fake_import):
        # authorize() with no headless token tries the real flow → lib missing
        status = oauth.authorize()
    # Must be a clear failure with an install hint, not a silent pass
    assert status["status"] == ts.STATUS_FAILED
    assert "google-auth-oauthlib" in status["message"] or "pip install" in status["message"]


# ─── Mock flow still works (unaffected) ──────────────────────────────────────

def test_mock_upload_flow_still_works_v083(tmp_path, monkeypatch):
    import services.youtube.upload_job_store as ujs
    monkeypatch.setattr(ujs, "_jobs_dir", lambda: tmp_path / "jobs")
    from services.youtube.upload_job_store import create_upload_job, load_upload_state
    from services.youtube.upload_payload_service import build_upload_payload
    from workers.youtube_upload_worker import run_upload_job

    video = tmp_path / "final_video.mp4"; video.write_bytes(b"\x00" * 1000)
    payload = build_upload_payload("T", "d", ["citypop"], privacy_status="private")
    s = create_upload_job("pkg", str(video), "", "T", payload)
    run_upload_job(s["upload_job_id"], use_mock=True)
    state = load_upload_state(s["upload_job_id"])
    assert state["status"] == "completed"
    assert state["privacy_status"] == "private"


def test_default_still_manual_and_private_v083():
    from services.youtube.youtube_package_service import DEFAULT_UPLOAD_MODE
    from services.youtube.upload_payload_service import DEFAULT_PRIVACY
    assert DEFAULT_UPLOAD_MODE == "manual_package_only"
    assert DEFAULT_PRIVACY == "private"


# ─── Independence ────────────────────────────────────────────────────────────

def test_existing_features_unaffected_v083():
    from providers.ai.base import MOCK_SONGS
    from services.video.render_plan import build_full_render_command
    from services.thumbnail.prompt_generator import generate_flow_prompt
    assert len(MOCK_SONGS) >= 2
    assert callable(build_full_render_command)
    assert generate_flow_prompt("korea", "n", 0)["main_prompt"]
