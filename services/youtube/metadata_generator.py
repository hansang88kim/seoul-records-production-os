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
    """Generate a tag list (no '#', plain keywords)."""
    tags = [
        "citypop", "city pop", "playlist", "music playlist",
        "nostalgic", "night drive", "chill", "lofi citypop",
        "japanese citypop", "80s citypop", "retro music",
        "seoul records",
    ]
    if country:
        tags.append(f"{country.lower()} citypop")
        tags.append(f"{country.lower()} playlist")
    if mood:
        tags.append(mood.lower())
    tags.append(f"citypop vol {volume}")
    # Dedupe, keep order, cap at 30 (YouTube allows ~500 chars of tags)
    seen = set()
    out = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:30]


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
) -> dict:
    """Generate the full metadata bundle."""
    chapters = parse_chapters_txt(chapters_path) if chapters_path else []
    return {
        "title": generate_title(playlist_title, country, volume, duration_min, mood),
        "description": generate_description(
            playlist_title, country, volume, mood, chapters, duration_min),
        "tags": generate_tags(country, mood, volume),
        "hashtags": generate_hashtags(country, volume),
        "pinned_comment": generate_pinned_comment(country, volume),
        "chapters": chapters,
        "chapters_section": format_chapters_section(chapters),
    }
