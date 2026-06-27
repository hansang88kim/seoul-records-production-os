"""
providers/suno/playwright_suno_web.py (v0.3)
─────────────────────────────────────────────
Browser automation fallback using Playwright.

Safety principles:
  - NEVER bypass CAPTCHA / hCaptcha
  - NEVER bypass 2FA / phone verification
  - If human verification detected → stop, return user_action_required
  - Never store session cookies in code or logs
  - browser session path is .gitignore'd

v0.3 scope: skeleton only — returns user_action_required for all generation calls.
Full automation deferred to v0.4.
"""
from __future__ import annotations

import logging
from pathlib import Path

from providers.suno.base import (
    ComposerProvider, ProviderCapabilities, ProviderError, CandidateInfo,
)

logger = logging.getLogger(__name__)


class PlaywrightSunoWebProvider(ComposerProvider):
    """
    Browser automation fallback via Playwright.

    v0.3: skeleton — all generation calls return user_action_required.
    Full implementation: v0.4+.

    Safety:
      - Detects CAPTCHA, hCaptcha, 2FA → stops immediately
      - Never commits cookies/tokens
      - Browser user data dir in .gitignore
    """

    PROVIDER_NAME = "playwright_suno_web"

    # CAPTCHA detection patterns
    _CAPTCHA_MARKERS = [
        "hcaptcha", "h-captcha", "captcha-container",
        "cf-challenge", "turnstile", "recaptcha",
    ]
    _2FA_MARKERS = [
        "two-factor", "2fa", "verification-code",
        "phone-verification", "sms-code",
    ]

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider=self.PROVIDER_NAME,
            status="not_implemented",
            title=True,
            lyrics=True,
            style=True,
            exclude_styles=False,
            vocal_gender=False,
            weirdness=False,
            style_influence=False,
            instrumental=True,
            model_selector=False,
            persona=False,
            two_candidates=True,
            wav_download=True,
            mp3_preview=True,
            supports_polling=False,
            requires_user_session=True,
            note=(
                "v0.3 skeleton — returns user_action_required. "
                "Full automation in v0.4. "
                "Stops immediately if CAPTCHA or 2FA is detected."
            ),
            fallback_instructions=(
                "Use ManualImportProvider: download WAV from suno.com manually, "
                "then import via Song Generation tab."
            ),
        )

    def _check_page_for_verification(self, page_content: str) -> str | None:
        """
        Scan page HTML for CAPTCHA / 2FA markers.
        Returns error status string or None if clean.
        """
        lower = page_content.lower()
        for marker in self._CAPTCHA_MARKERS:
            if marker in lower:
                return "captcha_required"
        for marker in self._2FA_MARKERS:
            if marker in lower:
                return "two_factor_required"
        return None

    def create_song(
        self,
        title: str,
        style: str,
        lyrics: str,
        options: dict | None = None,
    ) -> str:
        """v0.3: Not yet implemented — returns user_action_required."""
        raise ProviderError(
            "manual_import_required",
            "PlaywrightSunoWebProvider is not yet implemented (v0.3 skeleton). "
            "Please use ManualImportProvider: download WAV from suno.com, "
            "then import via the Song Generation tab.",
            {"provider": self.PROVIDER_NAME, "target_version": "v0.4"},
        )

    def get_status(self, task_id: str) -> dict:
        return {
            "status": "manual_import_required",
            "progress": 0,
            "error": "Playwright provider is skeleton-only in v0.3.",
        }

    def download_wav(self, task_id: str, output_path: Path) -> Path:
        raise ProviderError(
            "manual_import_required",
            "WAV download via Playwright not implemented in v0.3.",
        )

    def download_mp3_preview(self, task_id: str, output_path: Path) -> Path | None:
        return None

    def get_metadata(self, task_id: str) -> dict:
        return {
            "provider": self.PROVIDER_NAME,
            "status": "not_implemented",
            "task_id": task_id,
        }
