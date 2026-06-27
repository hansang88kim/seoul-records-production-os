"""
providers/suno/playwright_suno_web.py
──────────────────────────────────────
STUB — v0.3 target.

Headless browser automation fallback using Playwright.
If human verification (CAPTCHA / 2FA) appears, stop and require user action.
Never automate CAPTCHA bypass.

Policy:
- Must halt and surface a ManualVerificationRequired exception if
  any human-verification challenge is detected.
- Never commit session cookies or tokens.
"""
from __future__ import annotations

from pathlib import Path
from providers.suno.base import ComposerProvider


class PlaywrightSunoWebProvider(ComposerProvider):
    """TODO v0.3 — browser automation via Playwright."""

    PROVIDER_NAME = "playwright_suno_web"

    def get_capabilities(self) -> dict:
        return {
            "provider": self.PROVIDER_NAME,
            "status": "not_implemented",
            "target_version": "v0.3",
            "note": "Stops if CAPTCHA / 2FA detected. Never bypasses human verification.",
        }

    def create_song(self, title: str, style: str, lyrics: str, options=None) -> str:
        raise NotImplementedError("PlaywrightSunoWebProvider — target: v0.3")

    def get_status(self, task_id: str) -> dict:
        raise NotImplementedError("PlaywrightSunoWebProvider — target: v0.3")

    def download_wav(self, task_id: str, output_path: Path) -> Path:
        raise NotImplementedError("PlaywrightSunoWebProvider — target: v0.3")

    def download_mp3_preview(self, task_id: str, output_path: Path) -> Path | None:
        raise NotImplementedError("PlaywrightSunoWebProvider — target: v0.3")

    def get_metadata(self, task_id: str) -> dict:
        raise NotImplementedError("PlaywrightSunoWebProvider — target: v0.3")
