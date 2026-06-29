"""
services/thumbnail/prompt_generator.py — Google Flow / Nano Banana prompt generation.

Generates background-image prompts for citypop YouTube thumbnails.
The image is BACKGROUND ONLY — no text/logos/watermarks (the Canva layer
adds all title text). Batch mode produces varied prompts.
"""
from __future__ import annotations

from services.thumbnail.country_presets import (
    get_country_preset,
    SCENE_VARIATIONS,
    TITLE_SAFE_AREAS,
)


# Explicit negative prompt — Flow image must NOT contain text/logos
NEGATIVE_PROMPT = (
    "no text, no letters, no words, no typography, no captions, no titles, "
    "no logos, no watermarks, no signatures, no UI elements, no fake interface, "
    "no unreadable signs as main focus, no overcrowded composition, no clutter, "
    "no distorted faces, no extra limbs, no tourism-poster look, no landmark focus"
)


def _camera_for(track_no: int) -> str:
    cameras = [
        "cinematic wide shot",
        "low-angle cinematic framing",
        "over-the-shoulder perspective",
        "medium shot with shallow depth of field",
        "high-angle establishing shot",
        "eye-level street-level framing",
    ]
    return cameras[track_no % len(cameras)]


def _time_for(track_no: int) -> str:
    times = [
        "late night", "after midnight", "early evening blue hour",
        "rainy midnight", "pre-dawn quiet hours",
    ]
    return times[track_no % len(times)]


def generate_flow_prompt(
    country: str,
    theme: str,
    track_no: int = 0,
) -> dict:
    """
    Generate a single Google Flow prompt for a citypop thumbnail background.

    Returns a dict with the main prompt, negative prompt, composition note,
    title-safe area, color palette, and suggested Canva accent color.
    """
    preset = get_country_preset(country)
    scene_var = SCENE_VARIATIONS[track_no % len(SCENE_VARIATIONS)]
    safe_area = TITLE_SAFE_AREAS[track_no % len(TITLE_SAFE_AREAS)]
    camera = _camera_for(track_no)
    time_of_day = _time_for(track_no)

    theme_phrase = f", {theme}" if theme else ""

    main_prompt = (
        f"A nostalgic 1980s-1990s Japanese city pop aesthetic background for a "
        f"music playlist thumbnail. Setting: {preset['city']} — {preset['scene']}. "
        f"Featured scene: {scene_var}{theme_phrase}, {time_of_day}. "
        f"Lighting: {preset['lighting']}. {preset['signage']}. "
        f"Color tone: {preset['color_tone']}. "
        f"Composition: {camera}, cinematic 16:9 framing for a YouTube thumbnail, "
        f"rich atmospheric depth, {safe_area}, high contrast suitable for text overlay. "
        f"Mood: bittersweet nostalgic city night, premium citypop playlist visual. "
        f"Style: clean anime-inspired cel shading mixed with cinematic photo realism, "
        f"vintage film grain, soft bloom. "
        f"IMPORTANT: background image only — absolutely no text, no letters, no logos, "
        f"no watermarks anywhere in the image."
    )

    return {
        "main_prompt": main_prompt,
        "negative_prompt": NEGATIVE_PROMPT,
        "composition_note": (
            f"{camera}, leave {safe_area} for the title overlay. "
            f"Avoid placing key faces/objects under the title area. "
            f"High contrast for legible text overlay."
        ),
        "title_safe_area": safe_area,
        "color_palette": preset["palette"],
        "canva_accent_color": preset["accent"],
        "country": country,
        "theme": theme,
        "scene": scene_var,
        "track_no": track_no,
    }


def generate_prompt_batch(
    country: str,
    theme: str,
    count: int = 5,
) -> list[dict]:
    """
    Generate a batch of varied Flow prompts. Each prompt varies scene,
    camera, time, composition, and title-safe area.
    """
    return [generate_flow_prompt(country, theme, track_no=i) for i in range(count)]
