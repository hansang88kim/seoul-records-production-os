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
