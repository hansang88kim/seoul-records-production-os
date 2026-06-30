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
# Bundled fonts (OS-independent) — Montserrat for Latin titles (YouTube
# music-channel standard). Titles are English-only; if a string contains Hangul
# (e.g. the optional 구독/좋아요 stickers) we fall back to an OS CJK font.
_FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
_MONTSERRAT_BLACK = _FONT_DIR / "Montserrat-Black.ttf"
_MONTSERRAT_BOLD = _FONT_DIR / "Montserrat-Bold.ttf"
_MONTSERRAT_SEMIBOLD = _FONT_DIR / "Montserrat-SemiBold.ttf"
_MONTSERRAT_MEDIUM = _FONT_DIR / "Montserrat-Medium.ttf"

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


def _has_hangul(text) -> bool:
    return any("\uac00" <= ch <= "\ud7a3" or "\u1100" <= ch <= "\u11ff"
               for ch in (text or ""))


def _load_font(size: int, bold: bool = True, text=None, black: bool = False):
    """Bundled Montserrat (English-only titles). ``black=True`` uses Montserrat
    Black (900) for the title. If ``text`` contains Hangul (optional stickers),
    fall back to an OS CJK font. Falls back to PIL default if nothing loads.
    """
    from PIL import ImageFont
    candidates = []
    if text is not None and _has_hangul(text):
        candidates += [Path(p) for p in _FONTS_BOLD]  # OS CJK for Korean glyphs
    elif black:
        candidates += [_MONTSERRAT_BLACK, _MONTSERRAT_BOLD]
    elif bold:
        candidates += [_MONTSERRAT_BOLD, _MONTSERRAT_SEMIBOLD]
    else:
        candidates += [_MONTSERRAT_SEMIBOLD, _MONTSERRAT_MEDIUM]
    candidates += [Path(p) for p in (_FONTS_BOLD if (bold or black) else _FONTS_REG)]
    for fp in candidates:
        try:
            return ImageFont.truetype(str(fp), size)
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
    font = _load_font(int(34 * scale), bold=True, text=text)
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
    font = _load_font(int(34 * scale), bold=True, text=text)
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


def _cover_fit(bg_path: str, W: int, H: int):
    """Load background, scale to COVER WxH, center-crop. LANCZOS. Returns RGBA."""
    from PIL import Image
    try:
        if bg_path and Path(bg_path).exists():
            im = Image.open(bg_path).convert("RGB")
        else:
            im = Image.new("RGB", (W, H), (18, 22, 36))
    except Exception:
        im = Image.new("RGB", (W, H), (18, 22, 36))
    sw, sh = im.size
    scale = max(W / sw, H / sh)
    nw, nh = max(1, int(sw * scale)), max(1, int(sh * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - W) // 2, (nh - H) // 2
    im = im.crop((left, top, left + W, top + H))
    return im.convert("RGBA")


def _radial_vignette(W: int, H: int, strength: int = 130):
    """Transparent overlay that darkens the edges (cinematic vignette)."""
    from PIL import Image, ImageDraw, ImageFilter, ImageOps
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).ellipse(
        [int(-W * 0.18), int(-H * 0.18), int(W * 1.18), int(H * 1.18)], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(int(W * 0.12)))
    inv = ImageOps.invert(mask).point(lambda p: int(p / 255 * strength))
    vig = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vig.putalpha(inv)
    return vig


def _spaced_width(draw, text: str, font, tracking: float) -> float:
    if not text:
        return 0.0
    return sum(draw.textlength(ch, font=font) + tracking for ch in text) - tracking


def _draw_spaced_centered(draw, text, cx, cy, font, fill=(255, 255, 255, 255),
                          tracking: float = 0.0, shadow=None, shadow_off=(0, 4)):
    """Draw letter-spaced text horizontally centered at cx, vertically centered at cy.

    ``shadow`` (if given) draws ONE soft offset drop shadow — not an outline/border.
    """
    if not text:
        return
    total = _spaced_width(draw, text, font, tracking)
    _, th = _text_wh(draw, text, font)
    x = cx - total / 2
    y = cy - th / 2
    sx, sy = shadow_off
    for ch in text:
        if shadow:
            draw.text((x + sx, y + sy), ch, font=font, fill=shadow)
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking


def _fit_font_spaced(draw, text, max_w, start, tracking_ratio=0.03, min_size=42,
                     bold=True, black=False):
    size = start
    while size > min_size:
        f = _load_font(size, bold, text=text, black=black)
        if _spaced_width(draw, text, f, size * tracking_ratio) <= max_w:
            return f
        size -= 4
    return _load_font(min_size, bold, text=text, black=black)


def render_premium_thumbnail(bg_path, title, subtitle="", brand_text="Seoul Records",
                             accent_color="#00d4ff", W=1920, H=1080, with_title=True):
    """
    Premium minimal music-channel thumbnail (10만+ 채널 레퍼런스): a cinematic
    background with a vignette and a clean CENTER-aligned title block
    (eyebrow + thin divider + letter-spaced title + subtitle). No CTA stickers.
    Returns a PIL RGB Image at WxH. Used for both the branded thumbnail and the
    exported deliverables so they stay consistent.
    """
    from PIL import Image, ImageDraw
    accent = _hex_to_rgb(accent_color)

    img = _cover_fit(bg_path, W, H)
    # Cinematic grade: light overall darken for legibility + a soft edge vignette.
    img = Image.alpha_composite(img, Image.new("RGBA", (W, H), (8, 10, 18, 45)))
    img = Image.alpha_composite(img, _radial_vignette(W, H, strength=95))
    draw = ImageDraw.Draw(img, "RGBA")

    cx, cy = W // 2, H // 2
    if with_title:
        # Eyebrow — uppercase brand, wide tracking, small (Montserrat).
        eyebrow = (brand_text or "Seoul Records").upper()
        ef = _load_font(int(H * 0.024), bold=True)
        _draw_spaced_centered(draw, eyebrow, cx, cy - int(H * 0.20), ef,
                              fill=(255, 255, 255, 205), tracking=H * 0.014)
        # Thin divider line above the title.
        lw = int(W * 0.055)
        ly = cy - int(H * 0.135)
        draw.rectangle([cx - lw // 2, ly, cx + lw // 2, ly + 3], fill=(*accent, 240))
        # Main playlist title — centered, letter-spaced, single soft drop shadow
        # (no outline/border). Montserrat, or Pretendard if the title has Hangul.
        tf = _fit_font_spaced(draw, title, int(W * 0.80), int(H * 0.10), black=True)
        _draw_spaced_centered(draw, title, cx, cy - int(H * 0.045), tf,
                              fill=(255, 255, 255, 255), tracking=int(H * 0.10) * 0.03,
                              shadow=(0, 0, 0, 130), shadow_off=(0, 4))
        # Subtitle — centered, accent, smaller, with a wider gap below the title.
        if subtitle:
            sf = _load_font(int(H * 0.032), bold=False, text=subtitle)
            _draw_spaced_centered(draw, subtitle, cx, cy + int(H * 0.11), sf,
                                  fill=(*accent, 235), tracking=H * 0.006)
    else:
        # Clean stage (video background) — only a faint brand mark, no title.
        bf = _load_font(int(H * 0.024), bold=True)
        _draw_spaced_centered(draw, (brand_text or "Seoul Records").upper(),
                              cx, H - int(H * 0.06), bf,
                              fill=(255, 255, 255, 110), tracking=H * 0.009)
    return img.convert("RGB")


def mock_render_branded_thumbnail(
    session_id: str,
    candidate: dict,
    title: str,
    subtitle: str,
    brand_text: str,
    accent_color: str,
    show_equalizer: bool = False,
    show_subscribe: bool = False,
    show_like: bool = False,
    title_layout: str = "center",
) -> str | None:
    """
    Render a finished, premium music-channel thumbnail locally (PIL) — no Canva.

    Default look (10만+ 채널 레퍼런스): a minimal CENTER-aligned title block over
    a cinematic, vignetted background, output at 1920x1080. YouTube CTA stickers
    (equalizer / 구독 / 좋아요) are OPTIONAL and OFF by default; when enabled they
    overlay the premium base. Uses CJK fonts so Korean renders. Returns the
    output path, or None if PIL is unavailable.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    from services.thumbnail.session_store import session_path
    sdir = session_path(session_id)
    branded_dir = sdir / "branded"
    branded_dir.mkdir(parents=True, exist_ok=True)

    W, H = 1920, 1080
    accent_rgb = _hex_to_rgb(accent_color)
    bg_path = candidate.get("uploaded_image_path", "")

    # Premium minimal base (centered title + cinematic vignette), full HD.
    img = render_premium_thumbnail(
        bg_path, title, subtitle, brand_text, accent_color, W, H,
        with_title=(title_layout != "none"),
    )

    # Optional CTA stickers overlaid on top (off by default).
    if show_subscribe or show_like or show_equalizer:
        draw = ImageDraw.Draw(img, "RGBA")
        margin = int(W * 0.045)
        scale = W / 1280.0
        try:
            from PIL import Image as _Img
            scratch = ImageDraw.Draw(_Img.new("RGBA", (10, 10)))
            widths = {}
            if show_subscribe:
                widths["sub"] = _draw_subscribe(scratch, 0, 0, scale=scale)[0]
            if show_like:
                widths["like"] = _draw_like(scratch, 0, 0, scale=scale, accent_rgb=accent_rgb)[0]
            gap = int(20 * scale)
            total = sum(widths.values()) + (gap if len(widths) == 2 else 0)
            x, y = W - margin - total, margin
            if show_subscribe:
                w, _h = _draw_subscribe(draw, x, y, scale=scale)
                x += w + gap
            if show_like:
                _draw_like(draw, x, y, scale=scale, accent_rgb=accent_rgb)
        except Exception:
            pass
        if show_equalizer:
            try:
                _draw_equalizer(draw, (int(W * 0.54), H - int(H * 0.16),
                                       W - margin, H - int(H * 0.03)),
                                accent_rgb, bars=16,
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
