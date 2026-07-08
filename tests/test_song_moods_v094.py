"""
tests/test_song_moods_v094.py — selectable song MOOD categories (v1.0.0-alpha.94).

Songs stay authentic city pop (never enka/trot) but the emotional color can be
picked: bright/refreshing, wistful, calm, romantic, dreamy.
"""
from __future__ import annotations

import pytest

from providers.ai.base import (
    SONG_MOODS, DEFAULT_SONG_MOOD, mood_directive, apply_mood_to_style,
    build_system_prompt,
)


def test_five_mood_categories_with_korean_labels():
    assert set(SONG_MOODS) == {"refreshing", "wistful", "calm", "romantic", "dreamy"}
    for m in SONG_MOODS.values():
        assert m["label"] and m["style"] and m["directive"]
    assert DEFAULT_SONG_MOOD in SONG_MOODS


def test_mood_directive_steers_and_forbids_trot():
    d = mood_directive("refreshing")
    assert "bright" in d.lower() and "refreshing" in d.lower()
    assert "enka" in d.lower() or "trot" in d.lower()  # genre discipline
    assert mood_directive("") == ""
    assert mood_directive("bogus") == ""


def test_apply_mood_flavors_even_a_locked_style():
    base = "Authentic 1980s Japanese city pop, warm rhodes, tight drums"
    out = apply_mood_to_style(base, "refreshing")
    assert "bright refreshing" in out.lower()
    assert "city pop" in out.lower()          # base preserved
    # idempotent-ish: applying again doesn't double-stack the same keywords
    assert apply_mood_to_style(out, "refreshing") == out


def test_apply_mood_noop_for_empty():
    assert apply_mood_to_style("x", "") == "x"
    assert apply_mood_to_style("", "refreshing") == ""


def test_guidance_allows_bright_moods_but_keeps_citypop_and_bans_trot():
    sp = build_system_prompt("korean")
    # the old hard "AVOID these words: bright, refreshing…" ban is gone
    assert "AVOID these words: bright" not in sp
    # but it's still city pop and still forbids trot/enka
    assert "Japanese city pop" in sp
    assert "enka" in sp.lower() and "trot" in sp.lower()
