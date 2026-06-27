"""
providers/suno/local_unofficial_suno.py
────────────────────────────────────────
STUB — v0.3 target.

Wraps a locally-running unofficial Suno API server
(e.g. https://github.com/SunoAI-API/Suno-API or similar).

The local server uses the user's own Suno account session cookie.
It must be running on SUNO_LOCAL_API_BASE_URL before this provider is used.

Policy:
- Never commit SUNO_COOKIE to version control.
- If the local server is unreachable, raise a clear error.
- Prefer WAV download over MP3.
"""
from __future__ import annotations

from pathlib import Path
from providers.suno.base import ComposerProvider


class LocalUnofficialSunoProvider(ComposerProvider):
    """TODO v0.3 — connects to local unofficial Suno API wrapper."""

    PROVIDER_NAME = "local_unofficial_suno"

    def get_capabilities(self) -> dict:
        return {
            "provider": self.PROVIDER_NAME,
            "status": "not_implemented",
            "target_version": "v0.3",
        }

    def create_song(self, title: str, style: str, lyrics: str, options=None) -> str:
        raise NotImplementedError("LocalUnofficialSunoProvider — target: v0.3")

    def get_status(self, task_id: str) -> dict:
        raise NotImplementedError("LocalUnofficialSunoProvider — target: v0.3")

    def download_wav(self, task_id: str, output_path: Path) -> Path:
        raise NotImplementedError("LocalUnofficialSunoProvider — target: v0.3")

    def download_mp3_preview(self, task_id: str, output_path: Path) -> Path | None:
        raise NotImplementedError("LocalUnofficialSunoProvider — target: v0.3")

    def get_metadata(self, task_id: str) -> dict:
        raise NotImplementedError("LocalUnofficialSunoProvider — target: v0.3")
