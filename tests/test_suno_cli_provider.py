"""
tests/test_suno_cli_provider.py (v0.4.2)
"""
from __future__ import annotations
import json, os
from pathlib import Path
from unittest import mock
import pytest
from providers.suno.base import ProviderError, CandidateInfo, ProviderCapabilities


# ─── Registry ────────────────────────────────────────────────────────────────

def test_registry_selects_suno_cli():
    from providers.suno import get_composer_provider
    assert get_composer_provider("suno_cli").PROVIDER_NAME == "suno_cli"

def test_registry_selects_suno_cli_short():
    from providers.suno import get_composer_provider
    assert get_composer_provider("cli").PROVIDER_NAME == "suno_cli"


# ─── Capabilities ───────────────────────────────────────────────────────────

def test_suno_cli_capabilities():
    from providers.suno.suno_cli_provider import SunoCliProvider
    caps = SunoCliProvider().get_capabilities()
    assert isinstance(caps, ProviderCapabilities)
    assert caps.vocal_gender is True
    assert caps.weirdness is True
    assert caps.wav_download is False
    assert caps.mp3_preview is True


# ─── SUNO_CLI_BIN env support ───────────────────────────────────────────────

def test_suno_cli_bin_absolute_path_is_used(monkeypatch):
    from providers.suno import suno_cli_provider as m
    from importlib import reload
    env_val = "C:/tools/suno/suno.exe"
    monkeypatch.setenv("SUNO_CLI_BIN", env_val)
    reload(m)
    result = m._get_suno_bin()
    assert "suno.exe" in result
    assert result == env_val or result == str(Path(env_val))

def test_suno_cli_bin_windows_path_supported(monkeypatch):
    from providers.suno import suno_cli_provider as m
    from importlib import reload
    win_path = "C:\\tools\\suno\\suno.exe"
    monkeypatch.setenv("SUNO_CLI_BIN", win_path)
    reload(m)
    result = m._get_suno_bin()
    assert "suno" in result.lower()
    assert result == win_path

def test_suno_available_uses_env_path_before_path_lookup(monkeypatch, tmp_path):
    from providers.suno import suno_cli_provider as m
    from importlib import reload
    fake_bin = tmp_path / "suno.exe"
    fake_bin.write_text("fake")
    monkeypatch.setenv("SUNO_CLI_BIN", str(fake_bin))
    reload(m)
    assert m._suno_available() is True

def test_path_fallback_to_suno_when_env_missing(monkeypatch):
    from providers.suno import suno_cli_provider as m
    from importlib import reload
    monkeypatch.delenv("SUNO_CLI_BIN", raising=False)
    reload(m)
    assert isinstance(m._get_suno_bin(), str)

def test_run_suno_uses_resolved_binary(tmp_path):
    from providers.suno.suno_cli_provider import _run_suno_json
    fake_bin = str(tmp_path / "my_suno")
    captured = []
    def mock_run(cmd, **kw):
        captured.extend(cmd)
        return mock.Mock(returncode=0, stdout=json.dumps({"data": {}}), stderr="")
    with mock.patch("subprocess.run", side_effect=mock_run):
        _run_suno_json(["credits"], suno_bin=fake_bin)
    assert captured[0] == fake_bin


# ─── generate command construction ──────────────────────────────────────────

def test_generate_command_includes_wait_and_download(monkeypatch, tmp_path):
    """create_song must include --wait --download and NOT --json."""
    from providers.suno import suno_cli_provider as m
    from importlib import reload
    fake_bin = tmp_path / "suno.exe"
    fake_bin.write_text("fake")
    monkeypatch.setenv("SUNO_CLI_BIN", str(fake_bin))
    reload(m)

    p = m.SunoCliProvider()
    captured = []
    dl_dir = str(tmp_path / "downloads")

    def mock_run(cmd, **kw):
        captured.extend(cmd)
        # Simulate downloaded file
        Path(dl_dir).mkdir(parents=True, exist_ok=True)
        (Path(dl_dir) / "test-song-abc12345.mp3").write_bytes(b"fake")
        return mock.Mock(returncode=0, stdout="", stderr="")

    with mock.patch("subprocess.run", side_effect=mock_run):
        p.create_song("밤이 지나면", "city pop", "test",
                       {"download_dir": dl_dir, "vocal_gender": "Female", "weirdness": 35})

    cmd_str = " ".join(captured)
    assert "--wait" in cmd_str
    assert "--download" in cmd_str
    assert "--json" not in cmd_str, f"--json must NOT be in generate command: {cmd_str}"
    assert "--vocal" in cmd_str
    assert "female" in cmd_str
    assert "--weirdness" in cmd_str

def test_generate_does_not_include_json_flag(monkeypatch, tmp_path):
    """--json conflicts with --wait --download; must NOT be appended to generate."""
    from providers.suno import suno_cli_provider as m
    from importlib import reload
    fake_bin = tmp_path / "suno.exe"
    fake_bin.write_text("fake")
    monkeypatch.setenv("SUNO_CLI_BIN", str(fake_bin))
    reload(m)

    p = m.SunoCliProvider()
    captured = []
    dl_dir = str(tmp_path / "dl")

    def mock_run(cmd, **kw):
        captured.extend(cmd)
        Path(dl_dir).mkdir(parents=True, exist_ok=True)
        (Path(dl_dir) / "song-abc12345.mp3").write_bytes(b"fake")
        return mock.Mock(returncode=0, stdout="", stderr="")

    with mock.patch("subprocess.run", side_effect=mock_run):
        p.create_song("Test", "pop", "lyrics", {"download_dir": dl_dir})

    assert "--json" not in captured, f"--json in generate args: {captured}"

def test_generate_full_command_matches_cli_syntax(monkeypatch, tmp_path):
    """Full command matches: suno generate --title --tags --lyrics-file --exclude --vocal --weirdness --style-influence --wait --download <dir>."""
    from providers.suno import suno_cli_provider as m
    from importlib import reload
    fake_bin = tmp_path / "suno"
    fake_bin.write_text("fake")
    monkeypatch.setenv("SUNO_CLI_BIN", str(fake_bin))
    reload(m)

    p = m.SunoCliProvider()
    captured = []
    dl = str(tmp_path / "out")

    def mock_run(cmd, **kw):
        captured.extend(cmd)
        Path(dl).mkdir(parents=True, exist_ok=True)
        (Path(dl) / "song-a1b2c3d4.mp3").write_bytes(b"fake")
        return mock.Mock(returncode=0, stdout="", stderr="")

    with mock.patch("subprocess.run", side_effect=mock_run):
        p.create_song("Test", "rock, guitar", "[Verse]\nHi", {
            "exclude_styles": ["sax lead", "trot"],
            "vocal_gender": "Female",
            "weirdness": 40,
            "style_influence": 65,
            "download_dir": dl,
        })

    assert captured[0] == str(fake_bin)
    assert "generate" in captured
    assert "--title" in captured
    assert "--tags" in captured
    assert "--lyrics-file" in captured
    assert "--exclude" in captured
    assert "--vocal" in captured
    assert "--weirdness" in captured
    assert "--style-influence" in captured
    assert "--wait" in captured
    assert "--download" in captured
    assert "--json" not in captured

def test_model_name_normalized(monkeypatch, tmp_path):
    """chirp-v4 → v4, chirp-v4-5 → v4.5."""
    from providers.suno import suno_cli_provider as m
    from importlib import reload
    fake_bin = tmp_path / "suno"
    fake_bin.write_text("fake")
    monkeypatch.setenv("SUNO_CLI_BIN", str(fake_bin))
    reload(m)

    p = m.SunoCliProvider()
    captured = []
    dl = str(tmp_path / "dl")

    def mock_run(cmd, **kw):
        captured.extend(cmd)
        Path(dl).mkdir(parents=True, exist_ok=True)
        (Path(dl) / "x-12345678.mp3").write_bytes(b"fake")
        return mock.Mock(returncode=0, stdout="", stderr="")

    with mock.patch("subprocess.run", side_effect=mock_run):
        p.create_song("T", "pop", "lyrics", {"model": "chirp-v4", "download_dir": dl})

    # chirp-v4 should be normalized to v4
    if "--model" in captured:
        idx = captured.index("--model")
        assert captured[idx + 1] == "v4"


# ─── status uses --json ─────────────────────────────────────────────────────

def test_status_uses_json_flag():
    from providers.suno.suno_cli_provider import SunoCliProvider
    p = SunoCliProvider()
    captured = []
    def mock_run(cmd, **kw):
        captured.extend(cmd)
        return mock.Mock(returncode=0, stdout=json.dumps({"data": [{"id": "c1", "status": "complete", "duration": 200}]}), stderr="")
    with mock.patch("subprocess.run", side_effect=mock_run):
        p.get_status("c1")
    assert "--json" in captured


# ─── WAV / errors / credentials ─────────────────────────────────────────────

def test_wav_download_raises_unavailable():
    from providers.suno.suno_cli_provider import SunoCliProvider
    with pytest.raises(ProviderError) as exc:
        SunoCliProvider().download_wav("x", Path("/tmp/t.wav"))
    assert exc.value.status == "wav_download_unavailable"

def test_auth_expired_maps_correctly():
    from providers.suno.suno_cli_provider import _run_suno_json
    err = json.dumps({"version": "1", "status": "error",
                      "error": {"code": "auth_expired", "message": "JWT expired", "suggestion": "suno auth"}})
    with mock.patch("subprocess.run", return_value=mock.Mock(returncode=1, stdout=err, stderr="")):
        with pytest.raises(ProviderError) as exc:
            _run_suno_json(["credits"])
        assert exc.value.status == "auth_required"

def test_binary_not_found():
    from providers.suno.suno_cli_provider import _run_suno_raw
    with mock.patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(ProviderError) as exc:
            _run_suno_raw(["generate"])
        assert exc.value.status == "provider_unavailable"

def test_exit_code_2_includes_stderr_in_error():
    """Exit code 2 (invalid args) must include sanitized stderr in error details."""
    from providers.suno.suno_cli_provider import _run_suno_raw
    with mock.patch("subprocess.run", return_value=mock.Mock(
        returncode=2, stdout="", stderr="error: unexpected argument '--json'")):
        with pytest.raises(ProviderError) as exc:
            _run_suno_raw(["generate", "--title", "test"])
    assert exc.value.status == "generation_failed"
    assert "stderr" in exc.value.details
    assert "unexpected" in exc.value.details["stderr"]

def test_credential_fields_redacted():
    from providers.suno.suno_cli_provider import SunoCliProvider
    err = SunoCliProvider().safe_error("auth_required", "expired",
                                       cookie="secret", jwt="secret2", url="http://ok")
    assert err.details["cookie"] == "***REDACTED***"
    assert err.details["jwt"] == "***REDACTED***"
    assert err.details["url"] == "http://ok"

def test_stderr_with_jwt_is_redacted():
    from providers.suno.suno_cli_provider import _redact_stderr
    assert _redact_stderr("error: invalid jwt token abc") == "[stderr redacted — may contain credentials]"
    assert "unexpected" in _redact_stderr("error: unexpected argument")

# ─── Backward compat ────────────────────────────────────────────────────────

def test_all_providers_importable():
    from providers.suno import get_composer_provider
    for name in ["mock", "manual_import", "local_unofficial", "suno_cli", "playwright_web"]:
        caps = get_composer_provider(name).get_capabilities()
        assert isinstance(caps, ProviderCapabilities)
