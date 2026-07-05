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


def _run_local_server_with_timeout(flow, timeout_seconds: float):
    """
    Run flow.run_local_server(port=0) with a hard wall-clock timeout.

    v1.0.0-alpha.53 fix: InstalledAppFlow.run_local_server() blocks
    forever waiting for the OAuth redirect. In a Streamlit app this means
    that if the browser doesn't auto-open (headless/remote session, no
    default browser configured, popup blocked) or the person closes the
    tab without finishing login, clicking "🔑 YouTube 인증" just hangs —
    no error, no timeout, nothing — which looks EXACTLY like "인증이 안
    됨" with zero diagnostic signal. This wraps the blocking call in a
    worker thread and gives up after `timeout_seconds`, raising
    TimeoutError so authorize() can show a clear, actionable message
    instead of hanging silently.

    Note: the worker thread itself cannot be forcibly killed (Python has
    no safe thread-kill); it keeps listening on its OS-assigned port
    until the browser eventually hits it or the process exits. That's
    harmless — port=0 means a fresh random port is used on each retry.
    """
    import concurrent.futures
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(flow.run_local_server, port=0)
    try:
        return future.result(timeout=timeout_seconds)
    except concurrent.futures.TimeoutError:
        raise TimeoutError(
            f"{int(timeout_seconds)}초 내에 브라우저 인증이 완료되지 않았습니다")


def authorize(headless_token: dict | None = None,
             timeout_seconds: float = 120) -> dict:
    """
    Run (or simulate) the OAuth authorization.

    - If headless_token is provided (tests / programmatic), store it directly.
    - Else, attempt the real installed-app flow via google-auth-oauthlib,
      bounded by timeout_seconds (see _run_local_server_with_timeout).
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
        secret = ts.load_client_secret()
        flow = InstalledAppFlow.from_client_config(secret, scopes=[YOUTUBE_UPLOAD_SCOPE])
        creds = _run_local_server_with_timeout(flow, timeout_seconds)
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
    except TimeoutError as e:
        return ts.set_status(
            ts.STATUS_FAILED,
            f"인증 실패 — {e}. 클릭 시 자동으로 열리는 브라우저 창에서 Google 로그인을 "
            "완료해야 합니다. 브라우저가 자동으로 열리지 않았다면, 이 앱을 실행한 "
            "터미널(cmd/PowerShell) 창에 출력된 인증 URL을 복사해 브라우저 주소창에 "
            "직접 붙여넣고 로그인을 완료한 뒤 다시 시도하세요.")
    except Exception as e:
        # v1.0.0-alpha.51 fix: the previous version discarded the real
        # exception and always showed a generic "인증 실패", leaving no way
        # to tell apart a closed browser, a Testing-mode Gmail not added,
        # a wrong client type (web vs. installed), a blocked local port,
        # etc. We now surface the (redacted) exception type + message so
        # the person can actually diagnose it.
        from services.security.redaction import redact_text
        detail = redact_text(f"{type(e).__name__}: {e}").strip()[:300]
        return ts.set_status(ts.STATUS_FAILED, f"인증 실패 — {detail}")


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
