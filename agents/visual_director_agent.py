"""
VisualDirectorAgent — generates image prompts for thumbnails and covers.

v0.1: Produces text prompts and delegates to MockImageProvider.
v0.4+: Will call Flow / Nano Banana image API.

PROMPT RULES (immovable):
- No text, no logo, no watermark, no fake letters, no random typography.
- DSP cover: no URLs, QR codes, social handles, brand logos, fake logos.
- CTR-focused composition for YouTube thumbnail (16:9).
- Conservative, metadata-safe composition for DSP cover (1:1).
- Mood: nostalgic night-city, soft neon, cinematic.
"""

from __future__ import annotations
from typing import Optional


class VisualDirectorAgent:
    """Creates image prompts and coordinates image generation."""

    def __init__(self, language_pack: str = "ko_kr_seoul"):
        self.language_pack = language_pack

    # ------------------------------------------------------------------
    # Prompt generation
    # ------------------------------------------------------------------

    def generate_thumbnail_prompt(
        self,
        title: str,
        theme: Optional[str] = None,
        style_tags: Optional[list[str]] = None,
    ) -> str:
        """
        Generate a Flow/Nano Banana prompt for the YouTube thumbnail (16:9).
        """
        base = (
            "Cinematic 16:9 city pop aesthetic, Seoul night cityscape, "
            "soft neon reflections on wet asphalt, blurred bokeh lights, "
            "nostalgic 1990s urban mood, film grain, warm amber and teal tones, "
            "no text, no logo, no watermark, no letters, no people faces visible"
        )
        if theme:
            base += f", theme: {theme}"
        return base

    def generate_dsp_cover_prompt(
        self,
        title: str,
        theme: Optional[str] = None,
        style_tags: Optional[list[str]] = None,
    ) -> str:
        """
        Generate a Flow/Nano Banana prompt for the DSP cover (1:1, 3000×3000).
        """
        base = (
            "Square album cover, minimalist city pop aesthetic, "
            "soft gradient night sky over urban skyline, "
            "nostalgic 1990s Japanese city pop mood, "
            "elegant composition, no text, no logo, no watermark, "
            "no QR code, no URL, no social handle, no brand mark, "
            "no fake letters, no typography of any kind"
        )
        if theme:
            base += f", theme: {theme}"
        return base

    def generate_canva_guide(self, title: str, artist: str = "Seoul Records") -> dict:
        """
        Generate a Canva text overlay guide for manual design step.
        Returns dict with text elements and placement hints.

        v0.1: Returns a structured placeholder guide.
        v0.4+: Will drive Canva MCP template filling.
        """
        return {
            "title_text": title,
            "artist_text": artist,
            "thumbnail_title_position": "lower-left",
            "thumbnail_title_font_size": "large",
            "thumbnail_title_color": "#FFFFFF",
            "thumbnail_title_shadow": True,
            "cover_title_position": "center-bottom",
            "cover_title_font_size": "medium",
            "cover_artist_position": "below-title",
            "notes": (
                "Keep text minimal. Use clean sans-serif or elegant serif. "
                "Avoid decorative fonts. No background boxes on cover art."
            ),
        }

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def validate_thumbnail_dimensions(self, width: int, height: int) -> bool:
        """Check that thumbnail meets 16:9 requirement (1280×720 minimum)."""
        return width >= 1280 and height >= 720 and abs(width / height - 16 / 9) < 0.05

    def validate_cover_dimensions(self, width: int, height: int) -> bool:
        """Check that cover meets 1:1 requirement (3000×3000 minimum)."""
        return width == height and width >= 3000
