"""
PillowOverlayProvider — applies text overlays to images using PIL/Pillow.

Used as a fallback when Canva MCP is not available.
Produces clean, minimal text overlays suitable for city pop aesthetic.
"""

from __future__ import annotations
import os

try:
    from PIL import Image, ImageDraw
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


class PillowOverlayProvider:
    """Applies text overlays to generated images using PIL."""

    def __init__(self):
        if not _PIL_AVAILABLE:
            raise ImportError("Pillow is required for PillowOverlayProvider.")

    def apply_thumbnail_text(
        self,
        source_path: str,
        output_path: str,
        title: str,
        artist: str = "Seoul Records",
    ) -> str:
        """
        Apply title and artist text to a YouTube thumbnail.

        Args:
            source_path: Path to source image (1280×720).
            output_path: Path to save result.
            title: Track title.
            artist: Artist name.

        Returns:
            Path to output image.
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with Image.open(source_path) as img:
            img = img.resize((1280, 720), Image.LANCZOS)
            draw = ImageDraw.Draw(img, "RGBA")
            # Semi-transparent text box
            draw.rectangle([40, 520, 900, 680], fill=(0, 0, 0, 160))
            draw.text((60, 535), title, fill=(255, 255, 220))
            draw.text((60, 620), artist, fill=(180, 180, 140))
            img.save(output_path)
        return output_path

    def apply_cover_text(
        self,
        source_path: str,
        output_path: str,
        title: str,
        artist: str = "Seoul Records",
    ) -> str:
        """
        Apply title and artist text to a DSP cover image.

        Args:
            source_path: Path to source image (3000×3000 target).
            output_path: Path to save result.
            title: Track title.
            artist: Artist name.

        Returns:
            Path to output image.
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with Image.open(source_path) as img:
            img = img.resize((3000, 3000), Image.LANCZOS)
            draw = ImageDraw.Draw(img, "RGBA")
            draw.rectangle([100, 2350, 2900, 2900], fill=(0, 0, 0, 180))
            draw.text((150, 2400), title, fill=(255, 255, 220))
            draw.text((150, 2620), artist, fill=(180, 180, 140))
            img.save(output_path)
        return output_path

    def get_capabilities(self) -> dict:
        return {
            "provider": "pillow_overlay",
            "available": _PIL_AVAILABLE,
            "real_canva": False,
        }
