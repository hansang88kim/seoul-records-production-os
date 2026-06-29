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
    return ts.save_client_secret(parsed)


def authorize(headless_token: dict | None = None) -> dict:
    """
    Run (or simulate) the OAuth authorization.

    - If headless_token is provided (tests / programmatic), store it directly.
    - Else, attempt the real installed-app flow via google-auth-oauthlib.
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
        return ts.set_status(
            ts.STATUS_FAILED,
            "google-auth-oauthlib 미설치 — 실제 인증을 진행할 수 없습니다. "
            "라이브러리를 설치하거나 수동 패키지 모드를 사용하세요.",
        )

    try:
        secret = ts.load_client_secret()
        flow = InstalledAppFlow.from_client_config(secret, scopes=[YOUTUBE_UPLOAD_SCOPE])
        creds = flow.run_local_server(port=0)
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
    except Exception as e:
        # Never include token material in the message
        return ts.set_status(ts.STATUS_FAILED, "인증 실패")


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
