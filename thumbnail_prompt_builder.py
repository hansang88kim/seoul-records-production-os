# -*- coding: utf-8 -*-
"""
Seoul Records — 썸네일 형태별 이미지 생성 프롬프트 빌더
Gemini(Nano Banana) / GPT-Image 등 text-to-image 모델용.

핵심 원칙
 1) 형태(A~F)마다 '구도 제약'이 다르다 → 프롬프트에 강제 주입해야 텍스트 합성이 맞음
 2) 브랜드 무드(시티팝/네온/90s 노스탤지어)는 항상 공통으로 얹는다
 3) 이미지에 글자를 그리면 안 된다 → negative에 'no text/letters/watermark' 필수
 4) 16:9와 1:1은 네거티브 스페이스 위치가 다르다 → 비율별로 살짝 다르게
"""

from dataclasses import dataclass, field
from typing import Literal

# ─────────────────────────────────────────────
# 공통 브랜드 무드 (모든 형태 공유 — 브랜딩 align의 핵심)
# ─────────────────────────────────────────────
BRAND_STYLE = (
    "1980s–1990s Japanese city-pop aesthetic, nostalgic late-night Seoul/Tokyo mood, "
    "cinematic neon lighting with magenta and cyan glow plus warm tungsten amber, "
    "moody film-grain texture, soft bokeh, shallow depth of field, "
    "rich saturated color grade, analog nostalgic atmosphere, editorial photography, "
    "high detail, professional color grading"
)

# 이미지에 글자가 들어가면 HTML 텍스트와 충돌 → 항상 배제
NEGATIVE = (
    "no text, no letters, no words, no typography, no captions, no watermark, "
    "no logo, no signature, no frame, no border, not cartoon, not illustration, "
    "no distorted faces, no extra limbs"
)

# ─────────────────────────────────────────────
# 형태별 정의: 피사체 + 구도 제약 + 추천 종횡비별 여백 위치
# ─────────────────────────────────────────────
FORM_SPECS = {
    "A": {
        "name": "인물형 (Portrait / Subject)",
        "subject_default": (
            "a single stylish woman in her 20s with an androgynous elegant look, "
            "short black bob or long hair, beige trench coat, sitting in a car at night "
            "lit by colorful neon reflections, looking slightly away from camera, "
            "cinematic portrait"
        ),
        "composition_169": (
            "subject centered in the middle third of the frame, "
            "generous empty negative space on the LEFT and RIGHT sides for large title text, "
            "head and shoulders around vertical center, "
            "eye-level cinematic framing"
        ),
        "composition_11": (
            "subject centered but shifted slightly right, "
            "negative space kept on the LEFT for a vertical spine, "
            "full head visible, not cropped at the top"
        ),
    },
    "B": {
        "name": "배경형 (Scenery / Establishing)",
        "subject_default": (
            "a wide atmospheric night cityscape of Seoul or Tokyo, "
            "rainy neon streets, glowing signage, distant traffic light trails, "
            "no people in the foreground"
        ),
        "composition_169": (
            "wide establishing shot, "
            "clear darker negative space across the CENTER and LOWER-CENTER for stacked title text, "
            "leading lines drawing toward the middle, balanced horizon"
        ),
        "composition_11": (
            "square framing of the cityscape, "
            "darker calmer area in the CENTER for a stacked title, "
            "keep left edge simpler for an optional spine"
        ),
    },
    "C": {
        "name": "오브젝트 교차형 (Object cross-over)",
        "subject_default": (
            "a single hero object on a table at night — "
            "a tall glass of iced coffee or a vintage cassette walkman or a cocktail glass — "
            "dramatic side lighting, dark moody background with soft neon glow"
        ),
        "composition_169": (
            "the hero object placed exactly in the CENTER of the frame, "
            "wide empty negative space on the far LEFT and far RIGHT for two big words, "
            "object tall enough to overlap where title text sits, dark background"
        ),
        "composition_11": (
            "hero object centered and prominent, "
            "empty space above and below for stacked title words, dark background"
        ),
    },
    "D": {
        "name": "라벨 뱃지형 (Badge / Label)",
        "subject_default": (
            "a cozy dim night interior — a warmly lit bedroom or a quiet cafe corner "
            "with a single lamp glow, calm intimate late-night mood"
        ),
        "composition_169": (
            "calm symmetric composition, "
            "clear empty space at the TOP-CENTER for a small oval badge, "
            "and a clean horizontal band across the LOWER-MIDDLE for a large title, "
            "soft vignette"
        ),
        "composition_11": (
            "symmetric cozy interior, "
            "empty space at TOP for a badge and CENTER band for the title"
        ),
    },
    "E": {
        "name": "플랫레이형 (Flat-lay / Top-down)",
        "subject_default": (
            "a top-down flat-lay of a vintage turntable with a vinyl record, "
            "or a retro desk with cassette tapes, headphones and coffee, "
            "warm wooden or dark surface, neat arrangement"
        ),
        "composition_169": (
            "perfectly top-down bird's-eye view, "
            "central object with symmetric empty margins on LEFT and RIGHT for two big words, "
            "even soft lighting"
        ),
        "composition_11": (
            "top-down square flat-lay, object centered, "
            "even margins for a title band, symmetric"
        ),
    },
    "F": {
        "name": "아치형 (Arch / Curved title)",
        "subject_default": (
            "an atmospheric night cityscape or a single subject with a clean upper area, "
            "neon city-pop mood"
        ),
        "composition_169": (
            "keep a wide clean CURVED horizontal band across the vertical center empty, "
            "so an arched title can sit over it, "
            "visual interest kept to top and bottom edges"
        ),
        "composition_11": (
            "clean curved central band left empty for an arched title, "
            "detail concentrated at top and bottom"
        ),
    },
}

ASPECT = {"169": "16:9 aspect ratio, horizontal", "11": "1:1 square aspect ratio"}


@dataclass
class ThumbnailPromptRequest:
    form: Literal["A", "B", "C", "D", "E", "F"]
    ratio: Literal["169", "11"] = "169"
    subject_override: str | None = None   # 사용자가 피사체를 직접 지정하면 우선
    mood_extra: str = ""                  # 예: "winter snow", "summer beach"


def build_image_prompt(req: ThumbnailPromptRequest) -> dict:
    spec = FORM_SPECS[req.form]
    subject = req.subject_override or spec["subject_default"]
    comp = spec[f"composition_{req.ratio}"]
    mood = f"{BRAND_STYLE}, {req.mood_extra}".strip(", ") if req.mood_extra else BRAND_STYLE

    prompt = (
        f"{subject}. "
        f"{comp}. "
        f"{mood}. "
        f"{ASPECT[req.ratio]}."
    )
    return {
        "form": req.form,
        "form_name": spec["name"],
        "ratio": req.ratio,
        "prompt": prompt,
        "negative_prompt": NEGATIVE,
        # 각 provider별 힌트
        "gemini_hint": {"aspect_ratio": "16:9" if req.ratio == "169" else "1:1"},
        "gpt_image_hint": {"size": "1536x1024" if req.ratio == "169" else "1024x1024"},
    }


if __name__ == "__main__":
    import json
    # 데모: 6형태 × 16:9 프롬프트 생성
    for form in ["A", "B", "C", "D", "E", "F"]:
        out = build_image_prompt(ThumbnailPromptRequest(form=form, ratio="169"))
        print("="*70)
        print(f"[{out['form']}] {out['form_name']}  ({out['ratio']})")
        print("PROMPT:", out["prompt"])
        print("NEG   :", out["negative_prompt"][:60], "...")
    print("="*70)
    # 데모: 사용자가 피사체 오버라이드 + 무드 추가
    custom = build_image_prompt(ThumbnailPromptRequest(
        form="A", ratio="11",
        subject_override="a young Korean man in his 20s, leather jacket, standing under neon signage",
        mood_extra="rainy winter night"))
    print("\n[커스텀 예시 - A형 1:1, 피사체/무드 오버라이드]")
    print(custom["prompt"])
