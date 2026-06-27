"""
MockCanvaProvider — generates placeholder Canva design files for v0.1 testing.

v0.1: Writes placeholder text files representing Canva exports.
v0.4+: Replace with CanvaMcpProvider for real template filling.
"""

from __future__ import annotations
import os
import json
from datetime import datetime

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


class MockCanvaProvider:
    """Simulates Canva output for v0.1 testing."""

    def create_youtube_thumbnail(
        self,
        title: str,
        source_image_path: str,
        output_dir: str,
    ) -> dict:
        """Create a mock 1280×720 YouTube thumbnail."""
        final_dir = os.path.join(output_dir, "final")
        os.makedirs(final_dir, exist_ok=True)

        output_jpg = os.path.join(final_dir, "youtube_thumbnail_16x9.jpg")
        output_png = os.path.join(final_dir, "youtube_thumbnail_16x9.png")

        if _PIL_AVAILABLE:
            img = Image.new("RGB", (1280, 720), color=(20, 20, 40))
            draw = ImageDraw.Draw(img)
            # Draw a simple gradient-like rectangle
            for y in range(720):
                shade = int(20 + (y / 720) * 30)
                draw.line([(0, y), (1280, y)], fill=(shade, shade, shade + 20))
            # Title placeholder text
            draw.rectangle([60, 500, 900, 640], fill=(0, 0, 0, 180))
            draw.text((80, 520), f"[MOCK] {title}", fill=(255, 255, 220))
            draw.text((80, 580), "Seoul Records", fill=(180, 180, 140))
            img.save(output_jpg, "JPEG", quality=90)
            img.save(output_png, "PNG")
        else:
            # Write minimal placeholder files
            for path in [output_jpg, output_png]:
                with open(path, "wb") as f:
                    f.write(b"MOCK_IMAGE_PLACEHOLDER")

        return {
            "status": "mock",
            "jpg": output_jpg,
            "png": output_png,
            "width": 1280,
            "height": 720,
        }

    def create_dsp_cover(
        self,
        title: str,
        artist: str,
        source_image_path: str,
        output_dir: str,
    ) -> dict:
        """Create a mock 3000×3000 DSP cover image."""
        final_dir = os.path.join(output_dir, "final")
        os.makedirs(final_dir, exist_ok=True)

        output_jpg = os.path.join(final_dir, "dsp_cover_3000x3000.jpg")
        output_png = os.path.join(final_dir, "dsp_cover_3000x3000.png")

        if _PIL_AVAILABLE:
            img = Image.new("RGB", (3000, 3000), color=(15, 15, 35))
            draw = ImageDraw.Draw(img)
            # Simple gradient background
            for y in range(3000):
                shade = int(15 + (y / 3000) * 40)
                draw.line([(0, y), (3000, y)], fill=(shade, shade - 5, shade + 15))
            # Artist / title placeholder
            draw.rectangle([150, 2400, 2850, 2700], fill=(0, 0, 0))
            draw.text((200, 2430), f"[MOCK] {title}", fill=(255, 255, 220))
            draw.text((200, 2560), artist, fill=(180, 180, 140))
            img.save(output_jpg, "JPEG", quality=95)
            img.save(output_png, "PNG")
        else:
            for path in [output_jpg, output_png]:
                with open(path, "wb") as f:
                    f.write(b"MOCK_IMAGE_PLACEHOLDER")

        return {
            "status": "mock",
            "jpg": output_jpg,
            "png": output_png,
            "width": 3000,
            "height": 3000,
        }

    def get_capabilities(self) -> dict:
        return {
            "provider": "mock_canva",
            "available": True,
            "real_canva": False,
            "pil_rendering": _PIL_AVAILABLE,
        }
