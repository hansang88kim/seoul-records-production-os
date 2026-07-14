"""
services/youtube/seo_description.py — professional, SEO-optimized YouTube
description generator for Seoul Records city-pop playlists (v1.0.0-alpha.98).

Replaces the old "DJ HANA" fixed frame. The layout the user supplied is kept
verbatim as the skeleton; only the *variable* copy (intro prose, 감성 키워드,
추천 무드, FAQ) is written fresh — by OpenAI→Gemini when a key is present, else
a solid mood-aware template. The TRACKLIST is always taken verbatim from the
real uploaded audio (chapters), never invented, and the copyright block +
hashtags are fixed.

Security: API keys are read from the environment only (never hardcoded, never
logged). On any missing key / LLM failure the template fallback is used.
"""
from __future__ import annotations

import json
import re

from services.youtube.metadata_generator import (
    _format_djhana_tracklist as _format_numbered_tracklist,  # HH:MM:SS  NN. title
)

# ── Mood suggestions (the 🎲 dice next to the 무드 field) ─────────────────────
SEOUL_MOODS: list[str] = [
    "감성 터지는 청량한 여름밤",
    "비 오는 밤 서울 드라이브",
    "네온 가득한 명동의 새벽",
    "쓸쓸한 도시의 밤, 아련한 그리움",
    "한강 노을과 여름 바람",
    "루프탑 바에서 보는 서울 야경",
    "카세트테이프 감성의 레트로 시티팝",
    "혼술하는 을지로 골목의 밤",
    "설레는 첫 데이트, 도시의 불빛",
    "몽환적인 자정의 서울, 디스코 그루브",
    "새벽 감성 산책, 고요한 도시",
    "청량한 대낮의 시티팝, 밝은 나른함",
]


def suggest_mood(avoid: str = "") -> str:
    """One evocative Korean mood phrase for the dice (avoids repeating `avoid`)."""
    import random
    pool = [m for m in SEOUL_MOODS if m.strip() != (avoid or "").strip()] or SEOUL_MOODS
    return random.choice(pool)


# ── Fixed pieces (never LLM) ─────────────────────────────────────────────────
COPYRIGHT_BLOCK = (
    "🎵 저작권 안내\n"
    "이 플레이리스트의 모든 음악과 이미지는 제작자가 AI 제작 도구를 활용해 만든 "
    "오리지널 창작물이며, 공식 발매된 음원입니다.\n\n"
    "무단 복제, 재배포, 재업로드, 편집, 2차 가공 및 상업적 재사용을 금지합니다.\n\n"
    "© All rights reserved. Unauthorized reproduction, distribution, re-uploading, "
    "editing, or secondary use is strictly prohibited."
)

HASHTAGS = (
    "#KoreanCityPop #SeoulCityPop #1980sCityPop #1990sCityPop #서울시티팝 "
    "#한국시티팝 #레트로뮤직 #시티팝플레이리스트 #LP사운드 #CassetteTape "
    "#NeonNights #CityPopPlaylist #명동감성 #을지로밤 #한강드라이브 #DiscoFunk"
)

_DEFAULT_KEYWORDS = ("1980s Nostalgia, Seoul Retro, Neon Night, Summer Night Drive, "
                     "City Pop Vibes, Disco, Funky")
_DEFAULT_MOODS = ("루프탑 바 🌇 / 카페 플레이리스트 ☕ / 여름 드라이브 🚗 / "
                  "한여름 밤 🌙 / 썸머 파티 🎉")


def _tagline_from_mood(mood: str) -> str:
    """Short title tagline. Uses the first clause of the mood, else a default."""
    m = (mood or "").strip()
    if not m:
        return "감성 터지는 청량한"
    # keep it short for the title line
    first = re.split(r"[,·/\n]", m)[0].strip()
    return first[:24] if first else "감성 터지는 청량한"


def generate_seo_title(country: str = "Korea", volume: int = 1, mood: str = "",
                       n_tracks: int = 0, edition: str = "Disco Edition") -> str:
    """The playlist title in the base format (no DJ persona)."""
    tag = _tagline_from_mood(mood)
    n = f" {n_tracks}곡" if n_tracks else ""
    return (f"[Playlist] {tag} 한국 서울 시티팝{n}🎧 | "
            f"Korean Seoul City pop Vol.{volume} | {edition}")


# ── LLM section generation ───────────────────────────────────────────────────
def _sections_prompt(mood: str, volume: int, n_tracks: int) -> str:
    return (
        "You are a professional YouTube SEO copywriter for a Korean CITY-POP "
        "music channel (Seoul Records). Write the variable copy for a PLAYLIST "
        "video description in KOREAN, optimized for YouTube search and discovery.\n"
        "Tone: warm, evocative, tasteful and NATURAL — like a real music "
        "curator. It must NOT sound cheesy, tacky, generic, or AI-written "
        "(촌스럽지 않게, 센스있고 자연스럽게). No clickbait, no exclamation spam.\n"
        "Center EVERYTHING on the given mood/theme so the whole description "
        "clearly reflects it.\n"
        "This is a PLAYLIST of ORIGINAL city-pop songs. Absolutely NO DJ persona, "
        "NO 'DJ', NO 'DJ HANA', NO '믹스셋/mixset' wording.\n\n"
        f"Context:\n- Korean Seoul City Pop, Volume {volume}, {n_tracks} tracks.\n"
        f"- Overall mood / theme (the heart of this playlist): "
        f"\"{(mood or '서울의 밤, 네온, 그리움').strip()}\".\n\n"
        "Return ONLY a JSON object (no markdown, no code fences) with EXACTLY "
        "these keys:\n"
        "- \"intro\": 3-6 short evocative Korean lines about Seoul's night, neon, "
        "and nostalgia that reflect the mood; join the lines with \\n.\n"
        "- \"keywords\": ONE line of 6-9 English emotional SEO keywords, "
        "comma-separated (e.g. \"1980s Nostalgia, Seoul Retro, Neon Night, ...\").\n"
        "- \"moods\": ONE line of 4-6 recommended listening scenes WITH emojis, "
        "separated by ' / ' (e.g. \"루프탑 바 🌇 / 카페 플레이리스트 ☕ / ...\").\n"
        "- \"faq\": an array of EXACTLY 3 objects {\"q\":\"...\",\"a\":\"...\"} — "
        "professional Korean FAQ: (1) what this Seoul city pop is, (2) when it's "
        "good to listen, (3) whether it can be played in a cafe/bar — the answer "
        "MUST note the songs are the creator's original works and forbid "
        "unauthorized reproduction/re-upload/editing.\n\n"
        "Output ONLY the JSON object."
    )


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _llm_sections(mood: str, volume: int, n_tracks: int) -> dict | None:
    """Ask OpenAI→Gemini for the variable sections. None on no-key/failure.
    Reuses the description_translator LLM callers (env-only keys, never logged)."""
    from services.youtube.description_translator import call_llm_raw
    prompt = _sections_prompt(mood, volume, n_tracks)
    raw = call_llm_raw(prompt, json_mode=True)   # RAW sections JSON (not {"translated"})
    data = _extract_json(raw or "")
    if data and data.get("intro") and isinstance(data.get("faq"), list) and len(data["faq"]) >= 3:
        return data
    return None


def _fallback_sections(mood: str, volume: int, n_tracks: int) -> dict:
    """Solid mood-aware template used when no LLM key / LLM fails."""
    m = (mood or "").strip()
    mood_line = f"‘{m}’, 그 감성을 그대로 담았습니다.\n\n" if m else ""
    intro = (
        f"서울의 밤, 네온, 그리고 오래 남은 그리움이 흐르는\n"
        f"한국형 시티팝 컬렉션입니다.\n\n"
        f"{mood_line}"
        f"남산 너머로 번지는 저녁빛, 한강 위로 스치는 바람,\n"
        f"을지로와 명동, 혜화와 청계천 사이로 번지는 도시의 불빛.\n\n"
        f"1980~1990년대의 레트로한 감성과 카세트테이프의 질감, LP 사운드의 따뜻함,\n"
        f"그리고 부드러운 디스코·펑크 그루브를 담아 서울의 밤을 다시 그려냈습니다."
    )
    faq = [
        {"q": "서울 시티팝은 어떤 음악인가요?",
         "a": "1980~1990년대의 레트로 감성을 바탕으로, 서울의 밤과 도시적 정서를 "
              "현대적으로 재해석한 한국형 시티팝입니다. 신스, 펑크, 재즈, 소울의 질감을 "
              "섞어 빈티지하면서도 세련된 분위기를 담았습니다."},
        {"q": "언제 듣기 좋은 플레이리스트인가요?",
         "a": "야경 드라이브, 새벽 산책, 혼술, 카페 BGM, 루프탑 바, 여름밤 플레이리스트로 "
              "잘 어울립니다. 서울의 네온과 한강 바람, 오래된 골목의 분위기를 떠올리며 "
              "들으면 더 깊게 즐길 수 있습니다."},
        {"q": "카페나 Bar에서 재생해도 되나요?",
         "a": "이 플레이리스트의 모든 곡은 제작자의 오리지널 창작곡입니다. 매장 분위기 "
              "연출용 BGM으로 자유롭게 감상하실 수 있습니다. 단, 음원의 무단 복제, "
              "재업로드, 배포, 편집 및 2차 가공은 금지됩니다."},
    ]
    return {"intro": intro, "keywords": _DEFAULT_KEYWORDS,
            "moods": _DEFAULT_MOODS, "faq": faq}


def _assemble(sections: dict, chapters: list[dict], n_tracks: int) -> str:
    tracklist = _format_numbered_tracklist(chapters) or (
        "00:00:00  01. (트랙 정보는 업로드된 음원 기준으로 자동 생성됩니다)")
    faq = sections.get("faq", [])[:3]
    faq_lines = []
    for i, item in enumerate(faq, start=1):
        q = str(item.get("q", "")).strip()
        a = str(item.get("a", "")).strip()
        faq_lines.append(f"Q{i}. {q}\nA. {a}")
    faq_block = "\n\n".join(faq_lines)

    return (
        f"{sections.get('intro', '').strip()}\n\n"
        f"🏖️ 감성 키워드\n{sections.get('keywords', _DEFAULT_KEYWORDS).strip()}\n\n"
        f"🎧 추천 무드\n{sections.get('moods', _DEFAULT_MOODS).strip()}\n\n"
        f"🎶 총 {n_tracks}곡 연속 재생 (Full Playlist)\n\n"
        f"🎧 Seoul City Pop / Retro Korean City Pop Playlist\n\n"
        f"{tracklist}\n\n"
        f"FAQ 자주 묻는 질문\n\n"
        f"{faq_block}\n\n"
        f"{COPYRIGHT_BLOCK}\n\n"
        f"{HASHTAGS}"
    )


def generate_seo_description(chapters: list[dict] | None = None, mood: str = "",
                            country: str = "Korea", volume: int = 1,
                            use_llm: bool = True) -> str:
    """Full SEO description in the fixed base layout (DJ HANA removed).

    Variable prose is LLM-written (OpenAI→Gemini) when a key is present and
    ``use_llm`` is True; otherwise a mood-aware template. The tracklist is taken
    verbatim from ``chapters`` (real uploaded audio)."""
    chapters = chapters or []
    n = len(chapters)
    sections = (_llm_sections(mood, volume, n) if use_llm else None) \
        or _fallback_sections(mood, volume, n)
    return _assemble(sections, chapters, n)
