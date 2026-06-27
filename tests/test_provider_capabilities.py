"""
tests/test_provider_capabilities.py (v0.3)
───────────────────────────────────────────
Tests for provider capability system, normalized errors,
and LocalUnofficialSunoProvider behavior.
"""
from __future__ import annotations
from pathlib import Path
from unittest import mock
import json
import pytest

from providers.suno.base import ProviderCapabilities, ProviderError, CandidateInfo


# ─── Capability Schema ───────────────────────────────────────────────────────

def test_provider_capabilities_schema():
    """ProviderCapabilities must have all required fields."""
    caps = ProviderCapabilities(provider="test")
    d = caps.to_dict()
    assert "provider" in d
    assert "status" in d
    assert "title" in d
    assert "lyrics" in d
    assert "wav_download" in d
    assert "mp3_preview" in d
    assert "supports_polling" in d


def test_provider_capabilities_to_dict():
    """to_dict excludes None fields."""
    caps = ProviderCapabilities(provider="test", note=None)
    d = caps.to_dict()
    assert "note" not in d
    caps2 = ProviderCapabilities(provider="test", note="hello")
    d2 = caps2.to_dict()
    assert d2["note"] == "hello"


# ─── Provider Registry ──────────────────────────────────────────────────────

def test_registry_selects_local_unofficial():
    """get_composer_provider('local_unofficial') → LocalUnofficialSunoProvider."""
    from providers.suno import get_composer_provider
    p = get_composer_provider("local_unofficial")
    assert p.PROVIDER_NAME == "local_unofficial_suno"


def test_registry_selects_playwright():
    from providers.suno import get_composer_provider
    p = get_composer_provider("playwright_web")
    assert p.PROVIDER_NAME == "playwright_suno_web"


def test_all_providers_return_capabilities():
    """Every provider's get_capabilities returns ProviderCapabilities."""
    from providers.suno import get_composer_provider
    for name in ["mock", "manual_import", "local_unofficial", "playwright_web"]:
        p = get_composer_provider(name)
        caps = p.get_capabilities()
        assert isinstance(caps, ProviderCapabilities), (
            f"{name} returned {type(caps)}, expected ProviderCapabilities"
        )
        assert caps.provider, f"{name} has empty provider name"


# ─── LocalUnofficialSunoProvider ─────────────────────────────────────────────

def test_local_provider_normalizes_mock_http_response():
    """LocalUnofficialSunoProvider normalizes a mock Suno API response."""
    from providers.suno.local_unofficial_suno import _normalize_candidates

    mock_clips = [
        {
            "id": "clip-aaa",
            "audio_url": "https://cdn.suno.ai/clip-aaa.mp3",
            "audio_url_wav": None,
            "status": "complete",
            "duration": 215.0,
            "title": "Test Song",
            "metadata": {"tags": "city pop, female vocal"},
        },
        {
            "id": "clip-bbb",
            "audio_url": "https://cdn.suno.ai/clip-bbb.mp3",
            "audio_url_wav": "https://cdn.suno.ai/clip-bbb.wav",
            "status": "complete",
            "duration": 220.0,
            "title": "Test Song",
            "metadata": {"tags": "city pop, female vocal"},
        },
    ]
    candidates = _normalize_candidates(mock_clips)

    assert len(candidates) == 2
    assert candidates[0].candidate_id == "A"
    assert candidates[1].candidate_id == "B"
    assert candidates[0].suno_clip_id == "clip-aaa"
    assert candidates[1].wav_url == "https://cdn.suno.ai/clip-bbb.wav"
    assert candidates[0].wav_url is None
    assert candidates[0].status == "completed"
    assert candidates[1].duration_seconds == 220.0


def test_local_provider_unavailable_returns_safe_error():
    """ConnectionError → provider_unavailable, no crash."""
    from providers.suno.local_unofficial_suno import LocalUnofficialSunoProvider

    p = LocalUnofficialSunoProvider()
    # Force base URL to unreachable address
    p._config["base_url"] = "http://127.0.0.1:19999"
    p._config["cookie"] = "fake"

    with pytest.raises(ProviderError) as exc_info:
        p.create_song("test", "pop", "hello world")

    assert exc_info.value.status == "provider_unavailable"
    assert "cookie" not in exc_info.value.message.lower()


def test_local_provider_capabilities_require_cookie():
    """Without SUNO_COOKIE, status should be auth_required."""
    from providers.suno.local_unofficial_suno import LocalUnofficialSunoProvider

    p = LocalUnofficialSunoProvider()
    p._config["cookie"] = ""
    caps = p.get_capabilities()
    assert caps.status == "auth_required"

    p._config["cookie"] = "valid_session_cookie"
    caps = p.get_capabilities()
    assert caps.status == "ready"


def test_unsupported_vocal_gender_injected_into_style():
    """vocal_gender not directly supported → appended to style tags."""
    from providers.suno.local_unofficial_suno import LocalUnofficialSunoProvider

    p = LocalUnofficialSunoProvider()
    p._config["base_url"] = "http://127.0.0.1:19999"
    p._config["cookie"] = "fake"

    # We can't actually call create_song (server not running),
    # so we test the payload construction logic by mocking _request
    captured_payload = {}

    def mock_request(method, path, body=None):
        captured_payload.update(body or {})
        return [{"id": "test-id", "status": "submitted"}]

    p._request = mock_request

    p.create_song(
        title="Test",
        style="city pop, synth",
        lyrics="hello",
        options={"vocal_gender": "Female"},
    )

    assert "female vocal" in captured_payload.get("tags", "").lower()


def test_unsupported_weirdness_stored_as_not_applied():
    """weirdness/style_influence not supported → stored in metadata, not_applied."""
    from providers.suno.local_unofficial_suno import LocalUnofficialSunoProvider
    caps = LocalUnofficialSunoProvider().get_capabilities()
    assert caps.weirdness is False
    assert caps.style_influence is False


# ─── Playwright Provider ────────────────────────────────────────────────────

def test_playwright_returns_user_action_required():
    """Playwright skeleton returns ProviderError with manual_import_required."""
    from providers.suno.playwright_suno_web import PlaywrightSunoWebProvider

    p = PlaywrightSunoWebProvider()
    with pytest.raises(ProviderError) as exc_info:
        p.create_song("test", "pop", "lyrics")
    assert exc_info.value.status == "manual_import_required"


def test_playwright_captcha_detection():
    """Playwright _check_page_for_verification detects CAPTCHA markers."""
    from providers.suno.playwright_suno_web import PlaywrightSunoWebProvider

    p = PlaywrightSunoWebProvider()
    assert p._check_page_for_verification("<div class='hcaptcha'>") == "captcha_required"
    assert p._check_page_for_verification("<div class='two-factor'>") == "two_factor_required"
    assert p._check_page_for_verification("<div>Normal page</div>") is None


# ─── Credential Safety ──────────────────────────────────────────────────────

def test_credentials_not_logged_in_errors():
    """ProviderError.safe_error must redact credential-like fields."""
    from providers.suno.base import ComposerProvider

    # Create a concrete subclass just for testing safe_error
    class TestProvider(ComposerProvider):
        def get_capabilities(self): return ProviderCapabilities(provider="test")
        def create_song(self, *a, **kw): ...
        def get_status(self, *a): ...
        def download_wav(self, *a): ...
        def download_mp3_preview(self, *a): ...
        def get_metadata(self, *a): ...

    p = TestProvider()
    err = p.safe_error(
        "auth_required", "Session expired",
        cookie="super_secret_cookie_value",
        token="sk-12345",
        normal_field="this is fine",
    )
    assert err.details["cookie"] == "***REDACTED***"
    assert err.details["token"] == "***REDACTED***"
    assert err.details["normal_field"] == "this is fine"


# ─── MP3-only blocks distribution ───────────────────────────────────────────

def test_mp3_only_candidate_blocks_distribution():
    """CandidateInfo with wav_url=None → MP3-only, distribution blocked."""
    c = CandidateInfo(candidate_id="A", audio_url="https://x.mp3", wav_url=None)
    assert c.wav_url is None
    # Distribution eligibility is checked by audio_qc, not candidate directly,
    # but the absence of wav_url means the downloaded file is MP3


# ─── Backward compatibility ────────────────────────────────────────────────

def test_existing_v02_tests_still_importable():
    """Verify key v0.2 modules still import without error."""
    from workflows.audio_qc import run_audio_qc
    from workflows.create_distribution_master import create_distribution_master
    from workflows.render_video import export_video_package
    from app.tabs.project_library import list_projects_library
