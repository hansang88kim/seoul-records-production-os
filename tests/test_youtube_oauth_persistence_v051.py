"""
tests/test_youtube_oauth_persistence_v051.py — v1.0.0-alpha.51

Fixes two real problems reported after screenshots:
  1. client_secret.json looked like it needed re-uploading every time —
     it was already persisted to disk, but every screen re-rendered a
     blank file_uploader with no "already configured" indicator. New
     shared panel (app/ui/youtube_oauth_panel.py) is persisted-aware and
     used by BOTH Settings and the YouTube Package tab.
  2. authorize() swallowed the real exception and always showed a
     generic "인증 실패", giving no way to diagnose WHY (wrong client
     type, testing-mode Gmail not added, browser closed, etc). It now
     surfaces a redacted type+message.
  3. A 'web'-type client_secret (vs. 'installed'/Desktop app) is flagged
     immediately on upload, since it's the most common real-world cause
     of a silent local-OAuth failure with InstalledAppFlow.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolate_dirs(monkeypatch, tmp_path):
    import services.youtube.token_store as ts
    monkeypatch.setattr(ts, "_auth_dir", lambda: tmp_path / "youtube_auth")
    yield


# ─── client_secret type hint (web vs. installed) ────────────────────────────

def test_installed_type_has_no_hint():
    from services.youtube.oauth_service import client_secret_type_hint
    secret = {"installed": {"client_id": "x", "client_secret": "y"}}
    assert client_secret_type_hint(secret) == ""


def test_web_type_warns_to_use_desktop_app():
    from services.youtube.oauth_service import client_secret_type_hint
    secret = {"web": {"client_id": "x", "client_secret": "y"}}
    hint = client_secret_type_hint(secret)
    assert "데스크톱 앱" in hint
    assert "웹 애플리케이션" in hint


def test_upload_of_web_type_surfaces_warning_in_status():
    from services.youtube.oauth_service import load_client_secret_from_bytes
    from services.youtube import token_store as ts
    secret = {"web": {"client_id": "abc.apps.googleusercontent.com",
                      "client_secret": "SECRET123", "token_uri": "https://oauth2"}}
    ok = load_client_secret_from_bytes(json.dumps(secret).encode("utf-8"))
    assert ok is True
    status = ts.get_status()
    assert status["status"] == ts.STATUS_CLIENT_LOADED
    assert "데스크톱 앱" in status["message"]


def test_upload_of_installed_type_has_clean_status():
    from services.youtube.oauth_service import load_client_secret_from_bytes
    from services.youtube import token_store as ts
    secret = {"installed": {"client_id": "abc.apps.googleusercontent.com",
                            "client_secret": "SECRET123", "token_uri": "https://oauth2"}}
    ok = load_client_secret_from_bytes(json.dumps(secret).encode("utf-8"))
    assert ok is True
    status = ts.get_status()
    assert status["message"] == "client_secret.json 로드됨"


# ─── authorize() no longer swallows the real error ──────────────────────────

def test_authorize_surfaces_real_error_not_generic_message(monkeypatch):
    from services.youtube import oauth_service as oauth
    from services.youtube import token_store as ts

    secret = {"installed": {"client_id": "x", "client_secret": "y",
                            "token_uri": "https://oauth2"}}
    oauth.load_client_secret_from_bytes(json.dumps(secret).encode("utf-8"))

    class _FakeFlow:
        @staticmethod
        def from_client_config(*a, **k):
            raise RuntimeError("redirect_uri_mismatch: no loopback URI registered")

    monkeypatch.setitem(
        __import__("sys").modules, "google_auth_oauthlib.flow",
        type("m", (), {"InstalledAppFlow": _FakeFlow}))

    res = oauth.authorize()
    assert res["status"] == ts.STATUS_FAILED
    assert "RuntimeError" in res["message"]
    assert "redirect_uri_mismatch" in res["message"]
    assert res["message"] != "인증 실패"  # old generic message is gone


def test_authorize_error_message_is_redacted(monkeypatch):
    from services.youtube import oauth_service as oauth
    from services.youtube import token_store as ts

    secret = {"installed": {"client_id": "x", "client_secret": "y",
                            "token_uri": "https://oauth2"}}
    oauth.load_client_secret_from_bytes(json.dumps(secret).encode("utf-8"))

    class _FakeFlow:
        @staticmethod
        def from_client_config(*a, **k):
            raise RuntimeError("token=ya29.SUPERSECRETVALUEHERE123456789 invalid")

    monkeypatch.setitem(
        __import__("sys").modules, "google_auth_oauthlib.flow",
        type("m", (), {"InstalledAppFlow": _FakeFlow}))

    res = oauth.authorize()
    assert "SUPERSECRETVALUEHERE123456789" not in res["message"]


# ─── shared panel: persisted-aware (no forced re-upload) ────────────────────

def test_shared_panel_module_exists_and_is_persisted_aware():
    src = Path("app/ui/youtube_oauth_panel.py").read_text(encoding="utf-8")
    assert "def render_oauth_account_panel" in src
    assert "has_client_secret" in src
    assert "이미 등록" in src or "등록됨" in src


def test_youtube_package_uses_shared_panel_no_duplicate_uploader():
    src = Path("app/tabs/youtube_package.py").read_text(encoding="utf-8")
    assert "render_oauth_account_panel" in src
    # The old always-visible raw uploader keyed 'yt_client_secret' is gone
    assert 'key="yt_client_secret"' not in src


def test_settings_page_has_youtube_oauth_section():
    src = Path("app/main.py").read_text(encoding="utf-8")
    assert "render_oauth_account_panel" in src
    assert "▶️ YouTube" in src


def test_panel_calls_are_namespaced_to_avoid_key_collisions():
    yt_pkg = Path("app/tabs/youtube_package.py").read_text(encoding="utf-8")
    settings = Path("app/main.py").read_text(encoding="utf-8")
    assert 'key_ns="yt_pkg"' in yt_pkg
    assert 'key_ns="settings_yt"' in settings


# ─── status labels are centralized (no drift between screens) ──────────────

def test_status_labels_centralized_in_token_store():
    from services.youtube import token_store as ts
    assert hasattr(ts, "STATUS_LABELS")
    assert ts.STATUS_LABELS[ts.STATUS_AUTHORIZED] == "🟢 인증됨"
    assert ts.STATUS_LABELS[ts.STATUS_NOT_CONFIGURED] == "⚪ 설정되지 않음"


try:
    from streamlit.testing.v1 import AppTest
    _HAS_APPTEST = True
except Exception:
    _HAS_APPTEST = False


@pytest.mark.skipif(not _HAS_APPTEST, reason="streamlit.testing.v1 not available")
def test_settings_page_renders_without_exception(monkeypatch, tmp_path):
    at = AppTest.from_file("app/main.py")
    at.session_state["nav_page"] = "settings"
    at.run(timeout=30)
    assert not at.exception


@pytest.mark.skipif(not _HAS_APPTEST, reason="streamlit.testing.v1 not available")
def test_youtube_package_renders_without_exception(monkeypatch, tmp_path):
    at = AppTest.from_file("app/main.py")
    at.session_state["nav_page"] = "youtube"
    at.run(timeout=30)
    assert not at.exception
