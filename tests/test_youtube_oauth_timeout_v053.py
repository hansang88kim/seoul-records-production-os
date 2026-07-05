"""
tests/test_youtube_oauth_timeout_v053.py — v1.0.0-alpha.53

Root cause targeted here: InstalledAppFlow.run_local_server() blocks
FOREVER waiting for the OAuth browser redirect. In a Streamlit app, if the
browser doesn't auto-open (headless/remote session, popup blocked, no
default browser) or the person never finishes the Google login, clicking
"🔑 YouTube 인증" just hangs with NO error and NO timeout — which looks
exactly like "인증이 안 됨" with zero diagnostic signal, and the person
has no way to know anything went wrong versus the app being broken.

authorize() now bounds the wait with a hard timeout and returns a clear,
actionable STATUS_FAILED message instead of hanging.
"""
from __future__ import annotations

import time

import pytest


@pytest.fixture(autouse=True)
def isolate_dirs(monkeypatch, tmp_path):
    import services.youtube.token_store as ts
    monkeypatch.setattr(ts, "_auth_dir", lambda: tmp_path / "youtube_auth")
    yield


def _upload_installed_secret():
    import json
    from services.youtube import oauth_service as oauth
    secret = {"installed": {"client_id": "x", "client_secret": "y",
                            "token_uri": "https://oauth2"}}
    oauth.load_client_secret_from_bytes(json.dumps(secret).encode("utf-8"))


class _SlowFlow:
    """Simulates a browser that never completes the OAuth redirect."""
    @staticmethod
    def from_client_config(*a, **k):
        return _SlowFlow()

    def run_local_server(self, port=0):
        time.sleep(5)  # much longer than the test's timeout_seconds
        raise AssertionError("should never reach this — timed out first")


class _FastFlow:
    """Simulates a browser that completes the flow almost instantly."""
    @staticmethod
    def from_client_config(*a, **k):
        return _FastFlow()

    def run_local_server(self, port=0):
        class _Creds:
            token = "tok"
            refresh_token = "rtok"
            token_uri = "https://oauth2"
            client_id = "x"
            client_secret = "y"
            scopes = ["scope"]
            expiry = None
        return _Creds()


def _patch_flow(monkeypatch, flow_cls):
    monkeypatch.setitem(
        __import__("sys").modules, "google_auth_oauthlib.flow",
        type("m", (), {"InstalledAppFlow": flow_cls}))


def test_authorize_times_out_instead_of_hanging_forever(monkeypatch):
    from services.youtube import oauth_service as oauth
    from services.youtube import token_store as ts

    _upload_installed_secret()
    _patch_flow(monkeypatch, _SlowFlow)

    start = time.monotonic()
    res = oauth.authorize(timeout_seconds=0.3)
    elapsed = time.monotonic() - start

    assert elapsed < 3.0, "authorize() should give up around the timeout, not hang"
    assert res["status"] == ts.STATUS_FAILED
    assert "시간" in res["message"] or "timeout" in res["message"].lower() \
        or "초" in res["message"]


def test_authorize_timeout_message_gives_actionable_guidance(monkeypatch):
    from services.youtube import oauth_service as oauth
    _upload_installed_secret()
    _patch_flow(monkeypatch, _SlowFlow)
    res = oauth.authorize(timeout_seconds=0.2)
    # Tells the person what to actually do, not just that it failed.
    assert "터미널" in res["message"] or "브라우저" in res["message"]


def test_authorize_succeeds_quickly_when_flow_completes_fast(monkeypatch):
    from services.youtube import oauth_service as oauth
    from services.youtube import token_store as ts
    _upload_installed_secret()
    _patch_flow(monkeypatch, _FastFlow)

    res = oauth.authorize(timeout_seconds=5)
    assert res["status"] == ts.STATUS_AUTHORIZED
    assert ts.has_token() is True


def test_default_timeout_is_generous_not_instant():
    """Sanity check: the production default isn't accidentally tiny."""
    import inspect
    from services.youtube.oauth_service import authorize
    sig = inspect.signature(authorize)
    assert sig.parameters["timeout_seconds"].default >= 60


def test_ui_panel_wraps_authorize_in_spinner_with_browser_guidance():
    from pathlib import Path
    src = Path("app/ui/youtube_oauth_panel.py").read_text(encoding="utf-8")
    assert "st.spinner" in src
    assert "터미널" in src
