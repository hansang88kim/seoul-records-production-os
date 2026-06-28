"""
tests/test_languages.py — Multilingual city pop prompt tests.
"""
from __future__ import annotations
import pytest


def test_all_languages_present():
    from providers.ai.languages import LANGUAGES
    for key in ["korean", "japanese", "thai", "indonesian", "vietnamese"]:
        assert key in LANGUAGES


def test_each_language_has_city_and_locations():
    from providers.ai.languages import LANGUAGES
    for key, cfg in LANGUAGES.items():
        assert cfg["city"], f"{key} missing city"
        assert cfg["locations"], f"{key} missing locations"
        assert cfg["lyric_language"], f"{key} missing lyric_language"
        assert cfg["title_examples"], f"{key} missing title_examples"


def test_get_language_fallback():
    from providers.ai.languages import get_language
    # Unknown key falls back to Korean
    assert get_language("klingon")["city"] == "Seoul"
    assert get_language("")["city"] == "Seoul"


def test_build_system_prompt_per_language():
    """System prompt includes the right lyric language + city for each."""
    from providers.ai.base import build_system_prompt
    from providers.ai.languages import LANGUAGES
    for key, cfg in LANGUAGES.items():
        sp = build_system_prompt(key)
        assert cfg["lyric_language"] in sp
        # City name (first word) appears
        assert cfg["city"].split(" ")[0] in sp


def test_system_prompt_always_japanese_citypop_style():
    """Style is ALWAYS Japanese city pop regardless of lyric language."""
    from providers.ai.base import build_system_prompt
    for key in ["thai", "vietnamese", "indonesian"]:
        sp = build_system_prompt(key)
        assert "Japanese city pop" in sp
        # No saxophone in any language
        assert "NEVER mention saxophone" in sp


def test_user_prompt_specifies_language_and_city():
    from providers.ai.base import _make_user_prompt
    # Thai
    p = _make_user_prompt("test", "all", "thai")
    assert "Thai" in p
    assert "Bangkok" in p
    # Japanese
    p2 = _make_user_prompt("test", "lyrics", "japanese")
    assert "Japanese" in p2


def test_japanese_targets_tokyo_shibuya():
    from providers.ai.languages import get_language
    jp = get_language("japanese")
    assert "Tokyo" in jp["city"]
    assert "渋谷" in jp["locations"]


def test_thai_targets_bangkok():
    from providers.ai.languages import get_language
    th = get_language("thai")
    assert th["city"] == "Bangkok"
    assert th["lyric_language"] == "Thai"


def test_vietnamese_targets_saigon():
    from providers.ai.languages import get_language
    vn = get_language("vietnamese")
    assert "Ho Chi Minh" in vn["city"] or "Saigon" in vn["city"]
