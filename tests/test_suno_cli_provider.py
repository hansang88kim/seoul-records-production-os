"""
tests/test_suno_cli_provider.py (v0.4)
───────────────────────────────────────
Tests for SunoCliProvider (paperfoot/suno-cli subprocess adapter).
All tests use mock subprocess — no real suno binary needed.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from providers.suno.base import ProviderError, CandidateInfo, ProviderCapabilities


# ─── Registry ────────────────────────────────────────────────────────────────

def test_registry_selects_suno_cli():
    """get_composer_provider('suno_cli') returns SunoCliProvider."""
    from providers.suno import get_composer_provider
    p = get_composer_provider("suno_cli")
    assert p.PROVIDER_NAME == "suno_cli"


def test_registry_selects_suno_cli_short():
    """get_composer_provider('cli') also works."""
    from providers.suno import get_composer_provider
    p = get_composer_provider("cli")
    assert p.PROVIDER_NAME == "suno_cli"


# ─── Capabilities ───────────────────────────────────────────────────────────

def test_suno_cli_capabilities():
    """SunoCliProvider reports correct capabilities."""
    from providers.suno.suno_cli_provider import SunoCliProvider
    p = SunoCliProvider()
    caps = p.get_capabilities()
    assert isinstance(caps, ProviderCapabilities)
    assert caps.title is True
    assert caps.exclude_styles is True
    assert caps.vocal_gender is True
    assert caps.weirdness is True
    assert caps.style_influence is True
    assert caps.persona is True
    assert caps.wav_download is False  # MP3 only; WAV via suno.com
    assert caps.mp3_preview is True


# ─── Command building ───────────────────────────────────────────────────────

def test_create_song_builds_correct_command():
    """create_song builds suno generate command with all flags."""
    from providers.suno.suno_cli_provider import SunoCliProvider

    p = SunoCliProvider()
    captured_cmd = []

    def mock_run(cmd, **kwargs):
        captured_cmd.extend(cmd)
        return mock.Mock(
            returncode=0,
            stdout=json.dumps({
                "status": "ok",
                "data": [{"id": "clip-aaa"}, {"id": "clip-bbb"}]
            }),
            stderr="",
        )

    with mock.patch("providers.suno.suno_cli_provider._suno_available", return_value=True), \
         mock.patch("subprocess.run", side_effect=mock_run):
        task_id = p.create_song(
            title="밤이 지나면",
            style="city pop, female vocal",
            lyrics="[Verse 1]\n테스트 가사",
            options={
                "exclude_styles": ["sax lead", "trot"],
                "vocal_gender": "Female",
                "weirdness": 35,
                "style_influence": 70,
                "model": "chirp-v4",
            },
        )

    assert task_id == "clip-aaa,clip-bbb"
    cmd_str = " ".join(captured_cmd)
    assert "generate" in cmd_str
    assert "--title" in cmd_str
    assert "밤이 지나면" in cmd_str
    assert "--tags" in cmd_str
    assert "--exclude" in cmd_str
    assert "sax lead" in cmd_str
    assert "--vocal" in cmd_str
    assert "female" in cmd_str
    assert "--weirdness" in cmd_str
    assert "35" in cmd_str
    assert "--style-influence" in cmd_str
    assert "70" in cmd_str
    assert "--model" in cmd_str
    assert "--json" in cmd_str


# ─── Status normalization ────────────────────────────────────────────────────

def test_status_polling_normalizes_response():
    """get_status normalizes suno status JSON."""
    from providers.suno.suno_cli_provider import SunoCliProvider

    p = SunoCliProvider()

    mock_response = json.dumps({
        "status": "ok",
        "data": [
            {"id": "clip-1", "status": "complete", "duration": 218.5,
             "audio_url": "https://cdn.suno.ai/1.mp3", "title": "Test",
             "metadata": {"tags": "pop"}},
            {"id": "clip-2", "status": "complete", "duration": 215.0,
             "audio_url": "https://cdn.suno.ai/2.mp3", "title": "Test",
             "metadata": {"tags": "pop"}},
        ],
    })

    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0, stdout=mock_response, stderr="")
        status = p.get_status("clip-1,clip-2")

    assert status["status"] == "completed"
    assert len(status["candidates"]) == 2
    assert status["candidates"][0]["candidate_id"] == "A"
    assert status["candidates"][1]["candidate_id"] == "B"


# ─── WAV unavailable ────────────────────────────────────────────────────────

def test_wav_download_raises_unavailable():
    """download_wav must raise wav_download_unavailable (MP3 only)."""
    from providers.suno.suno_cli_provider import SunoCliProvider

    p = SunoCliProvider()
    with pytest.raises(ProviderError) as exc:
        p.download_wav("clip-1", Path("/tmp/test.wav"))
    assert exc.value.status == "wav_download_unavailable"


# ─── Error mapping ──────────────────────────────────────────────────────────

def test_auth_expired_error_maps_correctly():
    """suno-cli auth_expired → auth_required."""
    from providers.suno.suno_cli_provider import SunoCliProvider

    p = SunoCliProvider()
    error_json = json.dumps({
        "version": "1",
        "status": "error",
        "error": {
            "code": "auth_expired",
            "message": "JWT expired",
            "suggestion": "Run `suno auth --login` to refresh",
        },
    })

    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=1, stdout=error_json, stderr="")
        with pytest.raises(ProviderError) as exc:
            p.get_status("clip-1")
        assert exc.value.status == "auth_required"


def test_binary_not_found_raises_unavailable():
    """FileNotFoundError → provider_unavailable."""
    from providers.suno.suno_cli_provider import _run_suno

    with mock.patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(ProviderError) as exc:
            _run_suno(["credits"])
        assert exc.value.status == "provider_unavailable"


# ─── Credential safety ──────────────────────────────────────────────────────

def test_stderr_with_credentials_is_redacted():
    """Stderr containing credential keywords must be redacted."""
    from providers.suno.suno_cli_provider import _run_suno

    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(
            returncode=1,
            stdout="",
            stderr="Error: invalid jwt token abc123secret",
        )
        with pytest.raises(ProviderError) as exc:
            _run_suno(["generate", "--title", "test"])

    # The stderr should be redacted because it contains "token"
    details = exc.value.details
    stderr_val = details.get("stderr", "")
    assert "abc123secret" not in stderr_val


def test_suno_cli_credentials_not_in_command_log():
    """Credential values must not appear in logged commands."""
    from providers.suno.suno_cli_provider import SunoCliProvider

    p = SunoCliProvider()
    err = p.safe_error(
        "auth_required", "Session expired",
        cookie="__client=eyJhbGciOiJSUzI1",
        jwt="eyJhbGciOiJSUzI1NiIsInR5",
    )
    assert "eyJhbGci" not in str(err.details)
    assert err.details["cookie"] == "***REDACTED***"
    assert err.details["jwt"] == "***REDACTED***"


# ─── Backward compat ────────────────────────────────────────────────────────

def test_all_providers_still_importable():
    """All provider modules import without error."""
    from providers.suno import get_composer_provider
    for name in ["mock", "manual_import", "local_unofficial", "suno_cli", "playwright_web"]:
        p = get_composer_provider(name)
        caps = p.get_capabilities()
        assert isinstance(caps, ProviderCapabilities)


def test_suno_cli_bin_env_respected(monkeypatch):
    """SUNO_CLI_BIN env var overrides default binary name."""
    from providers.suno.suno_cli_provider import _get_suno_bin
    monkeypatch.setenv('SUNO_CLI_BIN', 'C:/tools/suno/suno.exe')
    result = _get_suno_bin()
    assert 'suno' in result.lower()
    assert result == 'C:/tools/suno/suno.exe'


def test_suno_cli_bin_fallback_to_path(monkeypatch):
    """Without SUNO_CLI_BIN, falls back to suno on PATH."""
    from providers.suno.suno_cli_provider import _get_suno_bin
    monkeypatch.delenv('SUNO_CLI_BIN', raising=False)
    result = _get_suno_bin()
    assert isinstance(result, str)


def test_create_song_includes_wait_and_download():
    """create_song command must include --wait and --download."""
    from providers.suno.suno_cli_provider import SunoCliProvider
    import json as _json

    p = SunoCliProvider()
    captured = []

    def mock_run(cmd, **kw):
        captured.extend(cmd)
        return mock.Mock(returncode=0, stdout=_json.dumps({"data": [{"id": "clip-1"}]}), stderr="")

    with mock.patch("providers.suno.suno_cli_provider._suno_available", return_value=True),          mock.patch("subprocess.run", side_effect=mock_run):
        p.create_song("Test", "pop", "lyrics", {"download_dir": "/tmp/test_dl"})

    cmd_str = " ".join(captured)
    assert "--wait" in cmd_str, f"--wait missing from: {cmd_str}"
    assert "--download" in cmd_str, f"--download missing from: {cmd_str}"
