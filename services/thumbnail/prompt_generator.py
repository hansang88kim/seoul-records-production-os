"""
services/thumbnail/prompt_generator.py — Google Flow / Nano Banana prompt generation.

v1.0.0-alpha.38: made the centered-portrait composition (introduced in
alpha.36) OPTIONAL via ``include_person`` (default True):
  * include_person=True  — centered fashion/glamour portrait over the
    country's night cityscape, styled as a 1990s city-pop record sleeve
    (the alpha.36 spec: subscribe-worthy thumbnail + genuine album cover,
    country-appropriate young woman as the subject).
  * include_person=False — background-only composition (pre-alpha.36):
    no person, clean cityscape with a title-safe band, for users who just
    want the atmospheric city-night look without a portrait subject.
Both modes still produce ONE prompt per candidate — 16:9 (YouTube
thumbnail) and 1:1 (streaming-cover-style) are derived from the SAME
generated image downstream (session_store.generate_images /
image_provider.derive_aspect_crop), never a second generation call.
Resolution: 1K (set on the provider side, not in the prompt text).
"""
from __future__ import annotations

from services.thumbnail.country_presets import (
    get_country_preset,
    get_culture,
    SCENE_VARIATIONS,
    TITLE_SAFE_AREAS,
    PORTRAIT_SAFE_AREAS,
)


# Explicit negative prompt — Flow image must NOT contain text/logos.
# Shared by both composition modes; the person-specific exclusions
# (nudity/swimwear/underwear) are harmless no-ops when include_person=False.
NEGATIVE_PROMPT = (
    "no text, no letters, no words, no typography, no captions, no titles, "
    "no logos, no watermarks, no signatures, no UI elements, no fake interface, "
    "no unreadable signs as main focus, no overcrowded composition, no clutter, "
    "no distorted faces, no extra limbs, no tourism-poster look, no landmark focus, "
    "no VHS effect, no film grain, no noise, no low resolution, no blurry, "
    "no pixelated, no retro filter, no vintage filter, no scan lines, no analog artifacts, "
    "no nudity, no explicit content, no swimwear, no underwear"
)


def _camera_for(track_no: int, include_person: bool = True) -> str:
    if include_person:
        cameras = [
            "cinematic medium shot",
            "low-angle glamour framing",
            "waist-up portrait framing",
            "medium shot with shallow depth of field",
            "three-quarter angle portrait",
            "eye-level fashion-editorial framing",
        ]
    else:
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


def _portrait_prompt(preset: dict, culture: str, scene_var: str, theme_phrase: str,
                     time_of_day: str, camera: str, safe_area: str) -> str:
    """v1.0.0-alpha.36 composition: centered fashion/glamour portrait, 1990s
    city-pop record-sleeve styling."""
    return (
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


def _background_prompt(preset: dict, culture: str, scene_var: str, theme_phrase: str,
                       time_of_day: str, camera: str, safe_area: str) -> str:
    """Pre-alpha.36 composition: background-only cityscape, no person."""
    return (
        f"A cinematic {culture} city night background for a premium music playlist "
        f"thumbnail, evoking a wistful 1980s-1990s city-pop atmosphere. "
        f"Setting: {preset['city']} — {preset['scene']}. "
        f"Featured scene: {scene_var}{theme_phrase}, {time_of_day}. "
        f"Lighting: {preset['lighting']}. {preset['signage']}. "
        f"Color tone: {preset['color_tone']}. "
        f"Composition: {camera}, cinematic 16:9 widescreen framing, rich atmospheric "
        f"depth, layered foreground and background, leading lines, balanced negative "
        f"space near the center for a title overlay. "
        f"Mood: bittersweet, dreamy, slightly melancholic city night, premium playlist visual. "
        f"Style: modern cinematic photography, clean high-resolution rendering, "
        f"shallow depth of field, soft volumetric light, gentle neon reflections on "
        f"wet surfaces, subtle lens bloom, moody low-key lighting with high contrast, "
        f"elegant muted sophisticated palette — NOT gaudy, NOT oversaturated. "
        f"Quality: ultra-detailed, photorealistic, 4K resolution, sharp focus, "
        f"high dynamic range, professional cinematography, award-winning. "
        f"IMPORTANT: background image only — absolutely no text, no letters, no logos, "
        f"no watermarks, no people-facing camera anywhere in the image."
    )


def generate_flow_prompt(
    country: str,
    theme: str,
    track_no: int = 0,
    include_person: bool = True,
) -> dict:
    """
    Generate a single Google Flow prompt for a citypop thumbnail.

    include_person=True (default): centered fashion/glamour portrait over
    the country's night cityscape, styled as a 1990s city-pop record sleeve
    (subscribe-worthy YouTube thumbnail + genuine album cover).
    include_person=False: background-only cityscape, no person — just the
    atmospheric city-night look with a clean title-safe band.

    Returns a dict with the main prompt, negative prompt, composition note,
    title-safe area, color palette, and suggested Canva accent color.
    """
    preset = get_country_preset(country)
    culture = get_culture(country)
    scene_var = SCENE_VARIATIONS[track_no % len(SCENE_VARIATIONS)]
    safe_areas = PORTRAIT_SAFE_AREAS if include_person else TITLE_SAFE_AREAS
    safe_area = safe_areas[track_no % len(safe_areas)]
    camera = _camera_for(track_no, include_person)
    time_of_day = _time_for(track_no)

    theme_phrase = f", {theme}" if theme else ""

    if include_person:
        main_prompt = _portrait_prompt(preset, culture, scene_var, theme_phrase,
                                       time_of_day, camera, safe_area)
        composition_note = (
            f"{camera}, leave {safe_area}. "
            f"Never place the title over the subject's face or body. "
            f"High contrast for legible text overlay."
        )
    else:
        main_prompt = _background_prompt(preset, culture, scene_var, theme_phrase,
                                          time_of_day, camera, safe_area)
        composition_note = (
            f"{camera}, leave {safe_area} for the title overlay. "
            f"Avoid placing key faces/objects under the title area. "
            f"High contrast for legible text overlay."
        )

    return {
        "main_prompt": main_prompt,
        "negative_prompt": NEGATIVE_PROMPT,
        "composition_note": composition_note,
        "title_safe_area": safe_area,
        "color_palette": preset["palette"],
        "canva_accent_color": preset["accent"],
        "country": country,
        "theme": theme,
        "scene": scene_var,
        "track_no": track_no,
        "include_person": include_person,
    }


def generate_prompt_batch(
    country: str,
    theme: str,
    count: int = 5,
    include_person: bool = True,
) -> list[dict]:
    """
    Generate a batch of varied Flow prompts. Each prompt varies scene,
    camera, time, composition, and title-safe area.
    """
    return [generate_flow_prompt(country, theme, track_no=i, include_person=include_person)
            for i in range(count)]
