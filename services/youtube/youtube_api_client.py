"""
services/youtube/youtube_api_client.py — YouTube upload client (v0.8.0).

Designed for OAuth 2.0 upload, but the real network upload is deferred (likely
v0.8.1). This module provides:
  - a MOCK client used in tests and by default (no network)
  - strict secret handling: OAuth tokens / Authorization headers are NEVER
    logged or written to disk in raw form — only redacted.

SECURITY RULES (enforced here):
  - redact_authorization_header() masks any bearer token.
  - sanitize_for_log() strips token/key fields before anything is logged.
  - upload private by default; never auto-publish public.
  - never delete local files.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


REDACTED = "***REDACTED***"


def redact_authorization_header(headers: dict) -> dict:
    """Return a copy of headers with any Authorization value masked."""
    safe = dict(headers or {})
    for k in list(safe.keys()):
        if k.lower() == "authorization":
            safe[k] = REDACTED
    return safe


def sanitize_for_log(data: dict) -> dict:
    """Strip secret-bearing fields from a dict before logging/saving."""
    SECRET_KEYS = {
        "access_token", "refresh_token", "token", "api_key", "apikey",
        "client_secret", "authorization", "auth", "bearer",
    }
    safe = {}
    for k, v in (data or {}).items():
        if k.lower() in SECRET_KEYS:
            safe[k] = REDACTED
        elif isinstance(v, dict):
            safe[k] = sanitize_for_log(v)
        else:
            safe[k] = v
    return safe


class MockYouTubeClient:
    """
    A mock YouTube client. Makes NO network calls. Used in tests and as the
    default so the package flow can be exercised without OAuth.
    """

    def __init__(self, credentials: dict | None = None):
        # Credentials are held in memory only; never written to disk raw.
        self._credentials = credentials or {}
        self.calls = []  # record of (method, sanitized args)

    def upload_video(self, video_path: str, payload: dict,
                     privacy_status: str = "private") -> dict:
        """
        Pretend to upload a video. Returns a mock result with a fake video_id.
        Never publishes public unless explicitly asked (and even then this is
        a mock that performs no real action).
        """
        # Record the call WITHOUT secrets
        self.calls.append(("upload_video", {
            "video_path": video_path,
            "privacy_status": privacy_status,
            "title": payload.get("snippet", {}).get("title", ""),
        }))
        fake_id = "MOCK_" + datetime.now(timezone.utc).strftime("%H%M%S")
        return {
            "video_id": fake_id,
            "url": f"https://youtu.be/{fake_id}",
            "privacy_status": privacy_status,
            "mock": True,
        }

    def set_thumbnail(self, video_id: str, thumbnail_path: str) -> dict:
        """Pretend to set a thumbnail after the video_id is known."""
        self.calls.append(("set_thumbnail", {
            "video_id": video_id, "thumbnail_path": thumbnail_path,
        }))
        return {"video_id": video_id, "thumbnail_set": True, "mock": True}


def save_upload_result(out_dir: str, result: dict) -> str:
    """
    Persist upload_result.json. The result is sanitized first so no token can
    leak into the file.
    """
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    safe = sanitize_for_log(result)
    path = d / "upload_result.json"
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def get_unverified_project_note() -> str:
    """A UI/docs note about unverified-project upload restrictions."""
    return (
        "참고: YouTube API 프로젝트가 인증(verification)되지 않은 경우, "
        "업로드된 영상은 비공개(private)로 제한될 수 있습니다. 공개 전환은 "
        "프로젝트 인증 이후 가능합니다."
    )
