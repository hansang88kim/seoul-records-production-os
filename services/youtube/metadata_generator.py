"""
services/youtube/metadata_generator.py — YouTube metadata (v0.8.0).

Generates title, description, tags, hashtags, pinned comment, and a YouTube
chapters section from the playlist info + chapters.txt. No clickbait, clean
music-channel format. Korean titles preserved (no mojibake).
"""
from __future__ import annotations

import re
from pathlib import Path


CHANNEL_NAME = "Seoul Records"


def _clean_filename_title(name: str) -> str:
    """Turn a filename into a readable title (fallback when no metadata)."""
    base = Path(name).stem
    base = base.replace("_", " ").replace("-", " ")
    base = re.sub(r"\s+", " ", base).strip()
    return base


def parse_chapters_txt(chapters_path: str) -> list[dict]:
    """
    Parse a chapters.txt (lines like '00:00 Title' or '1:23:45 Title').
    Returns [{timestamp, title}] preserving order and exact timestamps.
    """
    entries = []
    p = Path(chapters_path)
    if not p.exists():
        return entries
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$", line)
        if m:
            entries.append({"timestamp": m.group(1), "title": m.group(2).strip()})
    return entries


def generate_title(playlist_title: str, country: str = "", volume: int = 1,
                   duration_min: int = 60, mood: str = "") -> str:
    """
    Generate a clean YouTube title. Includes CityPop / Playlist / Vol.
    Avoids clickbait and excessive hashtags.

    Examples:
      CityPop Playlist Vol.1 · 60 Minutes of Seoul Night Drive
      Korea CityPop Playlist Vol.1 · Rainy Night Drive
    """
    # Base playlist label
    if playlist_title:
        base = playlist_title
    elif country:
        base = f"{country} CityPop Playlist Vol.{volume}"
    else:
        base = f"CityPop Playlist Vol.{volume}"

    # Subtitle (mood or duration)
    if mood:
        subtitle = mood
    elif duration_min:
        subtitle = f"{duration_min} Minutes of City Night Drive"
    else:
        subtitle = "Late Night Playlist"

    title = f"{base} · {subtitle}"
    # Keep it reasonable (YouTube hard cap 100 chars)
    return title[:100]


def generate_tags(country: str = "", mood: str = "", volume: int = 1) -> list[str]:
    """
    v1.0.0-alpha.60: SEO-optimised FIXED tag set, always in English.

    The tags are now a curated, stable list tuned for city-pop / playlist
    discovery on YouTube, targeting ~400-490 characters of the 500-char
    budget (previously only ~180 chars, which under-used the space). Tags
    stay in English regardless of the song's lyric language — only the
    title/description get localised (see the translation option) — because
    English tags reach the widest city-pop search audience.

    The list is intentionally fixed (not randomised) so every upload is
    consistently indexed under the same high-value keywords. country/mood/
    volume are accepted for backwards-compat and lightly folded in, but the
    core SEO set does the heavy lifting.
    """
    core = [
        # primary genre / intent (highest value, must always survive)
        "citypop", "city pop", "citypop playlist", "city pop playlist",
        "playlist", "music playlist", "citypop mix", "city pop mix",
        # brand / channel (must always survive)
        "seoul records", "seoul citypop", "seoul city pop", "korean citypop",
        # mood / usage (high-search long-tail)
        "nostalgic", "night drive", "night drive music", "chill", "chill music",
        "chill playlist", "relaxing music", "study music", "work music",
        "late night music", "aesthetic", "vaporwave", "lofi", "lofi citypop",
        # sub-genre / era
        "japanese citypop", "japanese city pop", "80s citypop", "80s city pop",
        "80s music", "retro music", "retro citypop", "synthwave",
        "nu disco", "disco house", "funk", "smooth jazz",
        # extra discovery long-tail
        "k citypop", "asian citypop", "citypop for driving", "citypop night",
        "neon night", "tokyo night", "seoul night", "summer citypop",
        "sunset drive", "rooftop lounge",
    ]

    # Light, optional folding of dynamic context (kept English). A mood is
    # only folded into tags when it's ASCII/English — Korean moods stay out
    # so the tag set remains all-English (alpha.60 rule).
    extras = []
    if country:
        c = country.strip().lower()
        extras += [f"{c} citypop", f"{c} playlist", f"{c} city pop"]
    if mood and mood.strip().isascii():
        extras.append(mood.strip().lower())
    extras.append(f"citypop vol {volume}")

    # Dedupe (case-insensitive), preserve order. Dynamic extras (mood /
    # country) go FIRST so they always survive the 490-char trim — the
    # curated core then fills the remaining budget.
    seen = set()
    ordered = []
    for t in extras + core:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(t)

    # Fill up toward ~480 chars (comma-joined), hard-stop under 500.
    out = []
    total = 0
    for t in ordered:
        add = len(t) + (1 if out else 0)  # +1 for the joining comma
        if total + add > 490:
            break
        out.append(t)
        total += add
    return out


def generate_hashtags(country: str = "", volume: int = 1) -> list[str]:
    """Generate a short hashtag list (3-5, not excessive)."""
    tags = ["#CityPop", "#Playlist", "#SeoulRecords"]
    if country:
        tags.append(f"#{country}CityPop")
    tags.append("#NightDrive")
    return tags[:5]


def format_chapters_section(chapters: list[dict]) -> str:
    """Format the chapters as a copy-ready YouTube description section."""
    if not chapters:
        return ""
    lines = ["⏱ Tracklist"]
    for ch in chapters:
        lines.append(f"{ch['timestamp']} {ch['title']}")
    return "\n".join(lines)


def generate_description(
    playlist_title: str, country: str = "", volume: int = 1,
    mood: str = "", chapters: list[dict] | None = None,
    duration_min: int = 60,
) -> str:
    """
    Build a structured YouTube description:
      1. Opening mood line
      2. Playlist concept
      3. Tracklist with timestamps
      4. Channel/brand line
      5. Usage note
      6. Hashtags
    """
    chapters = chapters or []
    label = playlist_title or (f"{country} CityPop Playlist Vol.{volume}"
                               if country else f"CityPop Playlist Vol.{volume}")
    city = country or "the city"
    mood_line = mood or "a nostalgic late-night drive through neon-lit streets"

    parts = []
    # 1. Opening mood line
    parts.append(f"🌃 {mood_line}.")
    parts.append("")
    # 2. Playlist concept
    parts.append("About this mix")
    parts.append(
        f"{label} — {duration_min} minutes of nostalgic city pop to score "
        f"your night in {city}. Smooth electric piano, warm analog synths, "
        f"and gentle grooves for late hours."
    )
    parts.append("")
    # 3. Tracklist
    section = format_chapters_section(chapters)
    if section:
        parts.append(section)
        parts.append("")
    # 4. Channel/brand line
    parts.append(f"🎵 {CHANNEL_NAME}")
    parts.append("AI-crafted city pop playlists from Seoul and beyond.")
    parts.append("")
    # 5. Usage note
    parts.append("Listen while")
    parts.append("driving at night · studying · relaxing · working late")
    parts.append("")
    # 6. Hashtags
    parts.append(" ".join(generate_hashtags(country, volume)))

    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# v1.0.0-alpha.59: Seoul Records "DJ HANA" default title/description template.
#
# The user asked for a fixed, brand-consistent title + description frame, with
# ONLY the tracklist being auto-filled from the actual uploaded audio (via the
# chapters parsed from chapters.txt / the real video's segment timings). The
# surrounding copy — title line, mood keywords, FAQ, copyright block — stays
# constant. Everything that follows is the exact frame the user supplied.
# ─────────────────────────────────────────────────────────────────────────────

DJHANA_DEFAULT_TITLE = (
    "[Playlist] 서울 시티팝 한강에서 DJ가 말아주는 디스코 하우스 | "
    "Seoul City Pop Sunset Nu Disco Mixset"
)


def _format_djhana_tracklist(chapters: list[dict]) -> str:
    """
    Render the tracklist block for the DJ HANA description using the ACTUAL
    uploaded audio. Each line: '00:00:00  01. <title>'. Timestamps are taken
    verbatim from the parsed chapters (which come from the real assembled
    video), and are normalised to HH:MM:SS so long (1h+) mixes read cleanly.
    Track titles are used exactly as chapters provide them — no invented
    '(feat. …)' names — so the list always matches what's really in the video.
    """
    if not chapters:
        return ""
    lines = []
    for i, ch in enumerate(chapters, start=1):
        ts = _normalise_timestamp(ch.get("timestamp", "0:00"))
        title = ch.get("title", "").strip()
        lines.append(f"{ts}  {i:02d}. {title}")
    return "\n".join(lines)


def _normalise_timestamp(ts: str) -> str:
    """Normalise 'M:SS' or 'MM:SS' or 'H:MM:SS' to 'HH:MM:SS'."""
    parts = ts.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return ts
    if len(nums) == 2:
        m, s = nums
        h = 0
    elif len(nums) == 3:
        h, m, s = nums
    else:
        return ts
    return f"{h:02d}:{m:02d}:{s:02d}"


def generate_djhana_description(chapters: list[dict] | None = None,
                                mood: str = "") -> str:
    """
    Build the full Seoul Records / DJ HANA description with the fixed frame
    the user specified, injecting ONLY the tracklist from the real uploaded
    audio. If there are no chapters, a placeholder line is used instead of a
    fabricated tracklist.

    v1.0.0-alpha.62: an optional `mood` (shared across song/thumbnail/
    YouTube) is woven into the opening line so the description reflects the
    same mood as the song and thumbnail, without disturbing the fixed FAQ /
    copyright frame.
    """
    chapters = chapters or []
    tracklist = _format_djhana_tracklist(chapters)
    if not tracklist:
        tracklist = "00:00:00  01. (트랙 정보는 업로드된 음원 기준으로 자동 생성됩니다)"

    mood_line = f"\n🌆 Tonight's mood — {mood.strip()}\n" if mood.strip() else ""

    return f"""[Playlist] 서울 시티팝 한강에서 DJ가 말아주는 디스코 하우스 | Seoul Citypop Sunset Nu Disco Mixset
{mood_line}
🏖️ Mood Keywords
DJ HANA, Seoul Sunset, Han River, Live DJ Set, Summer Night Drive, Nu Disco House, Tropical House, Disco House, Korean House Mix, Rooftop Lounge, Summer Playlist

🎶 총 {len(chapters)}곡 연속 재생 (Full Playlist)

🎧 Seoul City Pop / DJ HANA Mixset / Playlist

{tracklist}

FAQ 자주 묻는 질문

Q1. 이 영상은 어떤 콘텐츠인가요?
A. DJ HANA가 서울 한강의 여름 노을 감성을 바탕으로 구성한 누디스코 하우스, 디스코 하우스, 트로피컬 하우스 스타일의 라이브 믹스셋입니다. 청량하면서도 세련된 여름 하우스 무드를 담았습니다.

Q2. 언제 듣기 좋은 믹스셋인가요?
A. 한강 산책, 여름 드라이브, 루프탑 바, 카페 BGM, 선셋 파티, 휴양지 감성 플레이리스트로 잘 어울립니다. 해질 무렵부터 밤이 시작되는 시간대에 특히 좋습니다.

Q3. DJ HANA는 어떤 스타일의 음악을 들려주나요?
A. DJ HANA는 감각적인 선곡과 부드러운 전개를 중심으로, 세련된 누디스코 하우스와 트로피컬 하우스, 디스코 하우스 기반의 여름 믹스셋을 선보입니다.

Q4. 카페나 Bar에서 재생해도 되나요?
A. 이 라이브 믹스셋의 모든 곡은 제작자의 오리지널 창작곡입니다. 매장 분위기 연출용 BGM으로 자유롭게 감상하실 수 있습니다. 단, 음원의 무단 복제, 재업로드, 배포, 편집 및 2차 가공은 금지됩니다.

🎵 저작권 안내
이 라이브 믹스셋의 모든 음악과 이미지는 제작자가 AI 제작 도구를 활용해 만든 오리지널 창작물이며, 공식 발매된 음원입니다.

무단 복제, 재배포, 재업로드, 편집, 2차 가공 및 상업적 재사용을 금지합니다.

© All rights reserved. Unauthorized reproduction, distribution, re-uploading, editing, or secondary use is strictly prohibited."""


# YouTube setup steps that the Data API cannot automate — the user must set
# these by hand in YouTube Studio after each upload. Surfaced as a checklist
# in the UI so nothing is forgotten (see app/tabs/youtube_package.py).
STUDIO_MANUAL_STEPS = [
    "수익 창출: '사용'으로 켜기 (API로 설정 불가 — Studio 전용)",
    "동영상 내용에 관한 정보(자가 평가): 모두 '해당 사항 없음' 체크 후 제출",
    "시청자층: '아니요, 아동용이 아닙니다' 확인 (payload에 반영되나 Studio에서 재확인 권장)",
    "AI 사용(변경된 콘텐츠) 공개: '예'로 설정",
    "최종 화면: 구독 + 최근 업로드 동영상 + 재생목록 'Seoul City Pop Wave'",
    "카드: 동영상 5개 (최근 순, 약 10분 간격으로 배치)",
]


def generate_pinned_comment(country: str = "", volume: int = 1) -> str:
    """Short, friendly pinned comment with a subtle CTA + next-volume mention."""
    next_vol = volume + 1
    loc = f"{country} " if country else ""
    return (
        f"Thanks for listening to this {loc}CityPop mix 🌃 "
        f"Save it for your next night drive, and let me know which city "
        f"you'd like for Vol.{next_vol}. More playlists coming soon — "
        f"{CHANNEL_NAME} 🎵"
    )


def generate_all_metadata(
    playlist_title: str, country: str = "", volume: int = 1,
    mood: str = "", chapters_path: str = "", duration_min: int = 60,
    use_djhana_template: bool = True,
    language: str = "korean",
    translate: bool = True,
) -> dict:
    """
    Generate the full metadata bundle.

    v1.0.0-alpha.59: use_djhana_template (default True) applies the Seoul
    Records / DJ HANA fixed title + description frame the user requested,
    with ONLY the tracklist auto-filled from the real uploaded audio
    (chapters). Set it False to fall back to the older auto-generated
    English description.

    v1.0.0-alpha.60: `language` is the song's lyric language key (korean,
    japanese, thai, vietnamese, indonesian). When it is a non-Korean
    supported language and `translate` is True, the DJ HANA description
    frame is auto-translated into that language via OpenAI/Gemini (the
    tracklist is preserved verbatim). Tags always stay English. On any
    translation failure or missing API key, the Korean frame is kept.
    """
    chapters = parse_chapters_txt(chapters_path) if chapters_path else []

    translated_flag = False
    translated_language = "Korean"
    if use_djhana_template:
        title = DJHANA_DEFAULT_TITLE
        description = generate_djhana_description(chapters, mood=mood)
        if translate:
            from services.youtube.description_translator import (
                translate_description, needs_translation)
            if needs_translation(language):
                res = translate_description(description, language)
                description = res["description"]
                translated_flag = res["translated"]
                translated_language = res["language"]
    else:
        title = generate_title(playlist_title, country, volume, duration_min, mood)
        description = generate_description(
            playlist_title, country, volume, mood, chapters, duration_min)

    return {
        "title": title,
        "description": description,
        "tags": generate_tags(country, mood, volume),
        "hashtags": generate_hashtags(country, volume),
        "pinned_comment": generate_pinned_comment(country, volume),
        "chapters": chapters,
        "chapters_section": format_chapters_section(chapters),
        "studio_manual_steps": STUDIO_MANUAL_STEPS,
        "description_translated": translated_flag,
        "description_language": translated_language,
    }
