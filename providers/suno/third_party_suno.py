"""
providers/suno/third_party_suno.py
────────────────────────────────────
STUB — not a recommended provider.

Third-party paid Suno API wrappers (e.g. sunoapi.org) are NOT the default
and must be explicitly enabled via ALLOW_THIRD_PARTY_SUNO=true.

Policy:
- Disabled by default.
- Never commit third-party API keys.
- The intended default is LocalUnofficialSunoProvider using the user's
  own Suno account credits.
"""
from __future__ import annotations

from pathlib import Path
from providers.suno.base import ComposerProvider


class ThirdPartySunoProvider(ComposerProvider):
    """
    NOT the default provider.
    Requires ALLOW_THIRD_PARTY_SUNO=true in .env.
    TODO v0.3.
    """

    PROVIDER_NAME = "third_party_suno"

    def get_capabilities(self):
        from providers.suno.base import ProviderCapabilities
        return ProviderCapabilities(
            provider=self.PROVIDER_NAME,
            status="not_implemented",
            title=True, lyrics=True, style=True,
            exclude_styles=True, vocal_gender=True,
            weirdness=True, style_influence=True,
            instrumental=True, model_selector=True, persona=True,
            two_candidates=True, wav_download=True, mp3_preview=True,
            supports_polling=True,
            requires_api_key=True,
            note="Paid third-party. NOT default. Requires ALLOW_THIRD_PARTY_SUNO=true.",
        )

    def create_song(self, title: str, style: str, lyrics: str, options=None) -> str:
        raise NotImplementedError("ThirdPartySunoProvider — not permitted by default.")

    def get_status(self, task_id: str) -> dict:
        raise NotImplementedError("ThirdPartySunoProvider — not permitted by default.")

    def download_wav(self, task_id: str, output_path: Path) -> Path:
        raise NotImplementedError("ThirdPartySunoProvider — not permitted by default.")

    def download_mp3_preview(self, task_id: str, output_path: Path) -> Path | None:
        raise NotImplementedError("ThirdPartySunoProvider — not permitted by default.")

    def get_metadata(self, task_id: str) -> dict:
        raise NotImplementedError("ThirdPartySunoProvider — not permitted by default.")
