"""
Seoul Records Production OS — Producer Agent
Orchestrates song prompt generation using preset data.
"""
from __future__ import annotations
import json
import random
from pathlib import Path

from app.config import PRESETS_DIR


def _load_preset(language_pack: str) -> dict:
    pack_path = PRESETS_DIR / "language_packs" / f"{language_pack}.json"
    core_path = PRESETS_DIR / "core" / "seoul_records_citypop_core.json"
    core = json.loads(core_path.read_text(encoding="utf-8")) if core_path.exists() else {}
    if pack_path.exists():
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        # Pack overrides core where specified
        merged = {**core, **pack}
    else:
        merged = core
    return merged


def generate_song_prompt(
    track_number: int,
    theme: str = "",
    language_pack: str = "ko_kr_seoul",
    locked_title: bool = False,
    locked_style: bool = False,
    locked_lyrics: bool = False,
    existing_title: str = "",
    existing_style: str = "",
    existing_lyrics: str = "",
) -> dict:
    """
    Generate a song prompt from preset + theme.
    Respects locked fields.
    Returns dict with title, style, lyrics, exclude_styles.
    """
    preset = _load_preset(language_pack)

    title = existing_title if locked_title else _generate_title(preset, theme, track_number)
    style = existing_style if locked_style else _generate_style(preset)
    lyrics = existing_lyrics if locked_lyrics else _generate_lyrics(preset, theme, title)
    # exclude_styles in preset JSON is list[str]; normalise defensively
    raw_exclude = preset.get("exclude_styles", [])
    if isinstance(raw_exclude, str):
        exclude: list[str] = [s.strip() for s in raw_exclude.split(",") if s.strip()]
    else:
        exclude = list(raw_exclude)

    return {
        "title": title,
        "style": style,
        "lyrics": lyrics,
        "exclude_styles": exclude,   # always list[str]
    }


def _generate_title(preset: dict, theme: str, track_number: int) -> str:
    title_templates = preset.get("title_templates", [])
    city = preset.get("city", "Seoul")
    moods = preset.get("moods", ["night", "rain", "neon"])
    mood = random.choice(moods)
    if title_templates:
        template = random.choice(title_templates)
        return template.format(city=city, mood=mood, n=track_number, theme=theme or mood)
    return f"{city} Night Vol.{track_number}"


def _generate_style(preset: dict) -> str:
    core_styles = preset.get("core_styles", ["city pop", "j-pop", "sophisticated"])
    optional = preset.get("optional_style_modifiers", [])
    selected_optional = random.sample(optional, min(2, len(optional))) if optional else []
    all_styles = core_styles + selected_optional
    return ", ".join(all_styles)


def _generate_lyrics(preset: dict, theme: str, title: str) -> str:
    templates = preset.get("lyric_templates", [])
    if templates:
        template = random.choice(templates)
        return template.format(title=title, theme=theme or "night city")
    city = preset.get("city", "Seoul")
    lang = preset.get("language", "Korean")
    return (
        f"[Verse 1]\n"
        f"(Original {lang} lyrics for: {title})\n"
        f"네온빛 {city} 야경 아래\n"
        f"그대와 함께 걷던 그 길\n\n"
        f"[Chorus]\n"
        f"이 밤이 지나도 기억해\n"
        f"도시의 불빛처럼 빛나던 우리\n\n"
        f"[Verse 2]\n"
        f"창문 너머 흐르는 빗소리\n"
        f"그리움이 되어 흘러가네\n\n"
        f"[Outro]\n"
        f"안녕, {city}의 밤이여"
    )
