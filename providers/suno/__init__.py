"""
providers/suno/__init__.py
──────────────────────────
Central provider registry.
This is the ONLY place where get_composer_provider() is defined.
All workflows must import from here, not from individual provider files.
"""
from __future__ import annotations

from providers.suno.base import ComposerProvider
from providers.suno.mock_suno import MockSunoProvider
from providers.suno.manual_import import ManualImportProvider
from providers.suno.local_unofficial_suno import LocalUnofficialSunoProvider
from providers.suno.playwright_suno_web import PlaywrightSunoWebProvider
from providers.suno.third_party_suno import ThirdPartySunoProvider
from providers.suno.suno_cli_provider import SunoCliProvider


def get_composer_provider(name: str | None = None) -> ComposerProvider:
    """
    Factory function — returns the correct ComposerProvider instance.

    Resolution order:
      1. name argument (from workflow / test override)
      2. COMPOSER_PROVIDER env var
      3. Default: MockSunoProvider

    Valid keys: mock, manual_import, local_unofficial, suno_cli, playwright_web, third_party
    """
    from app.config import COMPOSER_PROVIDER, ALLOW_THIRD_PARTY_SUNO

    key = (name or COMPOSER_PROVIDER or "mock").strip().lower()

    if key == "mock":
        return MockSunoProvider()
    if key in ("manual", "manual_import"):
        return ManualImportProvider()
    if key in ("local", "local_unofficial"):
        return LocalUnofficialSunoProvider()
    if key in ("playwright", "playwright_web"):
        return PlaywrightSunoWebProvider()
    if key in ("suno_cli", "cli"):
        return SunoCliProvider()
    if key == "third_party":
        if not ALLOW_THIRD_PARTY_SUNO:
            raise PermissionError(
                "ThirdPartySunoProvider is disabled. "
                "Set ALLOW_THIRD_PARTY_SUNO=true in .env to enable."
            )
        return ThirdPartySunoProvider()

    raise ValueError(
        f"Unknown composer provider: {key!r}. "
        f"Valid options: mock, manual_import, local_unofficial, suno_cli, playwright_web, third_party"
    )


__all__ = [
    "ComposerProvider",
    "MockSunoProvider",
    "ManualImportProvider",
    "LocalUnofficialSunoProvider",
    "PlaywrightSunoWebProvider",
    "ThirdPartySunoProvider",
    "SunoCliProvider",
    "get_composer_provider",
]
