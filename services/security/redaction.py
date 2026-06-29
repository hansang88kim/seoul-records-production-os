"""
services/security/redaction.py — central secret redaction (v0.8.2).

One place to scrub secrets before anything is logged, saved to a manifest, or
shown in the UI. Covers OAuth tokens, client secrets, Authorization/Bearer
headers, and the various provider keys/cookies used across the app.
"""
from __future__ import annotations

import re

REDACTED = "***REDACTED***"

# Field names whose values must never be persisted/shown in raw form.
SECRET_KEYS = {
    "access_token", "refresh_token", "token", "id_token",
    "client_secret", "authorization", "auth", "bearer",
    "api_key", "apikey", "oauth", "oauth_code", "code",
    "token_uri", "cookie", "suno_cookie", "gemini_key",
    "openai_key", "openai_api_key", "canva_token", "password",
    "private_key", "client_email",
}

# Keys we allow to be shown but only partially (e.g. client_id).
PARTIAL_KEYS = {"client_id"}

# Regex patterns for redacting secrets embedded in free text / headers.
_PATTERNS = [
    (re.compile(r"(Authorization\s*:\s*Bearer\s+)\S+", re.IGNORECASE), r"\1" + REDACTED),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), r"\1" + REDACTED),
    (re.compile(r"(access_token[\"'\s:=]+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), r"\1" + REDACTED),
    (re.compile(r"(refresh_token[\"'\s:=]+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), r"\1" + REDACTED),
    (re.compile(r"(client_secret[\"'\s:=]+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), r"\1" + REDACTED),
    (re.compile(r"(ya29\.)[A-Za-z0-9\-._~+/]+=*"), REDACTED),  # Google access tokens
    (re.compile(r"(ghp_)[A-Za-z0-9]+"), REDACTED),             # GitHub PATs
]


def _partial(value: str) -> str:
    """Show only the first 4 and last 2 chars of a non-secret-but-sensitive id."""
    s = str(value)
    if len(s) <= 8:
        return REDACTED
    return f"{s[:4]}...{s[-2:]}"


def redact_text(text: str) -> str:
    """Redact secrets that appear inside a free-text string or header blob."""
    if not text:
        return text
    out = str(text)
    for pat, repl in _PATTERNS:
        out = pat.sub(repl, out)
    return out


def redact_headers(headers: dict) -> dict:
    """Mask Authorization (and any token-like) header values."""
    safe = {}
    for k, v in (headers or {}).items():
        if k.lower() in ("authorization", "x-goog-api-key", "cookie"):
            safe[k] = REDACTED
        else:
            safe[k] = v
    return safe


def redact_dict(data):
    """
    Recursively scrub a dict/list of secrets. Secret keys → REDACTED, partial
    keys → masked, nested structures handled. Strings are pattern-redacted.
    """
    if isinstance(data, dict):
        safe = {}
        for k, v in data.items():
            kl = str(k).lower()
            if kl in SECRET_KEYS:
                safe[k] = REDACTED
            elif kl in PARTIAL_KEYS:
                safe[k] = _partial(v) if v else v
            else:
                safe[k] = redact_dict(v)
        return safe
    elif isinstance(data, list):
        return [redact_dict(x) for x in data]
    elif isinstance(data, str):
        return redact_text(data)
    else:
        return data


def assert_no_secrets(text: str) -> bool:
    """
    Return True if the text appears free of obvious raw secrets. Used in tests
    and as a defensive check before writing logs.
    """
    if not text:
        return True
    markers = ["ya29.", "ghp_", "refresh_token\":", "access_token\":", "client_secret\":"]
    low = text
    for m in markers:
        if m in low and REDACTED not in low:
            return False
    return True
