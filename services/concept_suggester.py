"""
services/concept_suggester.py — v1.0.0-alpha.61

Suggest a single city-pop-appropriate concept keyword/phrase at a time
(a "variation" the user can cycle through) for the AI Composer's concept
field. The goal: instead of the user staring at an empty box, they press
🎲 변주 and get one evocative, on-brand concept to write a song around —
one at a time so it stays focused.

The suggestions are seeded from a curated Korean pool tuned to the Seoul
Records "nostalgic late-night city pop" identity (rainy Seoul nights,
after a breakup, Han river, rooftop views, neon alleys, last trains,
etc.). Each suggestion is a short concept phrase, keyword-forward, never a
full sentence.

We keep this deterministic-but-cycling: repeated presses walk through a
shuffled ordering without immediate repeats, so the user always gets
something new. An optional AI path (OpenAI/Gemini) can expand the pool,
but the curated pool guarantees this works with zero API keys.
"""
from __future__ import annotations

import random


# v1.0.0-alpha.104: the old pool was ALL one tone (late-night / breakup /
# loneliness / neon), so every 🎲 felt the same. Diversified across the modern
# Seoul lyric themes (see providers/ai/base LYRICS THEME/MOOD) so each press
# gives a genuinely different SUBJECT — city change, 20s worries, love (many
# angles), everyday moments, nostalgia, self-comfort, plus some night/summer.
CITYPOP_CONCEPTS: list[str] = [
    # 급변하는 도시 속 현대인의 애환
    "재개발로 사라진 골목", "월세 오른 옥탑방", "정든 가게가 문 닫던 날",
    "낯설어진 내 동네", "출퇴근 2호선 사람들", "이직 사이의 빈 며칠",
    "낡은 간판이 내려지던 밤",
    # 20대의 고민
    "스물다섯의 갈림길", "면접을 마치고 나온 길", "취준생의 새벽",
    "혼자 상경한 첫 서울", "비교에 지친 밤", "꿈과 월급 사이", "첫 월급날의 씁쓸함",
    # 연애와 사랑 (다양한 각도)
    "설레는 첫 데이트", "읽씹당한 새벽", "오래된 연인의 권태", "썸의 애매한 거리",
    "헤어지자는 말 대신", "다시 만난 첫사랑", "짝사랑하던 그 계절",
    # 일상의 작은 순간
    "퇴근길 편의점 맥주", "친구의 늦은 안부 전화", "혼밥하는 저녁",
    "빨래 널며 듣는 라디오", "주말 오후의 나른함", "야근 후 텅 빈 사무실",
    # 그리움 / 향수
    "졸업하던 봄", "고향집 가는 기차", "옛 친구들 생각", "스무 살의 여름",
    "오래된 카세트테이프 속 추억",
    # 위로와 다짐
    "오늘도 잘 버텼다", "다시 시작하는 월요일", "괜찮아질 거라는 말",
    # 밤 · 여름 시티팝 무드
    "비 오는 서울 밤", "한강 다리 위 드라이브", "루프탑에서 보는 야경",
    "막차를 놓친 새벽", "네온 불빛 골목길", "한여름 밤의 해방", "장마 끝 파란 하늘",
    "여름 바다로 가는 길", "노을 지는 퇴근길",
]

# Theme hints the LLM path rotates through so freshly-generated concepts also
# span the full range (not just night/loneliness).
_THEME_CATEGORIES: list[str] = [
    "90년대 이후 급변하는 서울에서 적응하며 사는 현대인의 애환",
    "20대의 고민(취업·미래·상경·비교·정체성)",
    "연애와 사랑(설렘·권태·이별·재회·짝사랑 등 다양한 각도)",
    "일상의 작고 소중한 순간",
    "그리움과 향수(계절·고향·옛 친구·어린 나)",
    "지친 하루 끝의 위로와 작은 다짐",
    "청량한 한여름의 해방감",
]


def _shuffled_cycle(seed_state: dict) -> list[str]:
    """
    Maintain a shuffled ordering in seed_state so repeated calls walk
    through all concepts before repeating. seed_state is a plain dict the
    caller persists (e.g. st.session_state).
    """
    order = seed_state.get("_concept_order")
    idx = seed_state.get("_concept_idx", 0)
    if not order or idx >= len(order):
        order = CITYPOP_CONCEPTS[:]
        random.shuffle(order)
        idx = 0
        seed_state["_concept_order"] = order
        seed_state["_concept_idx"] = 0
    return order


def _llm_fresh_concept(avoid: str = "") -> str:
    """v1.0.0-alpha.104: generate a genuinely FRESH concept via OpenAI→Gemini,
    rotating across the theme categories so each 🎲 press differs. Returns "" on
    no-key/failure (caller falls back to the diverse pool). Env-only keys, never
    logged. Reuses the description_translator LLM callers."""
    try:
        from services.youtube.description_translator import call_llm_raw
    except Exception:
        return ""
    cat = random.choice(_THEME_CATEGORIES)
    prompt = (
        "한국 시티팝 노래의 '컨셉'을 딱 한 줄 새로 지어줘.\n"
        f"주제 방향: {cat}.\n"
        "조건: 90년대 중후반 서울 배경, 6~16자 한국어 키워드형 문구(완결 문장 아님), 진부한 표현 금지, "
        "따옴표/설명/번호 없이 그 문구 한 줄만 출력."
        + (f" '{avoid}'와는 다른 새로운 걸로." if avoid else "")
    )
    raw = (call_llm_raw(prompt, json_mode=False) or "").strip()  # plain one-liner
    if raw:
        line = raw.splitlines()[0].strip().strip('"').strip("'").strip()
        if 2 <= len(line) <= 24 and line != avoid:
            return line
    return ""


def next_concept(seed_state: dict, avoid: str = "", use_llm: bool = True) -> str:
    """
    Return one concept keyword/phrase. v1.0.0-alpha.104: when `use_llm` and an
    LLM key is present, each press GENERATES a fresh concept (rotating themes) so
    the dice never feels repetitive; otherwise it cycles a shuffled ordering of
    the diverse curated pool without immediate repeats. `avoid` (the currently
    shown concept) is skipped. (`use_llm=False` keeps it pool-only + deterministic
    for tests, independent of any env key.)
    """
    if use_llm:
        fresh = _llm_fresh_concept(avoid)
        if fresh:
            return fresh

    order = _shuffled_cycle(seed_state)
    idx = seed_state.get("_concept_idx", 0)

    concept = order[idx]
    idx += 1
    # Skip an immediate repeat of `avoid`.
    if concept == avoid and len(order) > 1:
        if idx >= len(order):
            random.shuffle(order)
            seed_state["_concept_order"] = order
            idx = 0
        concept = order[idx]
        idx += 1

    seed_state["_concept_idx"] = idx
    return concept


def suggest_many(n: int = 5) -> list[str]:
    """Return n distinct random concepts (for a dropdown / preview)."""
    n = max(1, min(n, len(CITYPOP_CONCEPTS)))
    return random.sample(CITYPOP_CONCEPTS, n)
