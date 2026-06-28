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
    monkeypatch.setenv("SUNO_COOKIE", "fake_cookie")
    reload(m)

    p = m.SunoCliProvider()
    captured = []
    dl_dir = str(tmp_path / "downloads")

    def mock_run(cmd, **kw):
        # credits check (--json) returns valid session
        if "--json" in cmd:
            return mock.Mock(returncode=0, stdout=json.dumps({"data": {"credits_left": 100}}), stderr="")
        captured.extend(cmd)
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
    monkeypatch.setenv("SUNO_COOKIE", "fake_cookie")
    reload(m)

    p = m.SunoCliProvider()
    captured = []
    dl_dir = str(tmp_path / "dl")

    def mock_run(cmd, **kw):
        if "--json" in cmd:
            return mock.Mock(returncode=0, stdout=json.dumps({"data": {"credits_left": 100}}), stderr="")
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
    monkeypatch.setenv("SUNO_COOKIE", "fake_cookie")
    reload(m)

    p = m.SunoCliProvider()
    captured = []
    dl = str(tmp_path / "out")

    def mock_run(cmd, **kw):
        if "--json" in cmd:
            return mock.Mock(returncode=0, stdout=json.dumps({"data": {"credits_left": 100}}), stderr="")
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
    monkeypatch.setenv("SUNO_COOKIE", "fake_cookie")
    reload(m)

    p = m.SunoCliProvider()
    captured = []
    dl = str(tmp_path / "dl")

    def mock_run(cmd, **kw):
        if "--json" in cmd:
            return mock.Mock(returncode=0, stdout=json.dumps({"data": {"credits_left": 100}}), stderr="")
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

def test_exit_code_2_includes_command_args_in_error():
    """Exit code 2 maps to captcha_required (often CAPTCHA load failure)."""
    from providers.suno.suno_cli_provider import _run_suno_raw
    with mock.patch("subprocess.run", return_value=mock.Mock(returncode=2)):
        with pytest.raises(ProviderError) as exc:
            _run_suno_raw(["generate", "--title", "test"])
    assert exc.value.status == "captcha_required"
    assert "exit_code" in exc.value.details
    assert exc.value.details["exit_code"] == 2
    assert "command_args" in exc.value.details

def test_credential_fields_redacted():
    from providers.suno.suno_cli_provider import SunoCliProvider
    err = SunoCliProvider().safe_error("auth_required", "expired",
                                       cookie="secret", jwt="secret2", url="http://ok")
    assert err.details["cookie"] == "***REDACTED***"
    assert err.details["jwt"] == "***REDACTED***"
    assert err.details["url"] == "http://ok"

def test_stderr_redacts_long_tokens_not_keywords():
    """Smart redaction: redacts 40+ char tokens and key=value patterns, keeps error messages."""
    from providers.suno.suno_cli_provider import _redact_stderr
    # Long token gets redacted
    long_token = "a" * 50
    assert "REDACTED" in _redact_stderr(f"token: {long_token}")
    # Short error messages stay readable
    assert "unexpected" in _redact_stderr("error: unexpected argument")
    # cookie=value patterns get redacted
    assert "REDACTED" in _redact_stderr("cookie=abc123secret_value")

# ─── Backward compat ────────────────────────────────────────────────────────

def test_all_providers_importable():
    from providers.suno import get_composer_provider
    for name in ["mock", "manual_import", "local_unofficial", "suno_cli", "playwright_web"]:
        caps = get_composer_provider(name).get_capabilities()
        assert isinstance(caps, ProviderCapabilities)


# ─── verify_ready (auth + credits) ───────────────────────────────────────────

def test_verify_ready_no_cookie(monkeypatch):
    """verify_ready fails clearly when no cookie."""
    from providers.suno.suno_cli_provider import SunoCliProvider
    monkeypatch.delenv("SUNO_COOKIE", raising=False)
    p = SunoCliProvider()
    result = p.verify_ready()
    assert result["ok"] is False
    assert result["authenticated"] is False
    assert "쿠키" in result["message"] or "SUNO_COOKIE" in result["message"]


def test_verify_ready_success(monkeypatch, tmp_path):
    """verify_ready succeeds with valid cookie + credits."""
    from providers.suno import suno_cli_provider as m
    from importlib import reload
    fake_bin = tmp_path / "suno"
    fake_bin.write_text("fake")
    monkeypatch.setenv("SUNO_CLI_BIN", str(fake_bin))
    monkeypatch.setenv("SUNO_COOKIE", "fake_cookie_value")
    reload(m)

    p = m.SunoCliProvider()
    call_count = [0]

    def mock_run(cmd, **kw):
        call_count[0] += 1
        # First call: auth (no --json). Second: credits (--json)
        if "--json" in cmd:
            return mock.Mock(returncode=0, stdout=json.dumps({"data": {"credits_left": 9970}}), stderr="")
        return mock.Mock(returncode=0)

    with mock.patch("subprocess.run", side_effect=mock_run):
        result = p.verify_ready()

    assert result["ok"] is True
    assert result["authenticated"] is True
    assert result["credits"] == 9970


def test_verify_ready_does_not_expose_cookie(monkeypatch, tmp_path):
    """verify_ready message must never contain the cookie value."""
    from providers.suno import suno_cli_provider as m
    from importlib import reload
    fake_bin = tmp_path / "suno"
    fake_bin.write_text("fake")
    secret = "SUPER_SECRET_COOKIE_xyz789"
    monkeypatch.setenv("SUNO_CLI_BIN", str(fake_bin))
    monkeypatch.setenv("SUNO_COOKIE", secret)
    reload(m)

    p = m.SunoCliProvider()

    def mock_run(cmd, **kw):
        if "--json" in cmd:
            return mock.Mock(returncode=0, stdout=json.dumps({"data": {"credits_left": 100}}), stderr="")
        return mock.Mock(returncode=0)

    with mock.patch("subprocess.run", side_effect=mock_run):
        result = p.verify_ready()

    assert secret not in str(result)


# ─── Auth required before generation ─────────────────────────────────────────

def test_create_song_raises_without_cookie(monkeypatch, tmp_path):
    """create_song must raise auth_required if SUNO_COOKIE is not set."""
    from providers.suno import suno_cli_provider as m
    from importlib import reload
    fake_bin = tmp_path / "suno"
    fake_bin.write_text("fake")
    monkeypatch.setenv("SUNO_CLI_BIN", str(fake_bin))
    monkeypatch.delenv("SUNO_COOKIE", raising=False)
    reload(m)

    p = m.SunoCliProvider()
    with pytest.raises(ProviderError) as exc:
        p.create_song("test", "pop", "lyrics", {"download_dir": str(tmp_path / "dl")})
    assert exc.value.status == "auth_required"


def test_create_song_raises_when_auth_fails(monkeypatch, tmp_path):
    """create_song must raise auth_required if auth command fails."""
    from providers.suno import suno_cli_provider as m
    from importlib import reload
    fake_bin = tmp_path / "suno"
    fake_bin.write_text("fake")
    monkeypatch.setenv("SUNO_CLI_BIN", str(fake_bin))
    monkeypatch.setenv("SUNO_COOKIE", "expired_cookie")
    reload(m)

    p = m.SunoCliProvider()

    def mock_run(cmd, **kw):
        # auth --cookie returns non-zero (auth failed)
        return mock.Mock(returncode=1, stdout="", stderr="")

    with mock.patch("subprocess.run", side_effect=mock_run):
        with pytest.raises(ProviderError) as exc:
            p.create_song("test", "pop", "lyrics", {"download_dir": str(tmp_path / "dl")})
    assert exc.value.status == "auth_required"


def test_ensure_auth_verifies_via_credits(monkeypatch, tmp_path):
    """_ensure_auth returns False if auth succeeds but credits show expired session."""
    from providers.suno import suno_cli_provider as m
    from importlib import reload
    fake_bin = tmp_path / "suno"
    fake_bin.write_text("fake")
    monkeypatch.setenv("SUNO_CLI_BIN", str(fake_bin))
    monkeypatch.setenv("SUNO_COOKIE", "cookie")
    reload(m)

    p = m.SunoCliProvider()

    def mock_run(cmd, **kw):
        if "--json" in cmd:
            # credits returns auth error → session invalid
            err = json.dumps({"status": "error", "error": {"code": "auth_expired", "message": "expired"}})
            return mock.Mock(returncode=1, stdout=err, stderr="")
        return mock.Mock(returncode=0)  # auth --cookie succeeds

    with mock.patch("subprocess.run", side_effect=mock_run):
        result = p._ensure_auth()
    assert result is False  # auth cmd OK but session invalid


# ─── Credit extraction (AttributeError fix) ──────────────────────────────────

def test_extract_credits_various_shapes():
    """_extract_credits handles all JSON shapes without AttributeError."""
    from providers.suno.suno_cli_provider import _extract_credits
    assert _extract_credits({"credits_left": 9970}) == 9970
    assert _extract_credits({"data": {"credits": 100}}) == 100
    assert _extract_credits({"balance": 200}) == 200


def test_extract_credits_no_attribute_error_on_int():
    """data under 'data' being an int must NOT raise AttributeError."""
    from providers.suno.suno_cli_provider import _extract_credits
    # These previously crashed with 'int has no attribute get'
    assert _extract_credits({"data": 50}) == 50
    assert _extract_credits(9970) == 9970


def test_extract_credits_no_attribute_error_on_none_or_str():
    """None/str/empty must return None, never crash."""
    from providers.suno.suno_cli_provider import _extract_credits
    assert _extract_credits(None) is None
    assert _extract_credits("not a dict") is None
    assert _extract_credits({}) is None
    assert _extract_credits({"data": None}) is None


# ─── CAPTCHA auto-retry ──────────────────────────────────────────────────────

def test_captcha_retries_then_succeeds(monkeypatch, tmp_path):
    """create_song retries on CAPTCHA failure and succeeds on a later attempt."""
    from providers.suno import suno_cli_provider as m
    from importlib import reload
    fake_bin = tmp_path / "suno"
    fake_bin.write_text("fake")
    monkeypatch.setenv("SUNO_CLI_BIN", str(fake_bin))
    monkeypatch.setenv("SUNO_COOKIE", "cookie")
    reload(m)

    p = m.SunoCliProvider()
    dl = str(tmp_path / "dl")
    generate_calls = [0]

    def mock_run(cmd, **kw):
        if "--json" in cmd:  # credits/auth verify
            return mock.Mock(returncode=0, stdout=json.dumps({"data": {"credits_left": 100}}), stderr="")
        if "generate" in cmd:
            generate_calls[0] += 1
            if generate_calls[0] < 2:
                # First attempt: CAPTCHA failure (exit 2)
                return mock.Mock(returncode=2, stdout="", stderr="")
            # Second attempt: success
            from pathlib import Path as P
            P(dl).mkdir(parents=True, exist_ok=True)
            (P(dl) / "song-abc12345.mp3").write_bytes(b"fake")
            return mock.Mock(returncode=0, stdout="", stderr="")
        return mock.Mock(returncode=0)

    with mock.patch("subprocess.run", side_effect=mock_run), \
         mock.patch("time.sleep"):  # skip the retry delay
        task_id = p.create_song("test", "pop", "lyrics", {"download_dir": dl})

    # Should have retried generate at least twice
    assert generate_calls[0] >= 2
    assert task_id  # got a result


def test_config_error_maps_to_captcha():
    """config_error (hcaptcha never loaded) maps to captcha_required."""
    from providers.suno.suno_cli_provider import _map_error_code
    assert _map_error_code("config_error") == "captcha_required"
    assert _map_error_code("hcaptcha") == "captcha_required"


# ─── CAPTCHA retry count + empty style guard ─────────────────────────────────

def test_captcha_retries_configurable(monkeypatch, tmp_path):
    """SUNO_CAPTCHA_RETRIES controls the retry count (clamped 1-30)."""
    from providers.suno import suno_cli_provider as m
    from importlib import reload
    fake_bin = tmp_path / "suno"
    fake_bin.write_text("fake")
    monkeypatch.setenv("SUNO_CLI_BIN", str(fake_bin))
    monkeypatch.setenv("SUNO_COOKIE", "cookie")
    monkeypatch.setenv("SUNO_CAPTCHA_RETRIES", "10")
    reload(m)

    p = m.SunoCliProvider()
    dl = str(tmp_path / "dl")
    attempts = [0]

    def mock_run(cmd, **kw):
        if "--json" in cmd:
            return mock.Mock(returncode=0, stdout=json.dumps({"data": {"credits_left": 100}}), stderr="")
        if "generate" in cmd:
            attempts[0] += 1
            # Always fail with CAPTCHA to count attempts
            return mock.Mock(returncode=2, stdout="", stderr="")
        return mock.Mock(returncode=0)

    with mock.patch("subprocess.run", side_effect=mock_run), mock.patch("time.sleep"):
        try:
            p.create_song("t", "Japanese citypop", "lyrics", {"download_dir": dl})
        except Exception:
            pass

    # Should have tried 10 times before giving up
    assert attempts[0] == 10


def test_empty_style_rejected(monkeypatch, tmp_path):
    """Empty style raises an error (prevents ', female vocals' junk tags)."""
    from providers.suno import suno_cli_provider as m
    from importlib import reload
    fake_bin = tmp_path / "suno"
    fake_bin.write_text("fake")
    monkeypatch.setenv("SUNO_CLI_BIN", str(fake_bin))
    monkeypatch.setenv("SUNO_COOKIE", "cookie")
    reload(m)

    p = m.SunoCliProvider()
    def mock_run(cmd, **kw):
        if "--json" in cmd:
            return mock.Mock(returncode=0, stdout=json.dumps({"data": {"credits_left": 100}}), stderr="")
        return mock.Mock(returncode=0)

    with mock.patch("subprocess.run", side_effect=mock_run):
        with pytest.raises(m.ProviderError):
            p.create_song("title", "   ", "lyrics", {"download_dir": str(tmp_path)})
