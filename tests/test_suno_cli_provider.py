"""
tests/test_suno_cli_provider.py (v0.4.2)
───────────────────────────────────────
Tests for SunoCliProvider (paperfoot/suno-cli subprocess adapter).
All tests use mock subprocess — no real suno binary needed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

import pytest

from providers.suno.base import ProviderError, CandidateInfo, ProviderCapabilities


# ─── Registry ────────────────────────────────────────────────────────────────

def test_registry_selects_suno_cli():
    from providers.suno import get_composer_provider
    p = get_composer_provider("suno_cli")
    assert p.PROVIDER_NAME == "suno_cli"


def test_registry_selects_suno_cli_short():
    from providers.suno import get_composer_provider
    p = get_composer_provider("cli")
    assert p.PROVIDER_NAME == "suno_cli"


# ─── Capabilities ───────────────────────────────────────────────────────────

def test_suno_cli_capabilities():
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
    assert caps.wav_download is False
    assert caps.mp3_preview is True


# ─── SUNO_CLI_BIN env support ────────────────────────────────────────────────

def test_suno_cli_bin_absolute_path_is_used(monkeypatch):
    """SUNO_CLI_BIN with absolute path → used directly, not PATH lookup."""
    from providers.suno import suno_cli_provider as m
    from importlib import reload

    monkeypatch.setenv("SUNO_CLI_BIN", "C:/tools/suno/suno.exe")
    reload(m)
    result = m._get_suno_bin()
    assert result == "C:/tools/suno/suno.exe"


def test_suno_cli_bin_windows_path_supported(monkeypatch):
    """Windows backslash paths in SUNO_CLI_BIN are accepted."""
    from providers.suno import suno_cli_provider as m
    from importlib import reload

    monkeypatch.setenv("SUNO_CLI_BIN", "C:\\tools\\suno\\suno.exe")
    reload(m)
    result = m._get_suno_bin()
    assert "suno" in result.lower()
    assert result == "C:\\tools\\suno\\suno.exe"


def test_suno_available_uses_env_path_before_path_lookup(monkeypatch, tmp_path):
    """_suno_available checks SUNO_CLI_BIN path first, not shutil.which."""
    from providers.suno import suno_cli_provider as m
    from importlib import reload

    # Create a fake binary at a known path
    fake_bin = tmp_path / "suno.exe"
    fake_bin.write_text("fake")
    monkeypatch.setenv("SUNO_CLI_BIN", str(fake_bin))
    reload(m)

    assert m._suno_available() is True


def test_path_fallback_to_suno_when_env_missing(monkeypatch):
    """Without SUNO_CLI_BIN, falls back to 'suno' on PATH."""
    from providers.suno import suno_cli_provider as m
    from importlib import reload

    monkeypatch.delenv("SUNO_CLI_BIN", raising=False)
    reload(m)
    result = m._get_suno_bin()
    # Either found on PATH or returns "suno" as fallback
    assert isinstance(result, str)
    assert "suno" in result.lower()


def test_run_suno_uses_resolved_binary(monkeypatch, tmp_path):
    """_run_suno must use the resolved binary path, not hardcoded 'suno'."""
    from providers.suno import suno_cli_provider as m
    from importlib import reload

    fake_bin = str(tmp_path / "my_suno_binary")
    monkeypatch.setenv("SUNO_CLI_BIN", fake_bin)
    reload(m)

    captured_cmd = []

    def mock_subprocess_run(cmd, **kwargs):
        captured_cmd.extend(cmd)
        return mock.Mock(
            returncode=0,
            stdout=json.dumps({"data": [{"id": "clip-1"}]}),
            stderr="",
        )

    with mock.patch("subprocess.run", side_effect=mock_subprocess_run):
        m._run_suno(["credits"], suno_bin=fake_bin)

    assert captured_cmd[0] == fake_bin, (
        f"Expected binary '{fake_bin}', got '{captured_cmd[0]}'"
    )


# ─── Command building with --wait --download ────────────────────────────────

def test_generate_command_includes_wait_and_download(monkeypatch, tmp_path):
    """create_song must include --wait and --download <dir> in the command."""
    from providers.suno.suno_cli_provider import SunoCliProvider

    fake_bin = tmp_path / "suno.exe"
    fake_bin.write_text("fake")
    monkeypatch.setenv("SUNO_CLI_BIN", str(fake_bin))

    from providers.suno import suno_cli_provider as m
    from importlib import reload
    reload(m)

    p = m.SunoCliProvider()
    captured = []

    def mock_run(cmd, **kw):
        captured.extend(cmd)
        return mock.Mock(
            returncode=0,
            stdout=json.dumps({"data": [{"id": "clip-aaa"}, {"id": "clip-bbb"}]}),
            stderr="",
        )

    with mock.patch("subprocess.run", side_effect=mock_run):
        dl_dir = str(tmp_path / "downloads")
        task_id = p.create_song(
            "밤이 지나면", "city pop", "test lyrics",
            {"download_dir": dl_dir, "vocal_gender": "Female", "weirdness": 35},
        )

    cmd_str = " ".join(captured)
    assert "--wait" in cmd_str, f"--wait missing: {cmd_str}"
    assert "--download" in cmd_str, f"--download missing: {cmd_str}"
    assert dl_dir in cmd_str, f"download dir missing: {cmd_str}"
    assert "--vocal" in cmd_str
    assert "female" in cmd_str
    assert "--weirdness" in cmd_str
    assert "35" in cmd_str
    assert "--json" in cmd_str
    assert task_id == "clip-aaa,clip-bbb"


def test_create_song_builds_full_command(monkeypatch, tmp_path):
    """Full command matches paperfoot/suno-cli v0.5.7 syntax."""
    from providers.suno import suno_cli_provider as m
    from importlib import reload

    fake_bin = tmp_path / "suno"
    fake_bin.write_text("fake")
    monkeypatch.setenv("SUNO_CLI_BIN", str(fake_bin))
    reload(m)

    p = m.SunoCliProvider()
    captured = []

    def mock_run(cmd, **kw):
        captured.extend(cmd)
        return mock.Mock(
            returncode=0,
            stdout=json.dumps({"data": [{"id": "c1"}]}),
            stderr="",
        )

    with mock.patch("subprocess.run", side_effect=mock_run):
        p.create_song(
            title="Test Song",
            style="indie rock, guitar",
            lyrics="[Verse]\nHello",
            options={
                "exclude_styles": ["sax lead", "trot", "EDM"],
                "vocal_gender": "Female",
                "weirdness": 40,
                "style_influence": 65,
                "model": "chirp-v4",
                "download_dir": str(tmp_path / "out"),
            },
        )

    cmd_str = " ".join(captured)
    assert captured[0] == str(fake_bin)
    assert "generate" in cmd_str
    assert "--title" in cmd_str
    assert "--tags" in cmd_str
    assert "--lyrics-file" in cmd_str
    assert "--exclude" in cmd_str
    assert "sax lead" in cmd_str
    assert "--vocal" in cmd_str
    assert "--weirdness" in cmd_str
    assert "--style-influence" in cmd_str
    assert "--model" in cmd_str
    assert "--wait" in cmd_str
    assert "--download" in cmd_str
    assert "--json" in cmd_str


# ─── Status normalization ────────────────────────────────────────────────────

def test_status_polling_normalizes_response(monkeypatch, tmp_path):
    from providers.suno import suno_cli_provider as m
    from importlib import reload
    fake_bin = tmp_path / "suno"
    fake_bin.write_text("fake")
    monkeypatch.setenv("SUNO_CLI_BIN", str(fake_bin))
    reload(m)

    p = m.SunoCliProvider()
    mock_response = json.dumps({
        "status": "ok",
        "data": [
            {"id": "clip-1", "status": "complete", "duration": 218.5,
             "audio_url": "https://cdn.suno.ai/1.mp3", "title": "Test"},
            {"id": "clip-2", "status": "complete", "duration": 215.0,
             "audio_url": "https://cdn.suno.ai/2.mp3", "title": "Test"},
        ],
    })

    with mock.patch("subprocess.run") as mr:
        mr.return_value = mock.Mock(returncode=0, stdout=mock_response, stderr="")
        status = p.get_status("clip-1,clip-2")

    assert status["status"] == "completed"
    assert len(status["candidates"]) == 2
    assert status["candidates"][0]["candidate_id"] == "A"


# ─── WAV unavailable ────────────────────────────────────────────────────────

def test_wav_download_raises_unavailable():
    from providers.suno.suno_cli_provider import SunoCliProvider
    p = SunoCliProvider()
    with pytest.raises(ProviderError) as exc:
        p.download_wav("clip-1", Path("/tmp/test.wav"))
    assert exc.value.status == "wav_download_unavailable"


# ─── Error mapping ──────────────────────────────────────────────────────────

def test_auth_expired_error_maps_correctly(monkeypatch, tmp_path):
    from providers.suno import suno_cli_provider as m
    from importlib import reload
    fake_bin = tmp_path / "suno"
    fake_bin.write_text("fake")
    monkeypatch.setenv("SUNO_CLI_BIN", str(fake_bin))
    reload(m)

    p = m.SunoCliProvider()
    error_json = json.dumps({
        "version": "1", "status": "error",
        "error": {"code": "auth_expired", "message": "JWT expired",
                  "suggestion": "Run `suno auth --login`"},
    })
    with mock.patch("subprocess.run") as mr:
        mr.return_value = mock.Mock(returncode=1, stdout=error_json, stderr="")
        with pytest.raises(ProviderError) as exc:
            p.get_status("clip-1")
        assert exc.value.status == "auth_required"


def test_binary_not_found_raises_unavailable():
    from providers.suno.suno_cli_provider import _run_suno
    with mock.patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(ProviderError) as exc:
            _run_suno(["credits"])
        assert exc.value.status == "provider_unavailable"


# ─── Credential safety ──────────────────────────────────────────────────────

def test_stderr_with_credentials_is_redacted():
    from providers.suno.suno_cli_provider import _run_suno
    with mock.patch("subprocess.run") as mr:
        mr.return_value = mock.Mock(returncode=1, stdout="", stderr="Error: invalid jwt token abc123")
        with pytest.raises(ProviderError) as exc:
            _run_suno(["generate", "--title", "test"])
    assert "abc123" not in exc.value.details.get("stderr", "")


def test_credential_fields_redacted_in_safe_error():
    from providers.suno.suno_cli_provider import SunoCliProvider
    p = SunoCliProvider()
    err = p.safe_error("auth_required", "expired",
                       cookie="secret_cookie", jwt="secret_jwt", base_url="http://ok")
    assert err.details["cookie"] == "***REDACTED***"
    assert err.details["jwt"] == "***REDACTED***"
    assert err.details["base_url"] == "http://ok"


# ─── Backward compat ────────────────────────────────────────────────────────

def test_all_providers_still_importable():
    from providers.suno import get_composer_provider
    for name in ["mock", "manual_import", "local_unofficial", "suno_cli", "playwright_web"]:
        p = get_composer_provider(name)
        caps = p.get_capabilities()
        assert isinstance(caps, ProviderCapabilities)
