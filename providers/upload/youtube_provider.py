"""
YouTubeProvider — uploads videos to YouTube via the YouTube Data API v3.

v0.1: Stub. Creates export package only.
v0.5+: Will perform real private upload via YouTube Data API.

POLICY:
- All uploads must be PRIVATE by default.
- Public release must be done manually outside the app.
- Never change visibility to public automatically.
"""

from __future__ import annotations
import os
import json


class YouTubeProvider:
    """YouTube Data API v3 integration. Not yet implemented for upload."""

    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        refresh_token: str = "",
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token

    def is_authenticated(self) -> bool:
        return bool(self.client_id and self.client_secret and self.refresh_token)

    def upload_private(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list[str],
        thumbnail_path: str,
    ) -> dict:
        """
        Upload video as private to YouTube.

        v0.5+: implement real upload.
        v0.1: raise NotImplementedError.
        """
        # TODO v0.5
        raise NotImplementedError(
            "YouTube upload is not implemented in v0.1. "
            "Use the export package for manual upload."
        )

    def set_thumbnail(self, video_id: str, thumbnail_path: str) -> dict:
        """Set thumbnail for an uploaded video. TODO v0.5."""
        raise NotImplementedError("YouTube thumbnail upload not implemented in v0.1.")

    def get_capabilities(self) -> dict:
        return {
            "provider": "youtube_data_api_v3",
            "available": False,
            "authenticated": self.is_authenticated(),
            "upload_enabled": False,
            "version": "stub_v0.1",
            "notes": "Implement in v0.5",
        }
