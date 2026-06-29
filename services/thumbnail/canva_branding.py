"""
services/thumbnail/canva_branding.py — Canva branding step.

Only SELECTED candidate images enter branding. Generates a consistent
Seoul Records brand template payload (title typography, layout, brand
placement stay consistent; only accent color adapts per image).

Three modes:
  1. Canva Manual    — generate payload/instructions for manual application
  2. Canva Autofill  — fill template variables (if token/template available)
  3. Mock Canva      — render a placeholder branded thumbnail locally (PIL)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


# Default brand template — consistent across all thumbnails
DEFAULT_TEMPLATE = {
    "template_id": "seoul_records_citypop_v1",
    "template_name": "Seoul Records CityPop Playlist",
    "aspect_ratio": "16:9",
    "canvas_size": [1280, 720],
    "font_family": "Montserrat",
    "title_font_size": 84,
    "subtitle_font_size": 40,
    "brand_font_size": 32,
    "text_color": "#FFFFFF",
    "title_position": "lower-left",
    "subtitle_position": "below-title",
    "brand_position": "top-left",
    "safe_margin": 64,
    "shadow_or_glow": "soft drop shadow + subtle glow",
    "overlay_gradient": "bottom-to-top dark gradient for text legibility",
}


def build_main_title(country_label: str, volume: int, custom_title: str = "") -> str:
    """Build the consistent main title text."""
    if custom_title:
        return custom_title
    if country_label:
        return f"{country_label} CityPop Playlist Vol.{volume}"
    return f"CityPop Playlist Vol.{volume}"


def generate_canva_payload(
    session_id: str,
    candidate: dict,
    title: str,
    subtitle: str,
    brand_text: str,
    volume: int,
    country: str,
    theme: str,
    template: dict | None = None,
) -> dict:
    """
    Generate a Canva branding payload for ONE selected candidate image.
    The payload owns ALL title text (Flow image has no text).
    """
    tpl = template or DEFAULT_TEMPLATE
    accent = candidate.get("canva_accent_color", "#ff4d6d")

    payload = {
        "template_id": tpl["template_id"],
        "template_name": tpl["template_name"],
        "aspect_ratio": tpl["aspect_ratio"],
        "canvas_size": tpl["canvas_size"],
        "background_image_path": candidate.get("uploaded_image_path", ""),
        # Template variables — Canva fills these
        "variables": {
            "{{BACKGROUND_IMAGE}}": candidate.get("uploaded_image_path", ""),
            "{{MAIN_TITLE}}": title,
            "{{SUBTITLE}}": subtitle,
            "{{BRAND_TEXT}}": brand_text,
            "{{COUNTRY}}": country,
            "{{THEME}}": theme,
            "{{VOL_NO}}": str(volume),
            "{{ACCENT_COLOR}}": accent,
        },
        # Consistent layout (same for every thumbnail)
        "font_family": tpl["font_family"],
        "title_font_size": tpl["title_font_size"],
        "subtitle_font_size": tpl["subtitle_font_size"],
        "brand_font_size": tpl["brand_font_size"],
        "text_color": tpl["text_color"],
        "accent_color": accent,  # adapts per image
        "title_position": tpl["title_position"],
        "subtitle_position": tpl["subtitle_position"],
        "brand_position": tpl["brand_position"],
        "safe_margin": tpl["safe_margin"],
        "shadow_or_glow": tpl["shadow_or_glow"],
        "overlay_gradient": tpl["overlay_gradient"],
        "candidate_id": candidate.get("candidate_id", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return payload


def save_canva_payload(session_id: str, candidate_id: str, payload: dict) -> str:
    """Save a Canva payload to the session."""
    from services.thumbnail.session_store import session_path
    sdir = session_path(session_id)
    canva_dir = sdir / "canva"
    canva_dir.mkdir(parents=True, exist_ok=True)
    path = canva_dir / f"canva_payload_{candidate_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def mock_render_branded_thumbnail(
    session_id: str,
    candidate: dict,
    title: str,
    subtitle: str,
    brand_text: str,
    accent_color: str,
) -> str | None:
    """
    Mock Canva mode — render a placeholder branded thumbnail locally with PIL.
    Applies the consistent brand layout (title/subtitle/brand text + gradient).
    Returns the output path, or None if PIL/image unavailable.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    from services.thumbnail.session_store import session_path
    sdir = session_path(session_id)
    branded_dir = sdir / "branded"
    branded_dir.mkdir(parents=True, exist_ok=True)

    W, H = 1280, 720
    bg_path = candidate.get("uploaded_image_path", "")

    # Load background or make a solid placeholder
    try:
        if bg_path and Path(bg_path).exists():
            img = Image.open(bg_path).convert("RGB").resize((W, H))
        else:
            img = Image.new("RGB", (W, H), (26, 34, 56))
    except Exception:
        img = Image.new("RGB", (W, H), (26, 34, 56))

    draw = ImageDraw.Draw(img, "RGBA")

    # Bottom-to-top dark gradient for legibility
    for y in range(H):
        alpha = int(180 * (y / H) ** 1.5)
        draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))

    margin = 64

    # Helper to load a font with fallback
    def _font(size):
        for fp in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]:
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
        return ImageFont.load_default()

    # Brand text (top-left, small)
    draw.text((margin, margin), brand_text or "Seoul Records",
              font=_font(32), fill="#FFFFFF")

    # Accent bar above title
    accent_rgb = _hex_to_rgb(accent_color)
    draw.rectangle([margin, H - 220, margin + 80, H - 210], fill=accent_rgb)

    # Main title (lower-left, large)
    draw.text((margin, H - 200), title, font=_font(72), fill="#FFFFFF")

    # Subtitle (below title)
    if subtitle:
        draw.text((margin, H - 110), subtitle, font=_font(36), fill=accent_rgb)

    # Save
    existing = list(branded_dir.glob("branded_thumbnail_*.png"))
    n = len(existing) + 1
    out_path = branded_dir / f"branded_thumbnail_{n:03d}.png"
    img.save(out_path)

    # Save branding metadata
    meta_path = branded_dir / "thumbnail_branding_metadata.json"
    meta = []
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = []
    meta.append({
        "candidate_id": candidate.get("candidate_id", ""),
        "branded_path": str(out_path),
        "title": title,
        "subtitle": subtitle,
        "brand_text": brand_text,
        "accent_color": accent_color,
        "aspect_ratio": "16:9",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return str(out_path)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return (255, 77, 109)
    try:
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return (255, 77, 109)


def export_final_thumbnail(session_id: str, branded_path: str) -> str | None:
    """Copy a branded thumbnail to the exports folder as the final output."""
    import shutil
    from services.thumbnail.session_store import session_path
    src = Path(branded_path)
    if not src.exists():
        return None
    sdir = session_path(session_id)
    exports_dir = sdir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    n = len(list(exports_dir.glob("final_thumbnail_*.png"))) + 1
    dest = exports_dir / f"final_thumbnail_{n:03d}.png"
    shutil.copy2(src, dest)
    return str(dest)
