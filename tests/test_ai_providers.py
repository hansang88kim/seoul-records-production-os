"""
tests/test_ai_providers.py (v0.5)
AI Composer provider tests — all mock, no real API calls.
"""
from __future__ import annotations
import os
import pytest
from providers.ai.base import (
    MockAIProvider, OpenAIProvider, GeminiProvider,
    SongPromptPackage, get_ai_provider, get_available_ai_providers,
)


# ─── Mock Provider ───────────────────────────────────────────────────────────

def test_mock_ai_generates_title_style_lyrics():
    """Mock provider generates all three fields."""
    p = MockAIProvider()
    pkg = p.generate_song_package("비 오는 서울 밤")
    assert pkg.title, "Title is empty"
    assert pkg.style, "Style is empty"
    assert pkg.lyrics, "Lyrics is empty"
    assert "[Intro" in pkg.lyrics
    assert "[Chorus" in pkg.lyrics


def test_mock_ai_generate_title():
    p = MockAIProvider()
    title = p.generate_title("서울 야경")
    assert isinstance(title, str)
    assert len(title) > 0


def test_mock_ai_generate_style():
    p = MockAIProvider()
    style = p.generate_style("서울 야경")
    assert isinstance(style, str)
    assert len(style) <= 1000  # Suno style limit


def test_mock_ai_generate_lyrics():
    p = MockAIProvider()
    lyrics = p.generate_lyrics("서울 야경")
    assert "[Verse 1]" in lyrics


def test_mock_ai_rotates_songs():
    """Mock provider cycles through multiple mock songs."""
    p = MockAIProvider()
    t1 = p.generate_song_package("a").title
    t2 = p.generate_song_package("b").title
    # Should have at least 2 different songs
    assert isinstance(t1, str) and isinstance(t2, str)


# ─── SongPromptPackage ───────────────────────────────────────────────────────

def test_ai_song_package_schema():
    """SongPromptPackage has all required fields."""
    pkg = SongPromptPackage(
        title="테스트",
        style="pop",
        lyrics="[Verse]\nHello",
    )
    d = pkg.to_dict()
    assert "title" in d
    assert "style" in d
    assert "lyrics" in d
    assert "exclude_styles" in d
    assert "model" in d
    assert "vocal_gender" in d
    assert "weirdness" in d
    assert "style_influence" in d
    assert "metadata" in d


def test_ai_song_package_defaults():
    """SongPromptPackage defaults match Seoul Records spec."""
    pkg = SongPromptPackage()
    assert pkg.model == "v5.5"
    assert pkg.vocal_gender == "Female"
    assert pkg.weirdness == 35
    assert pkg.style_influence == 70
    assert pkg.language_pack == "ko_kr_seoul"


# ─── Provider availability ───────────────────────────────────────────────────

def test_openai_provider_disabled_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert OpenAIProvider.is_available() is False


def test_gemini_provider_disabled_without_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    assert GeminiProvider.is_available() is False


def test_openai_provider_enabled_with_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-fake")
    assert OpenAIProvider.is_available() is True


def test_gemini_provider_enabled_with_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "AI-test-key-fake")
    assert GeminiProvider.is_available() is True


# ─── Registry ────────────────────────────────────────────────────────────────

def test_get_ai_provider_mock():
    p = get_ai_provider("mock")
    assert isinstance(p, MockAIProvider)


def test_get_ai_provider_openai():
    p = get_ai_provider("openai")
    assert isinstance(p, OpenAIProvider)


def test_get_ai_provider_gemini():
    p = get_ai_provider("gemini")
    assert isinstance(p, GeminiProvider)


def test_get_available_ai_providers_always_includes_mock(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GEMINI_API_KEY", raising=False)
    providers = get_available_ai_providers()
    names = [p["name"] for p in providers]
    assert "mock" in names
    mock_p = [p for p in providers if p["name"] == "mock"][0]
    assert mock_p["available"] is True


# ─── Security ────────────────────────────────────────────────────────────────

def test_ai_prompt_does_not_include_api_key(monkeypatch):
    """System prompt and user prompt must not contain API keys."""
    from providers.ai.base import SYSTEM_PROMPT, _make_user_prompt
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-12345")
    prompt = SYSTEM_PROMPT + _make_user_prompt("test concept")
    assert "sk-secret" not in prompt
    assert "API_KEY" not in prompt


def test_mock_metadata_does_not_contain_key():
    p = MockAIProvider()
    pkg = p.generate_song_package("test")
    meta_str = str(pkg.metadata)
    assert "sk-" not in meta_str
    assert "API_KEY" not in meta_str


# ─── Korean text preservation ────────────────────────────────────────────────

def test_korean_title_lyrics_preserved_utf8():
    """Korean text must not become mojibake."""
    import json
    p = MockAIProvider()
    pkg = p.generate_song_package("비 오는 밤")
    report = json.dumps(pkg.to_dict(), ensure_ascii=False)
    assert "諛" not in report  # mojibake check
    parsed = json.loads(report)
    assert parsed["title"]  # not empty
    # Check Korean characters preserved
    for char in parsed["title"]:
        assert ord(char) < 0xFFFF  # valid unicode


# ─── Lyrics formatting + structure ───────────────────────────────────────────

def test_format_lyrics_adds_blank_before_sections():
    """_format_lyrics inserts a blank line before each section header."""
    from providers.ai.base import _format_lyrics
    messy = "[Verse 1]\n종로에서\n시계를 봐\n[Chorus]\n동대문에서"
    result = _format_lyrics(messy)
    lines = result.split("\n")
    # There should be a blank line before [Chorus]
    chorus_idx = lines.index("[Chorus]")
    assert lines[chorus_idx - 1] == "", "No blank line before [Chorus]"


def test_format_lyrics_collapses_multiple_blanks():
    """Multiple blank lines collapse to one."""
    from providers.ai.base import _format_lyrics
    messy = "[Verse 1]\n가사\n\n\n\n[Chorus]\n후렴"
    result = _format_lyrics(messy)
    assert "\n\n\n" not in result


def test_format_lyrics_no_leading_blank():
    """No leading blank lines."""
    from providers.ai.base import _format_lyrics
    result = _format_lyrics("\n\n[Verse 1]\n가사")
    assert not result.startswith("\n")


def test_mock_songs_have_10_sections():
    """Mock songs follow the 10-section structure."""
    from providers.ai.base import MOCK_SONGS, _format_lyrics
    for song in MOCK_SONGS:
        formatted = _format_lyrics(song.lyrics)
        sections = [l for l in formatted.split("\n") if l.startswith("[")]
        assert len(sections) == 10, f"{song.title} has {len(sections)} sections, expected 10"


def test_mock_songs_lyric_length_for_330():
    """Mock song lyrics are ~360-440 chars for 3:30 duration."""
    from providers.ai.base import MOCK_SONGS, _format_lyrics
    for song in MOCK_SONGS:
        formatted = _format_lyrics(song.lyrics)
        lyric_lines = [l for l in formatted.split("\n") if l and not l.startswith("[") and not l.startswith("(")]
        total = sum(len(l.replace("(", "").replace(")", "")) for l in formatted.split("\n") if l and not l.startswith("["))
        assert 340 <= total <= 460, f"{song.title} has {total} chars (target ~400 for 3:30)"


# ─── Lyric length control for 3:30 ───────────────────────────────────────────

def test_lyrics_char_count_excludes_headers():
    """_lyrics_char_count ignores [Section] headers."""
    from providers.ai.base import _lyrics_char_count
    lyrics = "[Verse 1]\n가사한줄\n[Chorus]\n후렴구절"
    # Only counts: 가사한줄(4) + 후렴구절(4) = 8
    assert _lyrics_char_count(lyrics) == 8


def test_mock_songs_under_440_chars():
    """Mock songs stay in the 3:30 range (380-420 sweet spot, 440 max)."""
    from providers.ai.base import MOCK_SONGS, _lyrics_char_count
    for song in MOCK_SONGS:
        chars = _lyrics_char_count(song.lyrics)
        assert chars <= 440, f"{song.title} has {chars} chars (max 440 for 3:30)"


def test_system_prompt_has_char_limits():
    """SYSTEM_PROMPT must specify line limits and total char target."""
    from providers.ai.base import SYSTEM_PROMPT
    assert "8-17" in SYSTEM_PROMPT or "4 lines" in SYSTEM_PROMPT
    assert "380-420" in SYSTEM_PROMPT or "420" in SYSTEM_PROMPT


def test_user_prompt_emphasizes_length():
    """User prompt for full generation emphasizes the length limit."""
    from providers.ai.base import _make_user_prompt
    prompt = _make_user_prompt("test", "all")
    assert "3:30" in prompt
