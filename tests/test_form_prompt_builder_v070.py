"""
tests/test_form_prompt_builder_v070.py — v1.0.0-alpha.70.

services/thumbnail/form_prompt_builder.py (ported from the reference
thumbnail_prompt_builder.py) + its integration into
services/thumbnail/prompt_generator.generate_flow_prompt(form=...).
"""
from __future__ import annotations

import pytest

from services.thumbnail.form_prompt_builder import (
    FORM_SPECS, NEGATIVE, BRAND_STYLE, ASPECT,
    ThumbnailPromptRequest, build_image_prompt,
)
from services.thumbnail.prompt_generator import (
    generate_flow_prompt, generate_prompt_batch, NEGATIVE_PROMPT, _merge_negatives,
)


# ─── form_prompt_builder.py itself (ported ~verbatim) ───────────────────────

def test_all_six_forms_defined_with_both_ratios():
    assert set(FORM_SPECS) == {"A", "B", "C", "D", "E", "F"}
    for form, spec in FORM_SPECS.items():
        assert spec["composition_169"] and spec["composition_11"]
        assert spec["subject_default"]


def test_build_image_prompt_combines_subject_composition_mood_aspect():
    out = build_image_prompt(ThumbnailPromptRequest(form="C", ratio="169"))
    assert out["form"] == "C"
    assert FORM_SPECS["C"]["subject_default"] in out["prompt"]
    assert FORM_SPECS["C"]["composition_169"] in out["prompt"]
    assert BRAND_STYLE in out["prompt"]
    assert ASPECT["169"] in out["prompt"]
    assert out["negative_prompt"] == NEGATIVE
    assert out["gemini_hint"] == {"aspect_ratio": "16:9"}
    assert out["gpt_image_hint"] == {"size": "1536x1024"}


def test_build_image_prompt_subject_override_and_mood_extra():
    out = build_image_prompt(ThumbnailPromptRequest(
        form="A", ratio="11", subject_override="a robot DJ", mood_extra="winter snow",
    ))
    assert "a robot DJ" in out["prompt"]
    assert FORM_SPECS["A"]["subject_default"] not in out["prompt"]
    assert "winter snow" in out["prompt"]
    assert ASPECT["11"] in out["prompt"]


# ─── prompt_generator.py integration ────────────────────────────────────────

def test_form_none_is_byte_identical_to_pre_alpha70_behavior():
    """form=None (default) must not change a single character of the old
    output — the whole point of the backward-compat requirement."""
    with_default = generate_flow_prompt("korea", "night", 0)
    explicit_none = generate_flow_prompt("korea", "night", 0, form=None)
    assert with_default == explicit_none
    assert with_default["form"] is None
    assert with_default["form_composition"] is None
    assert with_default["negative_prompt"] == NEGATIVE_PROMPT


def test_form_given_appends_composition_and_merges_negative():
    base = generate_flow_prompt("korea", "night", 0, include_person=True)
    formed = generate_flow_prompt("korea", "night", 0, include_person=True, form="A")

    assert formed["main_prompt"].startswith(base["main_prompt"])
    assert FORM_SPECS["A"]["composition_169"] in formed["main_prompt"]
    assert formed["form"] == "A"
    assert formed["form_composition"] == FORM_SPECS["A"]["composition_169"]

    # Existing NEGATIVE_PROMPT terms preserved verbatim (esp. the VHS/grain
    # exclusions the .md instructions call out explicitly to keep).
    assert "no VHS effect" in formed["negative_prompt"]
    assert "no film grain" in formed["negative_prompt"]
    # New terms from the form builder's NEGATIVE get merged in.
    assert "no frame" in formed["negative_prompt"]


def test_form_composition_uses_169_even_when_include_person_false():
    """Only one image is ever generated per candidate (16:9); form's 1:1
    composition is never used here — see docstring."""
    formed = generate_flow_prompt("korea", "night", 0, include_person=False, form="D")
    assert formed["form_composition"] == FORM_SPECS["D"]["composition_169"]
    assert FORM_SPECS["D"]["composition_11"] not in formed["main_prompt"]


def test_unknown_form_raises_value_error():
    with pytest.raises(ValueError):
        generate_flow_prompt("korea", "night", 0, form="Z")


def test_generate_prompt_batch_applies_form_to_every_prompt():
    prompts = generate_prompt_batch("korea", "night", count=3, form="B")
    assert len(prompts) == 3
    assert all(p["form"] == "B" for p in prompts)
    assert all(FORM_SPECS["B"]["composition_169"] in p["main_prompt"] for p in prompts)


def test_generate_prompt_batch_form_none_default_unaffected():
    prompts = generate_prompt_batch("korea", "night", count=2)
    assert all(p["form"] is None for p in prompts)


# ─── _merge_negatives() helper ───────────────────────────────────────────────

def test_merge_negatives_dedups_case_insensitively_keeps_base_first():
    merged = _merge_negatives("no text, no logo", "NO TEXT, no frame")
    assert merged == "no text, no logo, no frame"


def test_merge_negatives_empty_extra_returns_base_unchanged():
    assert _merge_negatives("no text, no logo", "") == "no text, no logo"
