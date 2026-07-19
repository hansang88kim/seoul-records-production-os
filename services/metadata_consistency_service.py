"""
services/metadata_consistency_service.py — Prompt snapshot + metadata consistency.

When the user confirms a prompt (title/style/lyrics/settings), a canonical
snapshot is saved to disk. All subsequent operations reference this snapshot,
not volatile session state.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def compute_prompt_hash(title: str, style: str, lyrics: str, settings: dict | None = None) -> str:
    """Deterministic hash of a prompt for consistency checking."""
    data = f"{title}|{style}|{lyrics}|{json.dumps(settings or {}, sort_keys=True)}"
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def create_prompt_snapshot(
    track_dir: Path,
    title: str,
    style: str,
    lyrics: str,
    settings: dict,
    ai_provider: str = "",
    ai_model: str = "",
) -> dict:
    """
    Save a canonical prompt snapshot to disk.
    This is the source of truth for what the user confirmed.
    """
    track_dir = Path(track_dir)
    track_dir.mkdir(parents=True, exist_ok=True)

    snapshot = {
        "prompt_id": hashlib.sha256(
            f"{datetime.now(timezone.utc).isoformat()}{title}".encode()
        ).hexdigest()[:12],
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
        "title": title,
        "style_prompt": style,
        "lyrics": lyrics,
        "prompt_hash": compute_prompt_hash(title, style, lyrics, settings),
        "model": settings.get("model", "v5"),
        "vocal_gender": settings.get("vocal_gender", "Female"),
        "weirdness": settings.get("weirdness", 35),
        "style_influence": settings.get("style_influence", 70),
        "exclude_styles": settings.get("exclude_styles", []),
        "ai_provider": ai_provider,
        "ai_model": ai_model,
    }

    path = track_dir / "prompt_snapshot.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return snapshot


def load_prompt_snapshot(track_dir: Path) -> dict | None:
    """Load a saved prompt snapshot, or None if missing."""
    path = Path(track_dir) / "prompt_snapshot.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def compare_prompt_snapshot_to_submitted(snapshot: dict, payload: dict) -> list[str]:
    """
    Compare a confirmed prompt snapshot against a submitted payload.
    Returns a list of mismatch descriptions (empty = consistent).
    """
    mismatches = []
    for key, snap_key, pay_key in [
        ("title", "title", "title_sent"),
        ("style", "style_prompt", "tags_sent"),
        ("model", "model", "model_sent"),
        ("vocal", "vocal_gender", "vocal_sent"),
    ]:
        s = str(snapshot.get(snap_key, "")).strip()
        p = str(payload.get(pay_key, "")).strip()
        if s and p and s != p:
            mismatches.append(f"{key}: confirmed='{s[:40]}...' vs sent='{p[:40]}...'")
    return mismatches


def validate_track_metadata_consistency(track_dir: Path) -> dict:
    """
    Validate that a track's metadata is consistent with its prompt snapshot.
    Returns {consistent: bool, issues: [...]}.
    """
    result = {"consistent": True, "issues": []}
    snapshot = load_prompt_snapshot(track_dir)
    if not snapshot:
        result["issues"].append("No prompt_snapshot.json found")
        result["consistent"] = False
        return result

    # Check submitted_payload if exists
    payload_path = Path(track_dir) / "submitted_payload.json"
    if payload_path.exists():
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            mismatches = compare_prompt_snapshot_to_submitted(snapshot, payload)
            if mismatches:
                result["consistent"] = False
                result["issues"].extend(mismatches)
        except Exception as e:
            result["issues"].append(f"Could not read submitted_payload: {e}")

    return result


# ── Security Redaction ───────────────────────────────────────────────────────

_REDACT_PATTERNS = [
    "cookie", "token", "jwt", "session", "authorization",
    "hcaptcha", "api_key", "apikey", "secret",
]


def redact_sensitive(text: str) -> str:
    """
    Redact sensitive values from log text.
    Masks anything that looks like a credential value.
    Cookie/JWT/token values are never shown raw.
    """
    import re
    # Redact Bearer tokens FIRST (before key=value catches "Authorization")
    text = re.sub(r'Bearer\s+\S+', 'Bearer ***', text, flags=re.IGNORECASE)
    # Redact --cookie <value> patterns
    text = re.sub(r'(--cookie\s+)\S+', r'\1***', text, flags=re.IGNORECASE)
    # Redact key=value and key: value patterns
    for pattern in _REDACT_PATTERNS:
        text = re.sub(
            rf'({pattern}\s*[=:]\s*)\S+',
            rf'\1***',
            text,
            flags=re.IGNORECASE,
        )
    return text


def sanitize_command(cmd: list[str]) -> str:
    """
    Convert a command list to a display string with sensitive values masked.
    """
    sanitized = []
    skip_next = False
    for i, arg in enumerate(cmd):
        if skip_next:
            sanitized.append("***")
            skip_next = False
            continue
        lower = arg.lower()
        if any(p in lower for p in ["cookie", "token", "key", "secret"]):
            sanitized.append(arg)
            skip_next = True
        else:
            sanitized.append(arg)
    return " ".join(sanitized)
