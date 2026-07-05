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


# Curated city-pop concept phrases (keyword-forward, Korean). These match
# the Seoul Records mood: nostalgic, bittersweet, late-night, urban.
CITYPOP_CONCEPTS: list[str] = [
    "비 오는 서울 밤",
    "이별 후 택시 안에서",
    "루프탑에서 보는 야경",
    "막차를 놓친 새벽",
    "네온 불빛 골목길",
    "한강 다리 위 드라이브",
    "혼자 걷는 을지로 밤거리",
    "오래된 카세트테이프 속 추억",
    "첫사랑이 스치는 지하철역",
    "새벽 편의점 불빛",
    "옥탑방 창밖의 도시",
    "젖은 아스팔트에 번지는 불빛",
    "떠나간 사람의 향수",
    "야근 후 텅 빈 사무실",
    "여름밤 열대야의 도시",
    "낡은 레코드 가게",
    "가로등 아래 마지막 인사",
    "창문에 흐르는 빗방울",
    "심야 라디오 주파수",
    "노을 지는 퇴근길",
    "명동에서 종로까지 밤산책",
    "성수동 골목의 새벽",
    "택시 창밖으로 흐르는 도시",
    "혼자만의 밤 드라이브",
    "잊혀진 여름의 끝자락",
    "도시의 불빛과 외로움",
    "빈 방에 남은 담배 연기",
    "한밤중 고속도로 위",
    "재개발 앞둔 오래된 동네",
    "새벽 감성의 무드등",
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


def next_concept(seed_state: dict, avoid: str = "") -> str:
    """
    Return the next single concept keyword/phrase, cycling through a
    shuffled ordering without immediate repeats. `avoid` (usually the
    currently shown concept) is skipped if it would be returned again.
    """
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
