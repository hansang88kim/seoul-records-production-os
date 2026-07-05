"""
tests/test_youtube_oauth_timeout_v053.py — v1.0.0-alpha.53, replaced in alpha.54.

Root cause targeted here: InstalledAppFlow.run_local_server() blocks
FOREVER waiting for the OAuth browser redirect. In a Streamlit app, if the
browser doesn't auto-open (headless/remote session, popup blocked, no
default browser) or the person never finishes the Google login, clicking
"🔑 YouTube 인증" just hangs with NO error and NO timeout — which looks
exactly like "인증이 안 됨" with zero diagnostic signal.

alpha.54 fix: after reading the real google-auth-oauthlib source, its
run_local_server() has a NATIVE `timeout_seconds` parameter (raises
WSGITimeoutError via the underlying WSGI server's socket timeout). This
replaces the alpha.53 ThreadPoolExecutor-based wrapper, which had a real
bug: if the person finished Google login just a bit slower than our
patience threshold, the background thread's run_local_server() would
still succeed, but authorize() had ALREADY returned a "실패" status and
silently discarded that late success (never saved to token_store) — a
successful login could be thrown away and reported as a failure. Using
the library's own timeout avoids this: the abort happens synchronously
inside the same call, so there's no discarded background success.

Additionally: run_local_server() prints a fallback "please visit this
URL" message via plain `print()` when it can't be sure the browser
auto-opened. If the Streamlit process has no visible console (launched
via a shortcut/pythonw), that message is invisible. We now capture stdout
during the call and, on failure, extract that URL into the status
message shown directly in the app UI.
"""
from __future__ import annotations

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


class _FakeWSGITimeoutError(Exception):
    """Stands in for google_auth_oauthlib.flow.WSGITimeoutError in tests."""


class _TimeoutFlow:
    """
    Simulates a browser that never completes the OAuth redirect within
    the given timeout_seconds — exactly what the real WSGI server's
    socket timeout does. Also prints the same kind of fallback message
    the real library prints, so we can test URL extraction.
    """
    printed_url = "https://accounts.google.com/o/oauth2/auth?client_id=fake&state=abc"

    @staticmethod
    def from_client_config(*a, **k):
        return _TimeoutFlow()

    def run_local_server(self, port=0, timeout_seconds=None, **kwargs):
        print(f"Please visit this URL to authorize: {self.printed_url}")
        raise _FakeWSGITimeoutError("Timed out waiting for response "
                                    "from authorization server")


class _FastFlow:
    """Simulates a browser that completes the flow almost instantly."""
    @staticmethod
    def from_client_config(*a, **k):
        return _FastFlow()

    def run_local_server(self, port=0, timeout_seconds=None, **kwargs):
        class _Creds:
            token = "tok"
            refresh_token = "rtok"
            token_uri = "https://oauth2"
            client_id = "x"
            client_secret = "y"
            scopes = ["scope"]
            expiry = None
        return _Creds()


class _OtherErrorFlow:
    """Simulates a non-timeout failure (e.g. redirect_uri_mismatch)."""
    @staticmethod
    def from_client_config(*a, **k):
        return _OtherErrorFlow()

    def run_local_server(self, port=0, timeout_seconds=None, **kwargs):
        raise RuntimeError("redirect_uri_mismatch")


def _patch_flow(monkeypatch, flow_cls, wsgi_timeout_error=_FakeWSGITimeoutError):
    fake_module = type("m", (), {
        "InstalledAppFlow": flow_cls,
        "WSGITimeoutError": wsgi_timeout_error,
    })
    monkeypatch.setitem(__import__("sys").modules,
                        "google_auth_oauthlib.flow", fake_module)


def test_authorize_times_out_via_library_native_timeout(monkeypatch):
    from services.youtube import oauth_service as oauth
    from services.youtube import token_store as ts

    _upload_installed_secret()
    _patch_flow(monkeypatch, _TimeoutFlow)

    res = oauth.authorize(timeout_seconds=1)
    assert res["status"] == ts.STATUS_FAILED
    assert "시간" in res["message"] or "초" in res["message"]
    # No token should have been saved — nothing succeeded.
    assert ts.has_token() is False


def test_authorize_timeout_message_includes_captured_url(monkeypatch):
    """The URL that run_local_server printed to stdout must appear in the
    failure message — this is what makes the failure actionable even
    when the Streamlit process has no visible console."""
    from services.youtube import oauth_service as oauth
    _upload_installed_secret()
    _patch_flow(monkeypatch, _TimeoutFlow)
    res = oauth.authorize(timeout_seconds=1)
    assert _TimeoutFlow.printed_url in res["message"]


def test_authorize_succeeds_quickly_when_flow_completes_fast(monkeypatch):
    from services.youtube import oauth_service as oauth
    from services.youtube import token_store as ts
    _upload_installed_secret()
    _patch_flow(monkeypatch, _FastFlow)

    res = oauth.authorize(timeout_seconds=5)
    assert res["status"] == ts.STATUS_AUTHORIZED
    assert ts.has_token() is True


def test_non_timeout_failure_still_uses_generic_redacted_handler(monkeypatch):
    """A non-timeout exception (e.g. redirect_uri_mismatch) must NOT be
    swallowed by the timeout branch — it goes through the existing
    generic (redacted) error handler from alpha.51."""
    from services.youtube import oauth_service as oauth
    from services.youtube import token_store as ts
    _upload_installed_secret()
    _patch_flow(monkeypatch, _OtherErrorFlow)

    res = oauth.authorize(timeout_seconds=5)
    assert res["status"] == ts.STATUS_FAILED
    assert "RuntimeError" in res["message"]
    assert "redirect_uri_mismatch" in res["message"]


def test_no_dangling_thread_or_lost_success_on_slow_but_eventual_login():
    """
    Regression test for the alpha.53 bug: with the OLD ThreadPoolExecutor
    wrapper, a flow that succeeds slightly after the timeout would still
    silently save nothing (the late success was discarded). With the
    library-native timeout, the abort is synchronous — there is no
    "eventually succeeds in the background" case at all: either
    run_local_server() returns within timeout_seconds, or it raises
    WSGITimeoutError, full stop. This test documents that contract by
    asserting authorize() has no thread/executor machinery left.
    """
    import inspect
    from services.youtube import oauth_service as oauth
    src = inspect.getsource(oauth)
    # The docstring mentions "ThreadPoolExecutor" historically (explaining
    # why it was removed) — what matters is that it's no longer USED.
    assert "ThreadPoolExecutor(" not in src
    assert "concurrent.futures.TimeoutError" not in src


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


def test_missing_native_timeout_support_falls_back_to_generic_handler(monkeypatch):
    """
    Older google-auth-oauthlib versions may not export WSGITimeoutError.
    authorize() must degrade gracefully (generic redacted error) rather
    than crashing with an ImportError/AttributeError of its own.
    """
    from services.youtube import oauth_service as oauth
    from services.youtube import token_store as ts
    _upload_installed_secret()

    class _NoTimeoutSupportFlow:
        @staticmethod
        def from_client_config(*a, **k):
            return _NoTimeoutSupportFlow()

        def run_local_server(self, port=0, **kwargs):
            # Old-style signature: no timeout_seconds kwarg accepted at all.
            raise TypeError("run_local_server() got an unexpected keyword "
                            "argument 'timeout_seconds'")

    # Simulate a module with NO WSGITimeoutError attribute at all.
    fake_module = type("m", (), {"InstalledAppFlow": _NoTimeoutSupportFlow})
    monkeypatch.setitem(__import__("sys").modules,
                        "google_auth_oauthlib.flow", fake_module)

    res = oauth.authorize(timeout_seconds=5)
    assert res["status"] == ts.STATUS_FAILED
    assert "TypeError" in res["message"]


def test_known_old_library_attributeerror_bug_is_treated_as_timeout(monkeypatch):
    """
    Real-world bug (googleapis/google-auth-library-python-oauthlib#276):
    google-auth-oauthlib ~1.0.0 raises a bare
    "'NoneType' object has no attribute 'replace'" AttributeError instead
    of WSGITimeoutError when nothing ever completed the redirect before
    the timeout. We must recognize this specific pattern and give the
    same actionable timeout message, not a confusing raw AttributeError.
    """
    from services.youtube import oauth_service as oauth
    from services.youtube import token_store as ts
    _upload_installed_secret()

    class _OldBuggyTimeoutFlow:
        @staticmethod
        def from_client_config(*a, **k):
            return _OldBuggyTimeoutFlow()

        def run_local_server(self, port=0, timeout_seconds=None, **kwargs):
            print("Please visit this URL to authorize: "
                  "https://accounts.google.com/o/oauth2/auth?client_id=old")
            raise AttributeError("'NoneType' object has no attribute 'replace'")

    fake_module = type("m", (), {"InstalledAppFlow": _OldBuggyTimeoutFlow})
    # No WSGITimeoutError attribute at all on this fake old module.
    monkeypatch.setitem(__import__("sys").modules,
                        "google_auth_oauthlib.flow", fake_module)

    res = oauth.authorize(timeout_seconds=3)
    assert res["status"] == ts.STATUS_FAILED
    assert "초" in res["message"]  # timeout-style wording, not raw AttributeError
    assert "accounts.google.com" in res["message"]  # captured URL surfaced too
