"""
services/youtube/oauth_service.py — YouTube OAuth 2.0 flow (v0.8.2).

Wraps the OAuth authorization flow. The real flow uses google-auth-oauthlib if
available; in tests (and when libs are absent) it stays fully mockable and
makes no network calls. Secrets are delegated to token_store and never logged.
"""
from __future__ import annotations

from services.youtube import token_store as ts
from services.security.redaction import redact_dict

# YouTube upload scope
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"


def get_auth_status() -> dict:
    """Return the current OAuth status (no secrets)."""
    return ts.get_status()


def client_secret_type_hint(parsed: dict) -> str:
    """
    Warn early when the uploaded JSON is a 'web' application client instead
    of 'installed' (Desktop app). InstalledAppFlow.run_local_server expects
    a loopback redirect URI that Desktop-app clients get automatically;
    Web-application clients usually don't have one registered, which makes
    the browser handshake fail with a redirect_uri_mismatch AFTER the user
    approves access — a confusing "인증 실패" with no obvious cause.
    """
    if "installed" in parsed:
        return ""
    if "web" in parsed:
        return ("⚠️ 이 client_secret.json은 '웹 애플리케이션' 타입입니다. "
                "Google Cloud Console에서 OAuth 클라이언트 ID를 만들 때 "
                "애플리케이션 유형을 반드시 '데스크톱 앱'으로 선택해야 "
                "로컬 인증(run_local_server)이 정상 동작합니다. "
                "데스크톱 앱 타입으로 새로 만들어 다시 업로드하세요.")
    return ""


def load_client_secret_from_bytes(data: bytes) -> bool:
    """Parse an uploaded client_secret.json and store it locally."""
    import json
    try:
        parsed = json.loads(data.decode("utf-8"))
    except Exception:
        ts.set_status(ts.STATUS_FAILED, "client_secret.json 파싱 실패")
        return False
    # Basic shape check (installed/web app client)
    if not ("installed" in parsed or "web" in parsed):
        ts.set_status(ts.STATUS_FAILED, "유효한 OAuth client_secret 형식이 아닙니다")
        return False
    ok = ts.save_client_secret(parsed)
    hint = client_secret_type_hint(parsed)
    if ok and hint:
        # Keep CLIENT_LOADED status (file IS usable-ish) but surface the
        # warning in the message so the UI can show it without a 2nd call.
        ts.set_status(ts.STATUS_CLIENT_LOADED, hint)
    return ok


def _run_flow_local_server(flow, timeout_seconds: float, open_browser: bool = True):
    """
    Run flow.run_local_server(port=0, timeout_seconds=..., open_browser=...)
    and capture whatever it prints to stdout (the fallback "please visit
    this URL" message google-auth-oauthlib prints when it can't be sure
    the browser opened) so we can show that URL directly in the app UI
    on failure.

    v1.0.0-alpha.54 fix (replaces the alpha.53 ThreadPoolExecutor
    wrapper): reading the actual google-auth-oauthlib source confirmed
    run_local_server() has its OWN native `timeout_seconds` parameter that
    aborts the underlying WSGI server's socket wait and raises
    WSGITimeoutError — this is the correct way to bound the wait.

    The alpha.53 wrapper (a ThreadPoolExecutor + future.result(timeout=))
    had a real bug: if the person completed the Google login just a
    little slower than our patience threshold, the background thread's
    run_local_server() would keep running and eventually SUCCEED — but by
    then authorize() had already returned a "실패" status to the caller,
    and that late success was silently discarded (never saved to
    token_store). Someone could finish the real Google login correctly
    and still see "인증 실패". Using the library's own timeout instead
    avoids this entirely: the abort happens inside the same synchronous
    call, so there's no discarded background success.

    open_browser=False is exposed for headless/CI/test environments where
    no browser exists at all — auto-open would otherwise fail with its
    own webbrowser.Error before ever reaching the socket timeout.
    """
    import io
    import contextlib
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            creds = flow.run_local_server(port=0, timeout_seconds=int(timeout_seconds),
                                          open_browser=open_browser)
        return creds
    except Exception as e:
        # Stash whatever was printed (the auth URL, if google-auth-oauthlib
        # got that far) on the exception so authorize() can surface it —
        # this covers Streamlit sessions with no visible console for the
        # printed fallback message to appear in.
        e._captured_stdout = buf.getvalue()
        raise


def _extract_url(text: str) -> str | None:
    import re
    m = re.search(r"https://\S+", text or "")
    return m.group(0) if m else None


def authorize(headless_token: dict | None = None,
             timeout_seconds: float = 120,
             open_browser: bool = True) -> dict:
    """
    Run (or simulate) the OAuth authorization.

    - If headless_token is provided (tests / programmatic), store it directly.
    - Else, attempt the real installed-app flow via google-auth-oauthlib,
      bounded by timeout_seconds (see _run_flow_local_server).
    - open_browser=False skips the automatic browser launch (useful for
      headless environments / testing); production UI leaves it True.
    Returns the resulting status dict (no secrets).
    """
    if not ts.has_client_secret():
        return ts.set_status(ts.STATUS_NOT_CONFIGURED,
                             "먼저 client_secret.json을 업로드하세요")

    if headless_token is not None:
        ts.save_token(headless_token)
        return ts.set_status(ts.STATUS_AUTHORIZED, "인증 완료")

    # Real flow (only if the optional dependency is installed)
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
    except Exception:
        from services.youtube.dependency_check import oauth_install_hint
        hint = oauth_install_hint() or "pip install google-auth-oauthlib google-auth"
        return ts.set_status(ts.STATUS_FAILED, hint)
    try:
        from google_auth_oauthlib.flow import WSGITimeoutError  # type: ignore
    except Exception:
        WSGITimeoutError = ()  # no native timeout support in this version

    try:
        secret = ts.load_client_secret()
        flow = InstalledAppFlow.from_client_config(secret, scopes=[YOUTUBE_UPLOAD_SCOPE])
        creds = _run_flow_local_server(flow, timeout_seconds, open_browser=open_browser)
        token = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes or []),
            "expiry": creds.expiry.isoformat() if getattr(creds, "expiry", None) else None,
        }
        ts.save_token(token)
        return ts.set_status(ts.STATUS_AUTHORIZED, "인증 완료")
    except WSGITimeoutError as e:
        url = _extract_url(getattr(e, "_captured_stdout", ""))
        url_hint = (f" 다음 링크를 브라우저에 직접 열어 로그인을 완료한 뒤 다시 "
                    f"시도하세요: {url}" if url else
                    " 브라우저 창이 자동으로 열리지 않았다면 이 앱을 실행한 "
                    "터미널(cmd/PowerShell)에 출력된 인증 링크를 확인하세요.")
        return ts.set_status(
            ts.STATUS_FAILED,
            f"인증 실패 — {int(timeout_seconds)}초 내에 브라우저 인증이 완료되지 "
            f"않았습니다.{url_hint}")
    except Exception as e:
        # v1.0.0-alpha.54: known bug in older google-auth-oauthlib
        # (googleapis/google-auth-library-python-oauthlib#276) — versions
        # around 1.0.0 raise a bare AttributeError ("'NoneType' object has
        # no attribute 'replace'") instead of WSGITimeoutError in this
        # EXACT same "nothing ever completed the redirect" timeout
        # scenario. Treat it identically so the person still gets the
        # actionable timeout message instead of a confusing internal
        # AttributeError.
        if (isinstance(e, AttributeError) and "replace" in str(e)
                and "NoneType" in str(e)):
            url = _extract_url(getattr(e, "_captured_stdout", ""))
            url_hint = (f" 다음 링크를 브라우저에 직접 열어 로그인을 완료한 뒤 다시 "
                        f"시도하세요: {url}" if url else
                        " 브라우저 창이 자동으로 열리지 않았다면 이 앱을 실행한 "
                        "터미널(cmd/PowerShell)에 출력된 인증 링크를 확인하세요.")
            return ts.set_status(
                ts.STATUS_FAILED,
                f"인증 실패 — {int(timeout_seconds)}초 내에 브라우저 인증이 완료되지 "
                f"않았습니다.{url_hint} (google-auth-oauthlib 구버전에서 알려진 "
                "메시지 표시 문제 — pip install --upgrade google-auth-oauthlib 권장)")

        # v1.0.0-alpha.51 fix: the previous version discarded the real
        # exception and always showed a generic "인증 실패", leaving no way
        # to tell apart a closed browser, a Testing-mode Gmail not added,
        # a wrong client type (web vs. installed), a blocked local port,
        # etc. We now surface the (redacted) exception type + message so
        # the person can actually diagnose it — plus the captured URL
        # (if any was printed before the failure), which is useful even
        # for non-timeout failures.
        from services.security.redaction import redact_text
        detail = redact_text(f"{type(e).__name__}: {e}").strip()[:300]
        url = _extract_url(getattr(e, "_captured_stdout", ""))
        url_part = f" (인증 URL: {url})" if url else ""
        return ts.set_status(ts.STATUS_FAILED, f"인증 실패 — {detail}{url_part}")


def refresh_if_needed() -> dict:
    """
    Refresh the access token if expired and a refresh_token is available.
    No-op in mock mode. Returns status (no secrets).
    """
    if not ts.has_token():
        return ts.set_status(ts.STATUS_NOT_CONFIGURED, "토큰 없음")

    summary = ts.public_token_summary()
    if not summary["has_refresh_token"]:
        return ts.get_status()

    try:
        from google.oauth2.credentials import Credentials  # type: ignore
        from google.auth.transport.requests import Request  # type: ignore
    except Exception:
        # Can't refresh without libs; leave as-is
        return ts.get_status()

    try:
        tok = ts.load_token()
        creds = Credentials(
            token=tok.get("token"),
            refresh_token=tok.get("refresh_token"),
            token_uri=tok.get("token_uri"),
            client_id=tok.get("client_id"),
            client_secret=tok.get("client_secret"),
            scopes=tok.get("scopes"),
        )
        creds.refresh(Request())
        tok["token"] = creds.token
        if getattr(creds, "expiry", None):
            tok["expiry"] = creds.expiry.isoformat()
        ts.save_token(tok)
        return ts.set_status(ts.STATUS_AUTHORIZED, "토큰 갱신 완료")
    except Exception:
        return ts.set_status(ts.STATUS_EXPIRED, "토큰 갱신 필요 — 재인증하세요")


def revoke() -> bool:
    """Clear the local token (does not delete any uploaded video)."""
    return ts.clear_token()


def test_connection() -> dict:
    """
    A non-destructive connection check. In mock mode returns a status based on
    local state without any network call.
    """
    status = ts.get_status()
    if status.get("status") == ts.STATUS_AUTHORIZED:
        return {"ok": True, "message": "인증된 상태입니다 (토큰 존재)"}
    return {"ok": False, "message": "인증되지 않았습니다"}
