"""
services/thumbnail/prompt_generator.py — Google Flow / Nano Banana prompt generation.

v1.0.0-alpha.36: switched from a background-only composition to a centered-
portrait "1990s retro city-pop album cover" look, per fixed spec:
  1. Both 16:9 (YouTube thumbnail) and 1:1 (album-cover-style streaming cover)
     are the SAME generated image, just cropped to each ratio downstream
     (see session_store.generate_images / image_provider.derive_aspect_crop)
     — this module only ever produces ONE prompt per candidate.
  2. Resolution: 1K (set on the provider side, not in the prompt text).
  3. Must read as "subscribe-worthy" YouTube-thumbnail energy AND a genuine
     city-pop album cover.
  4. 1990s retro city-pop aesthetic, both as album art and thumbnail.
  5. A glamorous, stylish young woman (early 20s), centered, matching the
     selected country's look — described via tasteful fashion/glamour-
     photography language (the same register real 1980s-90s city-pop covers
     use), not explicit content.
The image is otherwise still background/logo/text-free — the Canva layer
adds all title text into the top or bottom clean band left in the prompt.
"""
from __future__ import annotations

from services.thumbnail.country_presets import (
    get_country_preset,
    get_culture,
    SCENE_VARIATIONS,
    PORTRAIT_SAFE_AREAS,
)


# Explicit negative prompt — Flow image must NOT contain text/logos
NEGATIVE_PROMPT = (
    "no text, no letters, no words, no typography, no captions, no titles, "
    "no logos, no watermarks, no signatures, no UI elements, no fake interface, "
    "no unreadable signs as main focus, no overcrowded composition, no clutter, "
    "no distorted faces, no extra limbs, no tourism-poster look, no landmark focus, "
    "no VHS effect, no film grain, no noise, no low resolution, no blurry, "
    "no pixelated, no retro filter, no vintage filter, no scan lines, no analog artifacts, "
    "no nudity, no explicit content, no swimwear, no underwear"
)


def _camera_for(track_no: int) -> str:
    cameras = [
        "cinematic medium shot",
        "low-angle glamour framing",
        "waist-up portrait framing",
        "medium shot with shallow depth of field",
        "three-quarter angle portrait",
        "eye-level fashion-editorial framing",
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
    Generate a single Google Flow prompt for a citypop album-cover-style
    thumbnail: a centered fashion/glamour portrait over the country's night
    cityscape, styled as a 1990s retro city-pop record sleeve.

    Returns a dict with the main prompt, negative prompt, composition note,
    title-safe area, color palette, and suggested Canva accent color.
    """
    preset = get_country_preset(country)
    culture = get_culture(country)
    scene_var = SCENE_VARIATIONS[track_no % len(SCENE_VARIATIONS)]
    safe_area = PORTRAIT_SAFE_AREAS[track_no % len(PORTRAIT_SAFE_AREAS)]
    camera = _camera_for(track_no)
    time_of_day = _time_for(track_no)

    theme_phrase = f", {theme}" if theme else ""

    main_prompt = (
        f"A premium 1990s retro city-pop album cover AND a subscribe-worthy YouTube "
        f"playlist thumbnail, evoking a wistful 1980s-1990s {culture} city-pop record "
        f"sleeve. Foreground subject, centered in frame: a glamorous, stylish "
        f"{culture} woman in her early twenties, confident sultry expression, "
        f"retro-glam fashion styling (bold lip color, soft voluminous hair, era-"
        f"appropriate chic outfit), fashion-magazine-cover presence, eye-catching "
        f"and click-worthy — the kind of striking central portrait a viewer stops "
        f"scrolling for. "
        f"Background setting: {preset['city']} — {preset['scene']}. "
        f"Featured scene: {scene_var}{theme_phrase}, {time_of_day}, softly out of "
        f"focus behind her. "
        f"Lighting: {preset['lighting']}, warm rim light on her silhouette. "
        f"{preset['signage']}. "
        f"Color tone: {preset['color_tone']}. "
        f"Composition: {camera}, cinematic framing, subject centered and dominant, "
        f"clean {safe_area}, balanced negative space only in that band for a title "
        f"overlay — never over her face or body. "
        f"Mood: bittersweet, dreamy, glamorous city night, premium record-sleeve "
        f"visual. "
        f"Style: 1990s retro city-pop album cover illustration/photography hybrid, "
        f"glossy analog-film aesthetic, soft volumetric light, gentle neon "
        f"reflections, subtle lens bloom, moody low-key lighting with high "
        f"contrast, elegant sophisticated palette — NOT gaudy, NOT oversaturated. "
        f"Quality: ultra-detailed, photorealistic portrait, 4K resolution, sharp "
        f"focus on the subject, high dynamic range, professional fashion "
        f"photography, award-winning album art. "
        f"IMPORTANT: tasteful glamour/fashion styling only, fully clothed, no "
        f"nudity — absolutely no text, no letters, no logos, no watermarks "
        f"anywhere in the image."
    )

    return {
        "main_prompt": main_prompt,
        "negative_prompt": NEGATIVE_PROMPT,
        "composition_note": (
            f"{camera}, leave {safe_area}. "
            f"Never place the title over the subject's face or body. "
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
