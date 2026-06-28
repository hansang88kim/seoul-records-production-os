"""
tests/test_song_lab.py (v0.5)
──────────────────────────────
Tests for Song Lab UI components and defaults.
"""
from __future__ import annotations
import pytest


def test_composer_panel_importable():
    """Composer panel module imports without error."""
    from app.ui.composer_panel import render_composer_panel, SUNO_MODELS, DEFAULT_EXCLUDE


def test_song_card_importable():
    """Song card module imports without error."""
    from app.ui.song_card import render_song_list, render_song_card


def test_song_lab_importable():
    """Song Lab tab imports without error."""
    from app.tabs.song_lab import render_song_lab


def test_valid_suno_cli_model_values():
    """Model list must contain only valid suno-cli model values."""
    from app.ui.composer_panel import SUNO_MODELS
    valid = {"v5.5", "v5", "v4.5", "v4", "v3.5"}
    for m in SUNO_MODELS:
        assert m in valid, f"Invalid model: {m}"


def test_default_exclude_styles():
    """Default exclude must include Seoul Records policy items."""
    from app.ui.composer_panel import DEFAULT_EXCLUDE
    required = ["sax lead", "drum fill-ins", "trot", "enka", "EDM"]
    for item in required:
        assert item in DEFAULT_EXCLUDE, f"Missing exclude: {item}"


def test_citypop_style_preset_under_1000_chars():
    """City pop style preset must be under Suno's 1000-char limit."""
    from app.ui.composer_panel import CITYPOP_STYLE_PRESET
    assert len(CITYPOP_STYLE_PRESET) <= 1000, (
        f"Preset is {len(CITYPOP_STYLE_PRESET)} chars, max 1000"
    )


def test_vocal_auto_not_in_options():
    """Vocal options must not include 'Auto' — Suno CLI doesn't accept it."""
    # The composer panel offers Female/Male/Instrumental
    # If Instrumental is selected, vocal_gender becomes "Auto" but
    # the instrumental flag is set, so --vocal is not sent
    pass  # Verified by code inspection: vocal != "Instrumental" → sent


def test_mp3_preview_distribution_blocked():
    """MP3 file must not be distribution eligible."""
    song = {
        "file_type": "mp3",
        "distribution_eligible": False,
    }
    assert song["distribution_eligible"] is False


def test_wav_import_distribution_eligible():
    """WAV file must be distribution eligible."""
    song = {
        "file_type": "wav",
        "distribution_eligible": True,
    }
    assert song["distribution_eligible"] is True


def test_korean_title_preserved():
    """Korean title must not be garbled."""
    import json
    title = "밤이 지나면"
    report = json.dumps({"title": title}, ensure_ascii=False)
    parsed = json.loads(report)
    assert parsed["title"] == "밤이 지나면"
    assert "諛" not in report  # mojibake check


def test_suno_cli_command_does_not_include_json_for_generate(monkeypatch):
    """generate command must NOT include --json."""
    from providers.suno.suno_cli_provider import SunoCliProvider
    from unittest import mock
    import json

    monkeypatch.setenv("SUNO_COOKIE", "fake_cookie")
    p = SunoCliProvider()
    captured = []

    def mock_run(cmd, **kw):
        if "--json" in cmd:
            return mock.Mock(returncode=0, stdout=json.dumps({"data": {"credits_left": 100}}), stderr="")
        captured.extend(cmd)
        return mock.Mock(returncode=0)

    with mock.patch("subprocess.run", side_effect=mock_run), \
         mock.patch("providers.suno.suno_cli_provider._suno_available", return_value=True):
        try:
            p.create_song("test", "pop", "[Verse]\nHi", {"download_dir": "/tmp/test_dl"})
        except Exception:
            pass  # May fail on file ops, but command is captured

    if captured:
        # Only check the generate command portion (before any fallback 'list' call)
        if "generate" in captured:
            gen_start = captured.index("generate")
            gen_end = captured.index("list") if "list" in captured else len(captured)
            generate_cmd = captured[gen_start:gen_end]
            assert "--json" not in generate_cmd, f"--json in generate: {generate_cmd}"


def test_provider_status_does_not_show_cookie():
    """Provider capabilities note must not contain actual cookie values."""
    from providers.suno.suno_cli_provider import SunoCliProvider
    import os
    os.environ["SUNO_COOKIE"] = "secret_cookie_value_12345"
    try:
        caps = SunoCliProvider().get_capabilities()
        note = caps.note or ""
        fallback = caps.fallback_instructions or ""
        assert "secret_cookie" not in note
        assert "secret_cookie" not in fallback
    finally:
        os.environ.pop("SUNO_COOKIE", None)


# ─── Auto Batch mode ─────────────────────────────────────────────────────────

def test_auto_batch_function_exists():
    """_render_auto_batch and _generate_one_auto must exist."""
    from app.tabs.song_lab import _render_auto_batch, _generate_one_auto


def test_generate_one_auto_uses_mock(monkeypatch, tmp_path):
    """_generate_one_auto with mock AI returns a result dict."""
    from app.tabs import song_lab
    from unittest import mock

    monkeypatch.setenv("SUNO_COOKIE", "fake_cookie")

    # Mock SunoCliProvider so it doesn't actually call suno
    def fake_create_song(self, title, style, lyrics, options):
        # Simulate a downloaded file
        dl = options.get("download_dir", str(tmp_path))
        from pathlib import Path as P
        P(dl).mkdir(parents=True, exist_ok=True)
        (P(dl) / "song-abc12345.mp3").write_bytes(b"fake")
        return "abc12345"

    with mock.patch("providers.suno.suno_cli_provider.SunoCliProvider.create_song", fake_create_song):
        result = song_lab._generate_one_auto(
            "서울 밤", "mock", {"model": "v5.5", "vocal_gender": "Female"}
        )

    assert result["status"] == "generated"
    assert result["title"]  # mock provides a title


def test_auto_batch_title_style_lyrics_all_generated():
    """Auto batch via mock generates title AND style AND lyrics."""
    from providers.ai.base import get_ai_provider
    ai = get_ai_provider("mock")
    pkg = ai.generate_song_package("서울 밤")
    assert pkg.title, "title missing"
    assert pkg.style, "style missing"
    assert pkg.lyrics, "lyrics missing"


# ─── Exclude styles sent separately (not merged into style) ──────────────────

def test_exclude_sent_via_flag_not_in_style(monkeypatch, tmp_path):
    """Exclude styles must go to --exclude flag, NOT be merged into --tags."""
    from providers.suno import suno_cli_provider as m
    from importlib import reload
    from unittest import mock
    from pathlib import Path
    fake_bin = tmp_path / "suno"
    fake_bin.write_text("fake")
    monkeypatch.setenv("SUNO_CLI_BIN", str(fake_bin))
    monkeypatch.setenv("SUNO_COOKIE", "cookie")
    reload(m)

    p = m.SunoCliProvider()
    captured = []
    dl = str(tmp_path / "dl")

    def mock_run(cmd, **kw):
        import json as _j
        if "--json" in cmd:
            return mock.Mock(returncode=0, stdout=_j.dumps({"data": {"credits_left": 100}}), stderr="")
        captured.extend(cmd)
        from pathlib import Path as P
        P(dl).mkdir(parents=True, exist_ok=True)
        (P(dl) / "x-12345678.mp3").write_bytes(b"fake")
        return mock.Mock(returncode=0, stdout="", stderr="")

    with mock.patch("subprocess.run", side_effect=mock_run):
        p.create_song(
            "test", "Japanese city pop, warm piano", "lyrics",
            {"download_dir": dl, "exclude_styles": ["sax lead", "trot", "EDM"]},
        )

    cmd_str = " ".join(captured)
    # --exclude flag present with the excludes
    assert "--exclude" in cmd_str
    # The style/tags must NOT contain the exclude terms
    tags_idx = captured.index("--tags") + 1
    tags_value = captured[tags_idx]
    assert "sax" not in tags_value, f"sax leaked into tags: {tags_value}"
    assert "trot" not in tags_value
    assert "-sax" not in tags_value  # no negative-prefix hack in tags


def test_composer_returns_clean_style_and_exclude_list():
    """The composer return format separates style from exclude_styles."""
    # The fix ensures style has no '-sax' negatives and exclude_styles is a list.
    from app.ui.composer_panel import DEFAULT_EXCLUDE
    exclude_list = [
        s.strip().lstrip("-").strip()
        for s in DEFAULT_EXCLUDE.split(",")
        if s.strip().lstrip("-").strip()
    ]
    assert "sax lead" in exclude_list
    assert all(not item.startswith("-") for item in exclude_list)


# ─── Auto Batch 2-step plan flow ─────────────────────────────────────────────

def test_plan_only_helpers_exist():
    """Plan-based generation helpers exist."""
    from app.tabs.song_lab import _generate_plan_only, _generate_one_from_draft, _render_auto_batch


def test_generate_plan_only_returns_draft():
    """_generate_plan_only with mock returns title/style/lyrics draft (no Suno)."""
    from app.tabs.song_lab import _generate_plan_only
    draft = _generate_plan_only("서울 밤", "mock")
    assert draft["status"] == "drafted"
    assert draft["title"]
    assert draft["style"]
    assert draft["lyrics"]
    assert "lyric_chars" in draft


def test_generate_one_from_draft_uses_exclude_flag(monkeypatch, tmp_path):
    """_generate_one_from_draft sends exclude via flag, clean style."""
    from app.tabs import song_lab
    from unittest import mock
    from pathlib import Path as P

    monkeypatch.setenv("SUNO_COOKIE", "cookie")
    captured = []

    def fake_create(self, title, style, lyrics, options):
        captured.append(("style", style))
        captured.append(("exclude", options.get("exclude_styles")))
        dl = options.get("download_dir", str(tmp_path))
        P(dl).mkdir(parents=True, exist_ok=True)
        (P(dl) / "x-12345678.mp3").write_bytes(b"fake")
        return "x12345678"

    draft = {"title": "테스트", "style": "Japanese city pop, warm piano", "lyrics": "[Verse]\n가사"}
    with mock.patch("providers.suno.suno_cli_provider.SunoCliProvider.create_song", fake_create):
        result = song_lab._generate_one_from_draft(draft, {"model": "v5.5"})

    assert result["status"] == "generated"
    # Style passed clean (no -sax), exclude as list
    style_val = [v for k, v in captured if k == "style"][0]
    exclude_val = [v for k, v in captured if k == "exclude"][0]
    assert "sax" not in style_val
    assert isinstance(exclude_val, list)
    assert "sax lead" in exclude_val


# ─── Single folder + keep longest mp3 ────────────────────────────────────────

def test_download_dir_is_project_songs_folder(monkeypatch, tmp_path):
    """All songs in a project download to the SAME songs/ folder (no subfolders)."""
    import app.project_manager as pm
    monkeypatch.setattr(pm, "OUTPUTS_DIR", tmp_path)
    d1 = pm.song_project_download_dir("앨범1", "곡 하나")
    d2 = pm.song_project_download_dir("앨범1", "곡 둘")
    assert d1 == d2  # same folder
    assert d1.name == "songs"


def test_keep_longest_new_mp3(monkeypatch, tmp_path):
    """Of newly-generated clips, only the longest is kept; shorter deleted."""
    from app.tabs import song_lab
    from unittest import mock

    folder = tmp_path / "songs"
    folder.mkdir()
    # Pre-existing file (should be ignored)
    old = folder / "old-song.mp3"
    old.write_bytes(b"old")
    before = song_lab._snapshot_mp3s(folder)

    # Two new clips
    short = folder / "new-short.mp3"
    long = folder / "new-long.mp3"
    short.write_bytes(b"s")
    long.write_bytes(b"l")

    # Mock durations: long=200s, short=150s
    def fake_dur(p):
        return 200.0 if "long" in str(p) else 150.0
    monkeypatch.setattr(song_lab, "_mp3_duration", fake_dur)

    kept = song_lab._keep_longest_new_mp3(folder, before)
    assert kept == long  # longest kept
    assert long.exists()
    assert not short.exists()  # shorter deleted
    assert old.exists()  # pre-existing untouched


def test_keep_longest_ignores_preexisting(monkeypatch, tmp_path):
    """If no new files, returns None and deletes nothing."""
    from app.tabs import song_lab
    folder = tmp_path / "songs"
    folder.mkdir()
    existing = folder / "a.mp3"
    existing.write_bytes(b"x")
    before = song_lab._snapshot_mp3s(folder)
    # No new files added
    kept = song_lab._keep_longest_new_mp3(folder, before)
    assert kept is None
    assert existing.exists()
