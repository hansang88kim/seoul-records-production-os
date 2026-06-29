"""
services/youtube/token_store.py — local OAuth token storage (v0.8.2).

Stores YouTube OAuth tokens and client secrets LOCALLY ONLY under
outputs/youtube_auth/. Raw token contents are never returned for display and
never included in any package/export. Status is tracked separately so the UI
can show progress without ever reading the secret values.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


# OAuth statuses surfaced to the UI (never the token itself)
STATUS_NOT_CONFIGURED = "not_configured"
STATUS_DEPENDENCIES_MISSING = "dependencies_missing"
STATUS_CLIENT_LOADED = "client_secrets_loaded"
STATUS_AUTHORIZED = "authorized"
STATUS_EXPIRED = "token_expired"
STATUS_FAILED = "authorization_failed"


def _auth_dir() -> Path:
    d = Path(__file__).resolve().parent.parent.parent / "outputs" / "youtube_auth"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _token_path() -> Path:
    return _auth_dir() / "token.json"


def _client_secret_path() -> Path:
    return _auth_dir() / "client_secret.json"


def _status_path() -> Path:
    return _auth_dir() / "oauth_status.json"


# ─── Client secret ───────────────────────────────────────────────────────────

def save_client_secret(data: dict) -> bool:
    """Save the uploaded client_secret.json locally. Never shown back raw."""
    try:
        _client_secret_path().parent.mkdir(parents=True, exist_ok=True)
        _client_secret_path().write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8")
        set_status(STATUS_CLIENT_LOADED, "client_secret.json 로드됨")
        return True
    except Exception:
        return False


def has_client_secret() -> bool:
    return _client_secret_path().exists()


def load_client_secret() -> dict | None:
    """Load client secret for internal use only (never returned to the UI)."""
    p = _client_secret_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# ─── Token ───────────────────────────────────────────────────────────────────

def save_token(token: dict) -> bool:
    """Save the OAuth token locally. Contents are never displayed."""
    try:
        _token_path().parent.mkdir(parents=True, exist_ok=True)
        _token_path().write_text(json.dumps(token, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception:
        return False


def has_token() -> bool:
    return _token_path().exists()


def load_token() -> dict | None:
    """Load the token for internal API use only (never returned to the UI)."""
    p = _token_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def clear_token() -> bool:
    """Delete the local token (revoke/clear). Keeps client_secret unless asked."""
    try:
        if _token_path().exists():
            _token_path().unlink()
        set_status(STATUS_CLIENT_LOADED if has_client_secret() else STATUS_NOT_CONFIGURED,
                   "로컬 토큰이 삭제되었습니다")
        return True
    except Exception:
        return False


def clear_all() -> bool:
    """Clear both token and client secret."""
    ok = True
    try:
        if _token_path().exists():
            _token_path().unlink()
        if _client_secret_path().exists():
            _client_secret_path().unlink()
        set_status(STATUS_NOT_CONFIGURED, "인증 정보가 모두 삭제되었습니다")
    except Exception:
        ok = False
    return ok


# ─── Status (safe to display) ────────────────────────────────────────────────

def set_status(status: str, message: str = "") -> dict:
    payload = {
        "status": status,
        "message": message,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _status_path().parent.mkdir(parents=True, exist_ok=True)
    _status_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    return payload


def get_status() -> dict:
    """Return the current OAuth status (no secrets). Safe for the UI."""
    p = _status_path()
    if not p.exists():
        # Infer from what exists on disk
        if has_token():
            return {"status": STATUS_AUTHORIZED, "message": "토큰 존재"}
        if has_client_secret():
            return {"status": STATUS_CLIENT_LOADED, "message": "client_secret 존재"}
        return {"status": STATUS_NOT_CONFIGURED, "message": "설정되지 않음"}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"status": STATUS_NOT_CONFIGURED, "message": ""}


def public_token_summary() -> dict:
    """
    A NON-SECRET summary of the token state for the UI. Never includes the
    actual token/refresh values — only booleans and (optional) expiry.
    """
    tok = load_token() or {}
    return {
        "has_access_token": bool(tok.get("access_token") or tok.get("token")),
        "has_refresh_token": bool(tok.get("refresh_token")),
        "expiry": tok.get("expiry") or tok.get("expires_at") or None,
        "scopes": tok.get("scopes") or tok.get("scope") or None,
    }
