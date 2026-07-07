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
import random

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


# ── 🎲 Korean scene suggestion (mood-aware) ──────────────────────────────────
# Curated Korean city-pop scene descriptions used when no LLM key is available
# (or the LLM call fails). {city} = the country preset's city, {mood} = the
# currently-selected shared mood. These are full free-form-style descriptions,
# not just mood phrases — the point is to seed the Korean input box with a
# ready-to-generate scene the user can then tweak.
_KO_SCENE_PERSON = [
    "{city} 비 오는 밤거리, 단발 보브 헤어에 베이지 트렌치코트를 입은 여성이 카세트 워크맨을 "
    "손에 들고 네온 불빛 아래 서 있음. 젖은 아스팔트에 분홍·파랑 네온이 반사되는 {mood} 무드.",
    "{city} 심야 육교 위, 오버사이즈 가죽 재킷 차림의 여성이 도시 야경을 등지고 카메라를 응시. "
    "머리카락이 바람에 살짝 날리고 뒤로 고층 빌딩 불빛이 보케로 번지는 {mood}.",
    "{city} 자정의 골목, 실크 블라우스에 진주 귀걸이를 한 여성이 공중전화 부스 옆에 기대 서 있음. "
    "따뜻한 창문 불빛과 차가운 네온이 교차하는 {mood} 시티팝 자켓 분위기.",
    "{city} 옥상, 니트 스웨터를 입은 여성이 캔커피를 들고 난간에 기대 도시를 내려다봄. "
    "지평선에 남은 노을과 켜지기 시작한 도시 불빛, {mood} 감성.",
    "{city} 레코드 가게 앞, 데님 재킷의 여성이 LP를 손에 들고 미소. 진열창 네온사인이 얼굴에 "
    "부드럽게 물드는 {mood} 무드.",
]
_KO_SCENE_BG = [
    "{city} 자정의 편의점 앞 골목, 분홍·파랑 네온 간판이 젖은 바닥에 길게 반사되는 시티팝 야경. {mood}.",
    "{city} 고가도로 아래 텅 빈 도로, 지나간 차들의 붉은 라이트 트레일과 신호등 불빛이 번지는 {mood}.",
    "{city} 한강(강변) 야경, 물결에 도시 불빛이 잔잔하게 흔들리고 멀리 다리 조명이 빛나는 {mood} 무드.",
    "{city} 비 그친 뒤 네온 상점가, 물웅덩이에 간판 불빛이 거울처럼 비치는 {mood} 시티팝 배경.",
    "{city} 심야 지하철 플랫폼, 형광등과 노란 조명이 섞인 텅 빈 승강장의 쓸쓸한 {mood} 분위기.",
]


def _country_city(country: str) -> str:
    try:
        from services.thumbnail.country_presets import get_country_preset
        return get_country_preset(country).get("city", "").strip() or "도시"
    except Exception:
        return "도시"


def _build_suggest_instruction(city: str, mood: str, include_person: bool) -> str:
    who = ("장면 중앙에 20대 초반 여성(레트로 시티팝 패션)을 포함하고, 포즈·의상·소품을 "
           "구체적으로." if include_person else "인물 없이 도시 야경/배경 중심으로.")
    return (
        "너는 유튜브 시티팝 플레이리스트 썸네일용 이미지 아이디어를 내는 아트 디렉터야.\n"
        f"도시: {city}\n무드: {mood or '아련한 도시의 밤'}\n"
        "1980~90년대 시티팝 앨범 자켓 감성의 이미지 한 장을 **한국어로 한두 문장** 구체적으로 "
        "묘사해줘. "
        f"{who} "
        "조명·색감·배경 디테일 포함. 글자/로고/워터마크는 넣지 말 것.\n"
        "출력은 묘사 문장만 (따옴표·머리말·설명 없이)."
    )


def suggest_korean_prompt(theme: str, country: str, include_person: bool = True) -> str:
    """
    Suggest ONE Korean free-form scene description in the city-pop mood, based on
    the currently-selected mood (``theme``) and country. Used by the 🎲 button
    next to the Korean input box.

    Gemini when a key is present (richer, varied), else a curated Korean scene
    template (mood/city woven in). Never raises; never logs the key.
    """
    city = _country_city(country)
    mood = (theme or "").strip()
    key = _gemini_key()
    if key:
        out = _call_gemini(_build_suggest_instruction(city, mood, include_person), key)
        if out:
            return out
    # Fallback: curated Korean template.
    pool = _KO_SCENE_PERSON if include_person else _KO_SCENE_BG
    return random.choice(pool).format(city=city, mood=mood or "아련한 도시의 밤")


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
