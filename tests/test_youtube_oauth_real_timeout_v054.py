"""
tests/test_youtube_oauth_real_timeout_v054.py — v1.0.0-alpha.54

Uses the REAL google-auth-oauthlib library (when installed) instead of a
mock, to confirm run_local_server(timeout_seconds=...) genuinely raises
WSGITimeoutError when nothing ever connects — no browser, no login, just
the actual socket-level timeout the production code now relies on.

Skips cleanly when the optional dependency isn't installed (matches this
project's existing convention of never hard-requiring it).
"""
from __future__ import annotations

import time

import pytest

try:
    from google_auth_oauthlib.flow import InstalledAppFlow, WSGITimeoutError
    _HAS_LIB = True
except Exception:
    _HAS_LIB = False


@pytest.fixture(autouse=True)
def isolate_dirs(monkeypatch, tmp_path):
    import services.youtube.token_store as ts
    monkeypatch.setattr(ts, "_auth_dir", lambda: tmp_path / "youtube_auth")
    yield


@pytest.mark.skipif(not _HAS_LIB, reason="google-auth-oauthlib not installed")
def test_real_run_local_server_times_out_when_nothing_connects():
    """Nobody will ever hit this local server in a test — it must give up
    within ~1-2 seconds rather than hang the test suite."""
    secret = {"installed": {
        "client_id": "fake-client-id.apps.googleusercontent.com",
        "client_secret": "fake-secret",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }}
    flow = InstalledAppFlow.from_client_config(
        secret, scopes=["https://www.googleapis.com/auth/youtube.upload"])

    start = time.monotonic()
    with pytest.raises(WSGITimeoutError):
        flow.run_local_server(port=0, open_browser=False, timeout_seconds=1)
    elapsed = time.monotonic() - start
    assert elapsed < 5, "should abort promptly via the socket timeout"


@pytest.mark.skipif(not _HAS_LIB, reason="google-auth-oauthlib not installed")
def test_authorize_end_to_end_with_real_library_times_out_cleanly(monkeypatch):
    """Full authorize() path, real library, real (short) socket timeout —
    only the actual browser+login is unreachable in a test sandbox."""
    import json
    from services.youtube import oauth_service as oauth
    from services.youtube import token_store as ts

    secret = {"installed": {
        "client_id": "fake-client-id.apps.googleusercontent.com",
        "client_secret": "fake-secret",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }}
    oauth.load_client_secret_from_bytes(json.dumps(secret).encode("utf-8"))

    start = time.monotonic()
    res = oauth.authorize(timeout_seconds=1, open_browser=False)
    elapsed = time.monotonic() - start

    assert elapsed < 10
    assert res["status"] == ts.STATUS_FAILED
    assert "초" in res["message"]
    assert ts.has_token() is False
