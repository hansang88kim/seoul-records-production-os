"""
services/thumbnail/prompt_composer.py — v1.0.0-alpha.77

Compose ONE polished English image-generation prompt from a user's free-form
Korean description, so the user can describe the exact image they want (poses,
clothing, objects, setting) and have it faithfully reflected — instead of only
picking country/mood dropdowns.

Design (per the alpha.77 spec):
  * Reuses the existing country/theme/person/FORM_SPECS scaffolding: the
    generated English prompt keeps the same 1990s city-pop record-sleeve
    styling, the country preset, the mood, and the selected form's composition
    constraint — the Korean free-form text is woven in as the concrete subject.
  * LLM = Gemini (GOOGLE_GEMINI_API_KEY), same key already used for Nano Banana
    image gen. requests only, no SDK. The key is read from env and NEVER logged.
  * Graceful fallback: if there is no key or the call fails, fall back to the
    existing f-string template prompt (generate_flow_prompt) — this feature must
    never hard-fail a generation. The caller can see which path was taken via
    the returned ``source`` field.
  * This module only COMPOSES text; it never calls the image provider.
"""
from __future__ import annotations

import logging
import os

from services.thumbnail.prompt_generator import generate_flow_prompt

logger = logging.getLogger(__name__)

_GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)


def _gemini_key() -> str | None:
    for var in ("GOOGLE_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        v = os.environ.get(var, "").strip()
        if v:
            return v
    return None


def _build_llm_instruction(korean_freeform: str, base: dict, include_person: bool) -> str:
    """Assemble the instruction sent to Gemini. ``base`` is a generate_flow_prompt
    dict (used as the style/composition reference)."""
    subject_rule = (
        "Include a glamorous, stylish woman in her early twenties as the centered, "
        "dominant subject (1990s retro-glam fashion styling)."
        if include_person else
        "Background only — no people facing the camera."
    )
    form_comp = base.get("form_composition")
    composition_rule = (
        form_comp if form_comp
        else "balanced negative space near a title-safe band for a text overlay"
    )
    return (
        "You are an expert prompt engineer for AI image generators (Midjourney / "
        "Nano Banana / GPT-Image), specializing in premium 1990s Korean/Asian "
        "city-pop album-cover YouTube thumbnails.\n\n"
        "Write ONE polished English image-generation prompt (a single flowing "
        "paragraph — no line breaks, no markdown, no preamble, no quotes) for a "
        "playlist thumbnail / city-pop album cover.\n\n"
        f"The user described, in Korean, what they want in the image:\n"
        f"\"{korean_freeform.strip()}\"\n\n"
        "Requirements you MUST honor:\n"
        f"- Faithfully reflect the user's description above (their poses, clothing, "
        f"objects, setting, mood).\n"
        f"- Country / setting: {base.get('country', '')} — {base.get('scene', '')}.\n"
        f"- Mood / theme: {base.get('theme', '') or 'wistful nostalgic city night'}.\n"
        "- Era / style: premium 1990s retro city-pop record-sleeve aesthetic, "
        "cinematic, moody neon reflections, glossy analog-film look, elegant and "
        "sophisticated — NOT gaudy, NOT oversaturated.\n"
        f"- {subject_rule}\n"
        f"- Composition constraint (keep this): {composition_rule}.\n"
        "- The image MUST contain no text, letters, logos, or watermarks.\n"
        "- Photorealistic, ultra-detailed, 4K, sharp focus, high dynamic range.\n\n"
        "Output ONLY the final English prompt text — nothing else."
    )


def _call_gemini(instruction: str, api_key: str) -> str | None:
    """Single text-generation call. Returns the composed text, or None on failure.
    Never logs the key."""
    try:
        import requests
        from providers.ai.base import GeminiProvider
        try:
            models = GeminiProvider.list_models(api_key)
            model = models[0] if models else "gemini-2.5-flash"
        except Exception:
            model = "gemini-2.5-flash"
        url = _GEMINI_ENDPOINT.format(model=model, key=api_key)
        resp = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": instruction}]}],
                  "generationConfig": {"maxOutputTokens": 1200, "temperature": 0.9}},
            timeout=60,
        )
        if resp.status_code != 200:
            logger.warning("Prompt compose: Gemini HTTP %s", resp.status_code)
            return None
        data = resp.json()
        text = ""
        for cand in data.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                text += part.get("text", "")
        text = _clean(text)
        return text or None
    except Exception as e:
        logger.warning("Prompt compose: Gemini call failed: %s", type(e).__name__)
        return None


def _clean(text: str) -> str:
    """Strip markdown fences / wrapping quotes / stray whitespace the model may add."""
    t = (text or "").strip()
    t = t.replace("```", "").strip()
    # collapse internal newlines into spaces (we want a single paragraph)
    t = " ".join(line.strip() for line in t.splitlines() if line.strip())
    if len(t) >= 2 and t[0] in "\"'“”" and t[-1] in "\"'“”":
        t = t[1:-1].strip()
    return t


def compose_english_prompt(
    korean_freeform: str,
    country: str,
    theme: str,
    include_person: bool = True,
    form: str | None = None,
    track_no: int = 0,
) -> dict:
    """
    Compose a single English image prompt from the Korean free-form description.

    Returns a full generate_flow_prompt-shaped dict (so downstream candidate /
    branding code keeps working unchanged) with ``main_prompt`` replaced by the
    composed English text. Extra keys: ``freeform_ko`` and ``prompt_source``
    (one of "llm" | "fallback_nokey" | "fallback_error" | "template").

    * korean_freeform empty  → returns the plain template prompt (source
      "template"), no LLM call (saves an API round-trip / cost).
    * korean_freeform given, no key → template fallback (source "fallback_nokey").
    * korean_freeform given, LLM fails → template fallback (source "fallback_error").
    * korean_freeform given, LLM ok → composed English (source "llm").
    """
    base = generate_flow_prompt(country, theme, track_no=track_no,
                                include_person=include_person, form=form)
    freeform = (korean_freeform or "").strip()
    if not freeform:
        base["freeform_ko"] = ""
        base["prompt_source"] = "template"
        return base

    key = _gemini_key()
    if not key:
        base["freeform_ko"] = freeform
        base["prompt_source"] = "fallback_nokey"
        return base

    composed = _call_gemini(_build_llm_instruction(freeform, base, include_person), key)
    base["freeform_ko"] = freeform
    if composed:
        base["main_prompt"] = composed
        base["prompt_source"] = "llm"
    else:
        base["prompt_source"] = "fallback_error"
    return base
