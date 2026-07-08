"""
tests/test_thumbnail_art_style_v096.py — thumbnail ART STYLE option (alpha.96).

Benchmarked from the top-viewed "tokyo citypop" YouTube thumbnails (mostly
1980s-90s city-pop ANIME illustration), the generator now defaults to an anime
art style and offers photo/analog. The chosen style flows into both the
template prompt and the Korean-freeform LLM instruction.
"""
from __future__ import annotations

from services.thumbnail.prompt_generator import (
    THUMB_ART_STYLES, DEFAULT_THUMB_ART_STYLE, art_render,
    generate_flow_prompt, generate_prompt_batch, build_prompt_batch,
)
from services.thumbnail import prompt_composer as pc


def test_three_styles_default_anime():
    assert set(THUMB_ART_STYLES) == {"anime", "photo", "analog"}
    assert DEFAULT_THUMB_ART_STYLE == "anime"
    for s in THUMB_ART_STYLES.values():
        assert s["label"] and s["render"]


def test_art_render_falls_back_to_anime():
    assert "ANIME" in art_render("")
    assert "ANIME" in art_render("bogus")
    assert "photorealistic" in art_render("photo")


def test_flow_prompt_defaults_to_anime_illustration():
    d = generate_flow_prompt("korea", "night", 0)
    assert d["art_style"] == "anime"
    assert "ANIME" in d["main_prompt"] and "album cover" in d["main_prompt"]
    # anime explicitly negates photoreal rather than requesting it
    assert "NOT photorealistic" in d["main_prompt"]


def test_flow_prompt_photo_style_is_photoreal():
    d = generate_flow_prompt("korea", "night", 0, art_style="photo")
    assert "photorealistic" in d["main_prompt"].lower()
    assert "ANIME" not in d["main_prompt"]


def test_anime_style_never_says_japanese_for_other_countries():
    # regression: the art directive must not leak "Japanese" into a Thai prompt
    th = generate_flow_prompt("thailand", "night", 0, art_style="anime")["main_prompt"]
    assert "Japanese" not in th and "Thai city-pop" in th


def test_batch_helpers_thread_art_style():
    b = generate_prompt_batch("korea", "night", 2, art_style="photo")
    assert all("photorealistic" in p["main_prompt"].lower() for p in b)
    bb = build_prompt_batch("korea", "night", 2, art_style="anime")
    assert all(p["art_style"] == "anime" for p in bb)


def test_background_only_prompt_also_takes_art_style():
    d = generate_flow_prompt("japan", "night", 0, include_person=False, art_style="anime")
    assert "ANIME" in d["main_prompt"]


def test_llm_instruction_reflects_anime_vs_photo():
    base = generate_flow_prompt("korea", "night", 0)
    anime = pc._build_llm_instruction("비 오는 밤 홍대", base, True, art_style="anime")
    photo = pc._build_llm_instruction("비 오는 밤 홍대", base, True, art_style="photo")
    assert "ANIME" in anime and "cel-shaded" in anime
    assert "35mm" in photo and "ANIME" not in photo


def test_compose_template_carries_art_style():
    out = pc.compose_english_prompt("", "korea", "night", True, art_style="photo")
    assert out["art_style"] == "photo"
    assert "photorealistic" in out["main_prompt"].lower()
