"""
Seoul Records Production OS — Mock Image Provider
Generates placeholder thumbnail and cover images using Pillow.
"""
from __future__ import annotations
from pathlib import Path


def _pillow_available() -> bool:
    try:
        import PIL
        return True
    except ImportError:
        return False


def generate_mock_thumbnail_16x9(
    output_path: Path,
    project_name: str = "Seoul Records",
    theme: str = "",
) -> Path:
    """Generate a 1280x720 placeholder thumbnail."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if _pillow_available():
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (1280, 720), color=(10, 15, 30))
        draw = ImageDraw.Draw(img)
        # Gradient-like background using rectangles
        for i in range(0, 720, 4):
            alpha = int(255 * (1 - i / 720) * 0.3)
            draw.rectangle([(0, i), (1280, i + 4)], fill=(20, 30, 60))
        # City grid lines
        for x in range(0, 1280, 80):
            draw.line([(x, 0), (x, 720)], fill=(30, 40, 80), width=1)
        for y in range(0, 720, 80):
            draw.line([(0, y), (1280, y)], fill=(30, 40, 80), width=1)
        # Decorative circles
        draw.ellipse([(400, 150), (880, 570)], outline=(60, 80, 140), width=2)
        draw.ellipse([(460, 210), (820, 510)], outline=(80, 100, 180), width=1)
        # Seoul Records label
        draw.rectangle([(40, 40), (300, 90)], fill=(180, 140, 80))
        try:
            font_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
        except Exception:
            font_label = ImageFont.load_default()
            font_title = font_label
        draw.text((50, 52), "SEOUL RECORDS", fill=(20, 15, 5), font=font_label)
        draw.text((640, 360), project_name[:30], fill=(220, 200, 160), font=font_title, anchor="mm")
        if theme:
            draw.text((640, 410), theme[:40], fill=(140, 160, 200), font=font_label, anchor="mm")
        draw.text((640, 680), "⬥ CITY POP ⬥", fill=(100, 120, 180), font=font_label, anchor="mm")
        img.save(str(output_path), "PNG")
    else:
        # Fallback: write a 1×1 transparent PNG
        output_path.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
            b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )

    return output_path


def generate_mock_cover_1x1(
    output_path: Path,
    project_name: str = "Seoul Records",
    theme: str = "",
) -> Path:
    """Generate a 3000x3000 placeholder DSP cover."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if _pillow_available():
        from PIL import Image, ImageDraw, ImageFont
        # Use smaller intermediate for speed, scale up
        size = 600
        img = Image.new("RGB", (size, size), color=(10, 15, 30))
        draw = ImageDraw.Draw(img)
        # Background circles
        for r in range(280, 50, -40):
            shade = int(10 + (280 - r) * 0.3)
            draw.ellipse(
                [(size // 2 - r, size // 2 - r), (size // 2 + r, size // 2 + r)],
                outline=(shade, shade + 10, shade + 40),
                width=1,
            )
        try:
            font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        except Exception:
            font_big = ImageFont.load_default()
            font_small = font_big
        draw.text((size // 2, size // 2 - 30), "SEOUL RECORDS", fill=(200, 180, 120), font=font_big, anchor="mm")
        draw.text((size // 2, size // 2 + 20), project_name[:24], fill=(160, 180, 220), font=font_small, anchor="mm")
        if theme:
            draw.text((size // 2, size // 2 + 50), theme[:24], fill=(120, 140, 180), font=font_small, anchor="mm")
        # Scale to 3000x3000
        img_large = img.resize((3000, 3000), resample=Image.LANCZOS)
        img_large.save(str(output_path), "PNG")
    else:
        output_path.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
            b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )

    return output_path
