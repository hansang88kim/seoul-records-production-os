"""
services/remote_control/security.py — chat_id whitelist + enable gating (v0.9.1).

The control plane is DISABLED unless TELEGRAM_BOT_TOKEN and
TELEGRAM_ALLOWED_CHAT_IDS are set. Only whitelisted chat_ids may issue commands;
everything else is rejected and audited. No secret is ever echoed.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from services.security.redaction import redact_text


def _audit_path() -> Path:
    d = Path(__file__).resolve().parent.parent.parent / "outputs" / "remote_control"
    d.mkdir(parents=True, exist_ok=True)
    return d / "command_audit_log.jsonl"


def get_bot_token() -> str | None:
    """Read the bot token from env. Never logged or returned to Telegram."""
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    return tok or None


def get_allowed_chat_ids() -> set[str]:
    """Parse TELEGRAM_ALLOWED_CHAT_IDS (comma-separated) into a set of strings."""
    raw = os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "").strip()
    if not raw:
        return set()
    return {p.strip() for p in raw.split(",") if p.strip()}


def is_control_enabled() -> bool:
    """Control plane is enabled only when BOTH token and whitelist are present."""
    return bool(get_bot_token()) and bool(get_allowed_chat_ids())


def is_chat_allowed(chat_id) -> bool:
    return str(chat_id) in get_allowed_chat_ids()


def audit(chat_id, command: str, allowed: bool, note: str = ""):
    """Append a SANITIZED audit line. Never writes tokens/secrets."""
    import json
    line = json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(),
        "chat_id": str(chat_id),
        "command": redact_text(str(command))[:120],
        "allowed": allowed,
        "note": redact_text(note)[:200],
    }, ensure_ascii=False)
    with _audit_path().open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def public_config_summary() -> dict:
    """
    Non-secret summary for the UI. Shows whether things are enabled and how many
    chat_ids are whitelisted — NEVER the token or the raw chat_ids.
    """
    return {
        "telegram_enabled": is_control_enabled(),
        "has_bot_token": bool(get_bot_token()),
        "allowed_chat_id_count": len(get_allowed_chat_ids()),
    }
