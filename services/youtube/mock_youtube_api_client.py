"""
services/youtube/mock_youtube_api_client.py — mock client (v0.8.2).

A drop-in YouTube client that makes NO network calls. Used in tests and as the
default fallback. Implements the same interface as the real client:
  authenticate / get_auth_status / upload_video_private / set_thumbnail /
  get_video_status / revoke_token.

It can be configured to simulate a thumbnail-set failure so partial_success
paths can be tested.
"""
from __future__ import annotations

from datetime import datetime, timezone


class MockYouTubeApiClient:
    def __init__(self, credentials: dict | None = None,
                 fail_thumbnail: bool = False,
                 fail_upload: bool = False,
                 raise_upload: Exception | None = None):
        self._credentials = credentials or {}
        self.fail_thumbnail = fail_thumbnail
        self.fail_upload = fail_upload
        self.raise_upload = raise_upload
        self.calls = []  # sanitized record (never secrets)

    def authenticate(self) -> dict:
        self.calls.append(("authenticate", {}))
        return {"ok": True, "mock": True}

    def get_auth_status(self) -> dict:
        return {"status": "authorized", "mock": True}

    def upload_video_private(self, payload: dict, video_path: str,
                             progress_callback=None) -> dict:
        """
        Simulate a resumable private upload. Calls progress_callback with a few
        steps so the worker's progress plumbing can be exercised.
        """
        self.calls.append(("upload_video_private", {
            "video_path": video_path,
            "privacy_status": payload.get("status", {}).get("privacyStatus", "private"),
            "title": payload.get("snippet", {}).get("title", ""),
        }))

        if getattr(self, "raise_upload", None):
            # Simulate a real thrown exception (e.g. an OAuth RefreshError
            # / invalid_grant) so the worker's except-branch is exercised.
            raise self.raise_upload

        if self.fail_upload:
            return {"status": "failed", "video_id": None,
                    "errors": ["mock upload failure"], "mock": True}

        # Simulate progress 0 → 100
        if progress_callback:
            for pct, sent in [(25, 250), (50, 500), (75, 750), (100, 1000)]:
                progress_callback({"percent": pct, "bytes_uploaded": sent,
                                   "total_bytes": 1000, "speed": "1.0MB/s"})

        fake_id = "MOCK_" + datetime.now(timezone.utc).strftime("%H%M%S%f")[:-3]
        privacy = payload.get("status", {}).get("privacyStatus", "private")
        return {
            "status": "uploaded",
            "video_id": fake_id,
            "youtube_url": f"https://youtu.be/{fake_id}",
            "privacy_status": privacy,
            "mock": True,
        }

    def set_thumbnail(self, video_id: str, thumbnail_path: str) -> dict:
        self.calls.append(("set_thumbnail", {
            "video_id": video_id, "thumbnail_path": thumbnail_path,
        }))
        if self.fail_thumbnail:
            return {"thumbnail_set": False, "video_id": video_id,
                    "error": "mock thumbnail failure", "mock": True}
        return {"thumbnail_set": True, "video_id": video_id, "mock": True}

    def get_video_status(self, video_id: str) -> dict:
        self.calls.append(("get_video_status", {"video_id": video_id}))
        return {"video_id": video_id, "privacy_status": "private",
                "upload_status": "processed", "mock": True}

    def revoke_token(self) -> dict:
        self.calls.append(("revoke_token", {}))
        return {"revoked": True, "mock": True}
