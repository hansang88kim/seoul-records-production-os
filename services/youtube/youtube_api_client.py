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

# ─── v0.8.2: central redaction delegation + client factory ──────────────────

def redact_authorization_header_v2(headers: dict) -> dict:
    """Delegate to the central redaction utility (covers more header types)."""
    from services.security.redaction import redact_headers
    return redact_headers(headers)


def sanitize_for_log_v2(data):
    """Delegate to the central redaction utility (recursive, pattern-based)."""
    from services.security.redaction import redact_dict
    return redact_dict(data)


class RealYouTubeApiClient:
    """
    Real YouTube Data API client (resumable upload). Requires the optional
    google-api-python-client + google-auth libraries AND a valid local token.
    If the libraries are missing, methods raise a clear error; the app falls
    back to the mock client. NEVER logs tokens or Authorization headers.
    """

    def __init__(self, credentials: dict | None = None):
        self._credentials = credentials or {}
        self.calls = []

    def _build_service(self):
        from googleapiclient.discovery import build  # type: ignore
        from google.oauth2.credentials import Credentials  # type: ignore
        tok = self._credentials
        creds = Credentials(
            token=tok.get("token"),
            refresh_token=tok.get("refresh_token"),
            token_uri=tok.get("token_uri"),
            client_id=tok.get("client_id"),
            client_secret=tok.get("client_secret"),
            scopes=tok.get("scopes"),
        )
        return build("youtube", "v3", credentials=creds)

    def authenticate(self) -> dict:
        # Auth handled by oauth_service; here we just verify creds are present.
        return {"ok": bool(self._credentials), "mock": False}

    def get_auth_status(self) -> dict:
        return {"status": "authorized" if self._credentials else "not_configured",
                "mock": False}

    def upload_video_private(self, payload: dict, video_path: str,
                             progress_callback=None) -> dict:
        """
        Resumable private upload via the real API. privacyStatus is forced to
        whatever the payload says (default private upstream). Never publishes
        public on its own.
        """
        from googleapiclient.http import MediaFileUpload  # type: ignore
        service = self._build_service()
        media = MediaFileUpload(video_path, chunksize=1024 * 1024 * 8,
                                resumable=True)
        request = service.videos().insert(
            part="snippet,status", body=payload, media_body=media)

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status and progress_callback:
                progress_callback({
                    "percent": int(status.progress() * 100),
                    "bytes_uploaded": int(status.resumable_progress),
                    "total_bytes": int(status.total_size or 0),
                    "speed": "",
                })
        vid = response.get("id")
        privacy = payload.get("status", {}).get("privacyStatus", "private")
        return {"status": "uploaded", "video_id": vid,
                "youtube_url": f"https://youtu.be/{vid}",
                "privacy_status": privacy, "mock": False}

    def set_thumbnail(self, video_id: str, thumbnail_path: str) -> dict:
        from googleapiclient.http import MediaFileUpload  # type: ignore
        service = self._build_service()
        try:
            service.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path)).execute()
            return {"thumbnail_set": True, "video_id": video_id, "mock": False}
        except Exception as e:
            # v1.0.0-alpha.55 fix: this used to swallow the real exception
            # entirely and always return the generic "thumbnail set
            # failed" — giving no way to tell a file-size/format problem
            # apart from the classic (and very common) real cause: a
            # YouTube channel that hasn't completed phone/channel
            # verification cannot set custom thumbnails AT ALL, via the
            # API or the website, even when the image file itself is
            # perfectly valid. We now surface the actual HTTP status +
            # message from YouTube's error body, and add a specific hint
            # when the message matches that known pattern.
            from services.security.redaction import redact_text
            status = None
            reason = ""
            try:
                from googleapiclient.errors import HttpError  # type: ignore
                if isinstance(e, HttpError):
                    status = getattr(e.resp, "status", None)
                    reason = str(e.reason or "")
            except Exception:
                pass
            reason = redact_text(reason or f"{type(e).__name__}: {e}").strip()[:300]

            hint = ""
            low = reason.lower()
            if (status == 403 and
                    any(k in low for k in ("thumbnail", "eligib", "verif"))):
                hint = (" — YouTube는 채널 인증(전화번호 인증)이 완료되지 않은 "
                        "채널은 API로도 커스텀 썸네일 설정을 막습니다. YouTube "
                        "Studio → 설정 → 채널 → 채널 상태 및 기능에서 전화번호 "
                        "인증을 완료한 뒤 '썸네일만 재시도'를 눌러주세요.")

            detail = f"HTTP {status}: {reason}" if status else reason
            return {"thumbnail_set": False, "video_id": video_id,
                    "error": f"{detail}{hint}", "mock": False}

    def get_video_status(self, video_id: str) -> dict:
        service = self._build_service()
        resp = service.videos().list(part="status", id=video_id).execute()
        items = resp.get("items", [])
        status = items[0].get("status", {}) if items else {}
        return {"video_id": video_id,
                "privacy_status": status.get("privacyStatus"),
                "upload_status": status.get("uploadStatus"), "mock": False}

    def revoke_token(self) -> dict:
        from services.youtube import token_store as ts
        ts.clear_token()
        return {"revoked": True, "mock": False}


def get_youtube_client(use_mock: bool = True, credentials: dict | None = None,
                       **mock_kwargs):
    """
    Factory: returns the mock client by default (no network). Pass
    use_mock=False to get the real client (requires libs + token). Tests always
    use the mock.
    """
    if use_mock:
        from services.youtube.mock_youtube_api_client import MockYouTubeApiClient
        return MockYouTubeApiClient(credentials=credentials, **mock_kwargs)
    return RealYouTubeApiClient(credentials=credentials)
