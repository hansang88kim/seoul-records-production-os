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


# ── Cross-platform fonts (CJK-capable) ────────────────────────────────────────
# Windows 맑은 고딕 / Linux Noto Sans CJK / macOS — CJK fonts render BOTH Korean
# and Latin, so Korean titles and 구독/좋아요 stickers never show tofu boxes.
_FONTS_BOLD = [
    r"C:\Windows\Fonts\malgunbd.ttf",
    r"C:\Windows\Fonts\malgun.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_FONTS_REG = [
    r"C:\Windows\Fonts\malgun.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _load_font(size: int, bold: bool = True):
    from PIL import ImageFont
    for fp in (_FONTS_BOLD if bold else _FONTS_REG):
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _text_wh(draw, text: str, font) -> tuple[int, int]:
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    return r - l, b - t


def _fit_font(draw, text: str, max_w: int, start: int, min_size: int = 40, bold: bool = True):
    size = start
    while size > min_size:
        f = _load_font(size, bold)
        if _text_wh(draw, text, f)[0] <= max_w:
            return f
        size -= 4
    return _load_font(min_size, bold)


def _draw_text_glow(draw, xy, text, font, fill=(255, 255, 255, 255),
                    glow=(0, 0, 0, 190), r: int = 3):
    x, y = xy
    for dx in (-r, 0, r):
        for dy in (-r, 0, r):
            if dx or dy:
                draw.text((x + dx, y + dy), text, font=font, fill=glow)
    draw.text((x, y), text, font=font, fill=fill)


def _draw_equalizer(draw, box, accent_rgb, bars: int = 14, seed: int = 0):
    """A row of citypop-tinted visualizer bars within box=(x0,y0,x1,y1)."""
    import random
    x0, y0, x1, y1 = box
    rnd = random.Random(seed)
    w, h = x1 - x0, y1 - y0
    slot = w / bars
    bar_w = max(4, slot * 0.55)
    for i in range(bars):
        bh = h * (0.18 + 0.82 * rnd.random())
        bx = x0 + i * slot + (slot - bar_w) / 2
        draw.rounded_rectangle([bx, y1 - bh, bx + bar_w, y1],
                               radius=bar_w / 2, fill=(accent_rgb[0], accent_rgb[1], accent_rgb[2], 235))


def _draw_subscribe(draw, x, y, scale: float = 1.0, text: str = "구독"):
    """YouTube-style red subscribe pill with a play triangle. Returns (w, h)."""
    font = _load_font(int(34 * scale), bold=True)
    pad_x, pad_y, gap = int(26 * scale), int(13 * scale), int(12 * scale)
    tw, th = _text_wh(draw, text, font)
    tri = int(th * 0.95)
    w = pad_x * 2 + tri + gap + tw
    h = pad_y * 2 + th
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=(0xCC, 0x00, 0x00, 255))
    tx, cy = x + pad_x, y + h / 2
    draw.polygon([(tx, cy - tri / 2), (tx, cy + tri / 2), (tx + tri * 0.9, cy)],
                 fill=(255, 255, 255, 255))
    draw.text((tx + tri + gap, y + pad_y), text, font=font, fill=(255, 255, 255, 255))
    return w, h


def _draw_like(draw, x, y, scale: float = 1.0, accent_rgb=(255, 77, 109), text: str = "좋아요"):
    """Outlined like pill with a heart. Returns (w, h)."""
    font = _load_font(int(34 * scale), bold=True)
    pad_x, pad_y, gap = int(24 * scale), int(13 * scale), int(10 * scale)
    heart = "\u2665"
    hw, hh = _text_wh(draw, heart, font)
    tw, th = _text_wh(draw, text, font)
    w = pad_x * 2 + hw + gap + tw
    h = pad_y * 2 + max(th, hh)
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2,
                           fill=(20, 24, 38, 215), outline=(255, 255, 255, 235),
                           width=max(2, int(2 * scale)))
    draw.text((x + pad_x, y + pad_y), heart, font=font, fill=(*accent_rgb, 255))
    draw.text((x + pad_x + hw + gap, y + pad_y), text, font=font, fill=(255, 255, 255, 255))
    return w, h


def mock_render_branded_thumbnail(
    session_id: str,
    candidate: dict,
    title: str,
    subtitle: str,
    brand_text: str,
    accent_color: str,
    show_equalizer: bool = True,
    show_subscribe: bool = True,
    show_like: bool = True,
    title_layout: str = "lower-left",
) -> str | None:
    """
    Render a finished YouTube thumbnail locally with PIL — no Canva needed.

    Composites the Seoul Records brand layout (title/subtitle/brand text +
    gradient) PLUS optional YouTube stickers (equalizer visualizer, red 구독
    button, 좋아요 button), all auto-placed. Uses CJK fonts so Korean renders.
    Returns the output path, or None if PIL/image unavailable.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    from services.thumbnail.session_store import session_path
    sdir = session_path(session_id)
    branded_dir = sdir / "branded"
    branded_dir.mkdir(parents=True, exist_ok=True)

    W, H = 1280, 720
    margin = 64
    accent_rgb = _hex_to_rgb(accent_color)
    bg_path = candidate.get("uploaded_image_path", "")

    # Load background (cover-fit) or solid placeholder.
    try:
        if bg_path and Path(bg_path).exists():
            img = Image.open(bg_path).convert("RGB").resize((W, H))
        else:
            img = Image.new("RGB", (W, H), (26, 34, 56))
    except Exception:
        img = Image.new("RGB", (W, H), (26, 34, 56))

    draw = ImageDraw.Draw(img, "RGBA")

    # Bottom-to-top dark gradient for text legibility.
    for y in range(H):
        alpha = int(190 * (y / H) ** 1.5)
        draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))

    # Brand text — top-left.
    draw.text((margin, margin), brand_text or "Seoul Records",
              font=_load_font(34, bold=True), fill=(255, 255, 255, 255))

    # Subscribe + Like — top-right row.
    try:
        row_x, row_y = W - margin, margin
        like_w = sub_w = 0
        if show_like:
            # measure by drawing off-canvas position then reposition: draw last.
            pass
        # Draw subscribe first (left of the pair), then like to its right, right-aligned.
        pieces = []
        if show_subscribe:
            pieces.append("sub")
        if show_like:
            pieces.append("like")
        # Pre-measure widths using temp draws on a scratch image.
        from PIL import Image as _Img
        scratch = ImageDraw.Draw(_Img.new("RGBA", (10, 10)))
        widths = {}
        if show_subscribe:
            widths["sub"] = _draw_subscribe(scratch, 0, 0)[0]
        if show_like:
            widths["like"] = _draw_like(scratch, 0, 0, accent_rgb=accent_rgb)[0]
        gap = 16
        total = sum(widths.values()) + (gap if len(widths) == 2 else 0)
        cx = W - margin - total
        if show_subscribe:
            w, h = _draw_subscribe(draw, cx, row_y)
            cx += w + gap
        if show_like:
            _draw_like(draw, cx, row_y, accent_rgb=accent_rgb)
    except Exception:
        pass  # stickers are best-effort; never fail the whole render

    # Title + subtitle.
    sub_font = _load_font(40, bold=False)
    sub_h = _text_wh(draw, subtitle, sub_font)[1] if subtitle else 0
    if title_layout == "center":
        title_font = _fit_font(draw, title, int(W * 0.84), 104)
        tw, th = _text_wh(draw, title, title_font)
        tx, ty = (W - tw) // 2, (H - th) // 2 - 10
        draw.rectangle([(W - 110) // 2, ty - 28, (W + 110) // 2, ty - 16], fill=(*accent_rgb, 255))
        _draw_text_glow(draw, (tx, ty), title, title_font)
        if subtitle:
            sw = _text_wh(draw, subtitle, sub_font)[0]
            draw.text(((W - sw) // 2, ty + th + 18), subtitle, font=sub_font, fill=(*accent_rgb, 255))
    else:  # lower-left
        title_font = _fit_font(draw, title, int(W * 0.60), 92)
        tw, th = _text_wh(draw, title, title_font)
        ty = H - margin - (sub_h + (18 if subtitle else 0)) - th
        draw.rectangle([margin, ty - 26, margin + 92, ty - 14], fill=(*accent_rgb, 255))
        _draw_text_glow(draw, (margin, ty), title, title_font)
        if subtitle:
            draw.text((margin, ty + th + 18), subtitle, font=sub_font, fill=(*accent_rgb, 255))

    # Equalizer — lower-right band (kept clear of the lower-left title).
    if show_equalizer:
        try:
            _draw_equalizer(draw, (int(W * 0.54), H - 150, W - margin, H - margin - 12),
                            accent_rgb, bars=14,
                            seed=sum(ord(c) for c in candidate.get("candidate_id", "x")))
        except Exception:
            pass

    # Save.
    existing = list(branded_dir.glob("branded_thumbnail_*.png"))
    n = len(existing) + 1
    out_path = branded_dir / f"branded_thumbnail_{n:03d}.png"
    img.save(out_path)

    # Branding metadata.
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
        "stickers": {"equalizer": show_equalizer, "subscribe": show_subscribe, "like": show_like},
        "title_layout": title_layout,
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
