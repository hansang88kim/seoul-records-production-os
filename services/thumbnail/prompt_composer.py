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

# v1.0.0-alpha.79: every Korean prompt (typed or 🎲-suggested) should read as a
# thumbnail for a city-pop YouTube music-playlist channel — 16:9, with a subtle
# nostalgic VHS analog-filter mood. This Korean tail is appended to suggestions;
# the English equivalent is woven into the composed prompt and its fallback.
KO_THUMBNAIL_SUFFIX = (
    "16:9 비율, 시티팝 감성의 유튜브 음악 플레이리스트 채널 썸네일, "
    "은은한 VHS 아날로그 필터의 감성적인 무드"
)
_EN_THUMBNAIL_FRAMING = (
    " Styled as a nostalgic 1980s-1990s city-pop YouTube music-playlist "
    "thumbnail with a subtle VHS analog-film filter aesthetic — soft grain, "
    "gentle chromatic haze, warm nostalgic color grade — while keeping the "
    "subject sharp and the composition clean and readable at small thumbnail "
    "size, 16:9 aspect ratio."
)


def _append_ko_suffix(text: str) -> str:
    t = (text or "").rstrip()
    if not t:
        return t
    # avoid doubling if the model already added the framing
    if "썸네일" in t and "VHS" in t.upper():
        return t
    sep = " — " if not t.endswith((".", "。", "!", "?", "…")) else " "
    return f"{t}{sep}{KO_THUMBNAIL_SUFFIX}."


def _gemini_key() -> str | None:
    for var in ("GOOGLE_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        v = os.environ.get(var, "").strip()
        if v:
            return v
    return None


def _openai_key() -> str | None:
    v = os.environ.get("OPENAI_API_KEY", "").strip()
    return v or None


def _any_llm_key() -> bool:
    return bool(_openai_key() or _gemini_key())


def _call_llm(instruction: str) -> str | None:
    """
    Compose via the best available LLM. OpenAI (gpt-4o-mini class) tends to write
    the most detailed, professional image prompts, so it's tried first; Gemini is
    the fallback. Returns the composed text, or None if no key / both fail.
    Never logs the key.
    """
    ok = _openai_key()
    if ok:
        out = _call_openai(instruction, ok)
        if out:
            return out
    gk = _gemini_key()
    if gk:
        out = _call_gemini(instruction, gk)
        if out:
            return out
    return None


def _build_llm_instruction(korean_freeform: str, base: dict, include_person: bool,
                           art_style: str = "") -> str:
    """Assemble the instruction sent to Gemini. ``base`` is a generate_flow_prompt
    dict (used as the style/composition reference). ``art_style`` (v1.0.0-alpha.96,
    one of THUMB_ART_STYLES) sets the render look — default anime per the YouTube
    tokyo-citypop thumbnail benchmark."""
    from services.thumbnail.prompt_generator import art_render, DEFAULT_THUMB_ART_STYLE
    _style = (art_style or DEFAULT_THUMB_ART_STYLE)
    art_rule = art_render(_style)
    is_anime = _style == "anime"
    is_doc = _style in ("documentary", "analog")
    craft_rule = (
        "Render as a clean cel-shaded 1980s-90s city-pop ANIME/MANGA illustration "
        "— crisp linework, flat nostalgic color blocking, stylized cel-shaded "
        "lighting with warm neon glow and gentle rim light, retro anime aesthetic "
        "(Hiroshi Nagai / Eizin Suzuki album-art vibe), NOT a photo, NOT 3D, no "
        "camera/lens realism; finish with a subtle retro-print grain."
        if is_anime else
        "Shoot it like a HYPER-REAL DOCUMENTARY photograph on analogue 35mm Kodak "
        "color film — candid and unposed, a natural lens feel (35mm, shallow depth "
        "of field), soft natural warm lighting, close-up macro everyday details, a "
        "glossy golden 'olive-oil' summer glow, fine film grain. Realistic, not "
        "staged glamour."
        if is_doc else
        "Include concrete craft detail woven naturally: a specific camera/lens feel "
        "(35mm/50mm, shallow depth of field, cinematic anamorphic), lighting design "
        "(key/rim/practical light, wet reflections, volumetric haze, bokeh), rich "
        "atmosphere and texture, finished with a subtle analog-film mood."
    )
    subject_rule = (
        "Include a beautiful woman in her early twenties as the centered subject, "
        "caught in a REAL everyday moment — candid and unposed, natural minimal makeup, "
        "NOT a studio glamour or costume look. Vary the wardrobe naturally (a simple "
        "summer dress, knitwear, a blazer, a trench, denim, etc.)."
        if include_person else
        "Background only — no people facing the camera."
    )
    form_comp = base.get("form_composition")
    composition_rule = (
        form_comp if form_comp
        else "balanced negative space near a title-safe band for a text overlay"
    )
    return (
        "You are a world-class prompt engineer for AI image generators "
        "(Midjourney, Google Nano Banana, GPT-Image), specializing in premium "
        "Korean/Asian YouTube music-playlist thumbnails.\n\n"
        "Write ONE richly detailed, professional English image-generation prompt "
        "as a single flowing paragraph (roughly 60-110 words — no line breaks, no "
        "markdown, no preamble, no quotes, no parameter flags like --ar). It must "
        "read like a top-tier prompt that renders beautifully across Midjourney, "
        "Nano Banana, and GPT-Image alike.\n\n"
        f"The user described, in Korean, what they want in the image:\n"
        f"\"{korean_freeform.strip()}\"\n\n"
        "Requirements you MUST honor:\n"
        "- Faithfully and specifically reflect the user's description (their "
        "subject, poses, wardrobe, props, setting, and mood) — expand it with "
        "concrete, evocative visual detail rather than restating it.\n"
        f"- Country / setting: {base.get('country', '')} — {base.get('scene', '')}.\n"
        f"- Mood / theme: {base.get('theme', '') or 'warm everyday-life summer'}.\n"
        f"- Style: premium, tasteful YouTube music-playlist thumbnail — natural and "
        f"cinematic, NOT gaudy, NOT oversaturated. {art_rule}\n"
        f"- {subject_rule}\n"
        f"- Composition constraint (keep this): {composition_rule}.\n"
        "- Give the street natural life: warm glowing neon signboards and a few "
        "softly out-of-focus passersby in the background — lively but not cluttered, "
        "the subject stays clearly dominant and the title-safe area stays clean.\n"
        f"- {craft_rule} Use a warm Kodak-film color palette (amber, honey, golden "
        f"'olive-oil' summer tones) with rich nostalgic atmosphere.\n"
        "- The image MUST contain no text, letters, logos, or watermarks.\n"
        "- Finished as a warm, documentary everyday-life YouTube music-playlist "
        "THUMBNAIL — crisp and readable at small thumbnail size, 16:9 aspect ratio.\n\n"
        "Output ONLY the final English prompt paragraph — nothing else."
    )


def _call_openai(instruction: str, api_key: str) -> str | None:
    """Compose via OpenAI chat completions (plain-text prose). None on failure.
    Never logs the key."""
    try:
        import requests
        model = os.environ.get("SEOUL_PROMPT_LLM_MODEL_OPENAI", "gpt-4o-mini")
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content":
                     "You are a world-class prompt engineer for AI image generators "
                     "(Midjourney, Google Nano Banana, GPT-Image). You write vivid, "
                     "technically detailed, production-ready prompts."},
                    {"role": "user", "content": instruction},
                ],
                "max_tokens": 1500,
                "temperature": 0.9,
            },
            timeout=60,
        )
        if resp.status_code != 200:
            logger.warning("Prompt compose: OpenAI HTTP %s", resp.status_code)
            return None
        data = resp.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return _clean(text) or None
    except Exception as e:
        logger.warning("Prompt compose: OpenAI call failed: %s", type(e).__name__)
        return None


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
                  "generationConfig": {"maxOutputTokens": 1500, "temperature": 0.9}},
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


# Tasteful, DIVERSE wardrobe seeds — one is injected at random into the 🎲
# suggestion instruction so each press yields a different, modern-elegant look
# instead of the same gaudy retro cliché (off-shoulder + high-waist jeans +
# leopard earrings). The model is told to treat it as a starting point, not a rule.
_KO_STYLE_SEEDS = [
    "베이지 트렌치코트에 심플한 터틀넥",
    "오버사이즈 니트 스웨터와 슬랙스",
    "테일러드 블레이저 안에 실크 블라우스",
    "미니멀한 새틴 슬립 드레스",
    "데님 재킷과 무지 티셔츠의 편안한 스타일",
    "파스텔 카디건과 미디스커트",
    "라이트 코트에 니트, 얇은 머플러",
    "모던한 셋업 정장(재킷+팬츠)",
    "부드러운 셔츠 원피스",
    "심플한 크롭 니트와 롱스커트",
]


def _build_suggest_instruction(city: str, mood: str, include_person: bool) -> str:
    if include_person:
        style_seed = random.choice(_KO_STYLE_SEEDS)
        who = (
            "장면 중앙에 20대 초반 여성을 배치하되, 패션은 감성적이고 세련된 시티팝 무드로 —\n"
            "과하거나 촌스러운 레트로 클리셰(화려한 패턴 블라우스, 호피/표범 무늬, 오프숄더+하이웨이스트 "
            "청바지, 큼지막한 액세서리 같은 뻔한 조합)는 피하고, 우아하고 절제된 현대적 감각으로.\n"
            f"이번 착장의 핵심은 반드시 '{style_seed}' 계열로 구성할 것 (색·소재·디테일은 자유롭게 "
            "변형하되 이 방향을 벗어나지 말 것) — 데님 재킷+티셔츠 같은 뻔한 기본 조합으로 매번 "
            "수렴하지 말고. 헤어·의상·소품·포즈를 자연스럽고 구체적으로 묘사."
        )
    else:
        who = "인물 없이 도시 야경/배경 중심으로 묘사."
    return (
        "너는 유튜브 시티팝 음악 플레이리스트 썸네일을 기획하는 감각적인 아트 디렉터야.\n"
        f"도시: {city}\n무드: {mood or '아련한 도시의 밤'}\n"
        "감성적인 1980~90년대 시티팝 무드의 이미지 한 장을 **한국어로 두세 문장** 아주 구체적으로 "
        "묘사해줘 (과한 레트로 코스튬 느낌은 지양, 세련되고 절제된 톤). "
        f"{who} "
        "주변에는 은은하게 빛나는 네온 간판과 멀리 흐릿하게 지나가는 행인 몇 명으로 거리에 "
        "자연스러운 생기를 더하되(주인공보다 부각되지 않게, 어수선하지 않게). "
        "조명(네온·젖은 반사·역광·보케), 색감(틸/마젠타 또는 앰버/시안 야간 톤), 카메라 느낌"
        "(얕은 심도, 시네마틱), 분위기·질감 디테일을 풍부하게 넣되 자연스러운 문장으로. "
        "화면에 오버레이될 큰 글자/로고/워터마크는 넣지 말 것.\n"
        "출력은 묘사 문장만 (따옴표·머리말·설명·목록 없이)."
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
    if _any_llm_key():
        out = _call_llm(_build_suggest_instruction(city, mood, include_person))
        if out:
            return _append_ko_suffix(out)
    # Fallback: curated Korean template.
    pool = _KO_SCENE_PERSON if include_person else _KO_SCENE_BG
    scene = random.choice(pool).format(city=city, mood=mood or "아련한 도시의 밤")
    return _append_ko_suffix(scene)


def compose_english_prompt(
    korean_freeform: str,
    country: str,
    theme: str,
    include_person: bool = True,
    form: str | None = None,
    track_no: int = 0,
    art_style: str = "",
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
    from services.thumbnail.prompt_generator import DEFAULT_THUMB_ART_STYLE
    _art = (art_style or "").strip() or DEFAULT_THUMB_ART_STYLE
    base = generate_flow_prompt(country, theme, track_no=track_no,
                                include_person=include_person, form=form,
                                art_style=_art)
    freeform = (korean_freeform or "").strip()
    if not freeform:
        base["freeform_ko"] = ""
        base["prompt_source"] = "template"
        return base

    # Freeform flow → subtle-VHS city-pop thumbnail look: relax the anti-VHS
    # negatives so they don't cancel the aesthetic (alpha.79).
    from services.thumbnail.prompt_generator import relax_vhs_negatives
    base["negative_prompt"] = relax_vhs_negatives(base["negative_prompt"])

    if not _any_llm_key():
        base["main_prompt"] = base["main_prompt"] + _EN_THUMBNAIL_FRAMING
        base["freeform_ko"] = freeform
        base["prompt_source"] = "fallback_nokey"
        return base

    composed = _call_llm(_build_llm_instruction(freeform, base, include_person, art_style=_art))
    base["freeform_ko"] = freeform
    if composed:
        base["main_prompt"] = composed  # LLM already weaves in the thumbnail/VHS framing
        base["prompt_source"] = "llm"
    else:
        base["main_prompt"] = base["main_prompt"] + _EN_THUMBNAIL_FRAMING
        base["prompt_source"] = "fallback_error"
    return base
