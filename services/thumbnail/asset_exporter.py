"""
services/thumbnail/asset_exporter.py — Export the 3 separated deliverables (v0.7.0).

  A. YouTube Thumbnail 16:9       — branded title (광고판)
  B. Video Playback Background 16:9 — clean, no center title (무대)
  C. Streaming Cover 1:1          — derived from thumbnail, title kept (앨범 자켓)

Plus a 1:1 crop tool (center / title-safe / fit-with-blur / manual) and a
combined asset_manifest.json. No real Canva calls; PIL local rendering only.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from services.thumbnail import asset_types as AT
from services.thumbnail.session_store import session_path


def _exports_dir(session_id: str) -> Path:
    d = session_path(session_id) / "exports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _font(size: int):
    from PIL import ImageFont
    for fp in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = (hex_color or "#ff4d6d").lstrip("#")
    if len(h) != 6:
        return (255, 77, 109)
    try:
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return (255, 77, 109)


def _load_bg(bg_path: str, size: tuple[int, int]):
    """Load a background image cropped/resized to fill `size`, or a placeholder."""
    from PIL import Image
    W, H = size
    try:
        if bg_path and Path(bg_path).exists():
            img = Image.open(bg_path).convert("RGB")
            # Cover-fit (fill then center-crop)
            iw, ih = img.size
            scale = max(W / iw, H / ih)
            img = img.resize((int(iw * scale), int(ih * scale)))
            left = (img.width - W) // 2
            top = (img.height - H) // 2
            return img.crop((left, top, left + W, top + H))
    except Exception:
        pass
    return Image.new("RGB", (W, H), (26, 34, 56))


# ─── A. YouTube Thumbnail 16:9 (branded, click-bait) ─────────────────────────

def export_youtube_thumbnail(
    session_id: str,
    bg_path: str,
    title: str,
    subtitle: str,
    brand_text: str,
    accent_color: str,
    title_color: str = "#FFFFFF",
    title_scale: float = 1.0,
    cjk_subtext: str = "",
) -> str | None:
    """
    Export a branded YouTube thumbnail (16:9). Contains the Playlist/CityPop/Vol.
    title. No song title, no waveform, no CTA sticker.
    """
    try:
        from services.thumbnail.canva_branding import render_premium_thumbnail
    except Exception:
        return None

    W, H = AT.CANVAS_SIZES[AT.YOUTUBE_THUMBNAIL_16X9]
    img = render_premium_thumbnail(bg_path, title, subtitle, brand_text, accent_color,
                                   W, H, with_title=True,
                                   title_color=title_color, title_scale=title_scale,
                                   cjk_subtext=cjk_subtext)

    out = _exports_dir(session_id) / AT.EXPORT_FILENAMES[AT.YOUTUBE_THUMBNAIL_16X9]
    img.save(out)
    # Optional JPG
    try:
        img.save(out.with_suffix(".jpg"), quality=95)
    except Exception:
        pass
    return str(out)


# ─── B. Video Playback Background 16:9 (clean, no center title) ───────────────

def export_video_playback_background(
    session_id: str,
    bg_path: str,
    brand_text: str = "Seoul Records",
    subtle_logo: bool = True,
) -> str | None:
    """
    Export a CLEAN playback background (16:9) for the Video Renderer.
    No large center title. Optional subtle logo only. Leaves safe areas for
    the top-left Now Playing card, top-right CTA sticker, bottom waveform.
    """
    try:
        from services.thumbnail.canva_branding import render_premium_thumbnail
    except Exception:
        return None

    W, H = AT.CANVAS_SIZES[AT.VIDEO_PLAYBACK_BACKGROUND_16X9]
    img = render_premium_thumbnail(bg_path, "", "",
                                   brand_text if subtle_logo else "",
                                   "#ffffff", W, H, with_title=False)

    out = _exports_dir(session_id) / AT.EXPORT_FILENAMES[AT.VIDEO_PLAYBACK_BACKGROUND_16X9]
    img.save(out)
    return str(out)


# ─── C. Streaming Cover 1:1 (derived from thumbnail, title kept) ─────────────

def export_streaming_cover(
    session_id: str,
    source_thumbnail_path: str,
    bg_path: str = "",
    title: str = "",
    subtitle: str = "",
    brand_text: str = "Seoul Records",
    accent_color: str = "#ff4d6d",
    crop_mode: str = "smart_title_safe",
    title_color: str = "#FFFFFF",
    title_scale: float = 1.0,
    cjk_subtext: str = "",
    square_bg_path: str = "",
) -> str | None:
    """
    Export a 1:1 streaming/playlist cover. When a native square background
    (``square_bg_path`` — generated at 1:1) is available it is used directly so
    the cover is never a stretched/cropped 16:9; otherwise falls back to ``bg_path``.
    Preserves the Playlist title. No song title, waveform, or CTA sticker.

    crop_mode: center_crop | smart_title_safe | fit_blur | manual
    """
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        return None

    S = AT.CANVAS_SIZES[AT.STREAMING_COVER_1X1][0]  # 3000

    # Prefer a native 1:1 source (no distortion); fall back to the 16:9 bg.
    cover_bg = square_bg_path if (square_bg_path and Path(square_bg_path).exists()) else bg_path

    cover = None
    if cover_bg and Path(cover_bg).exists():
        # Fresh, properly-composed square cover (premium centered title) — avoids
        # the cropped/cut-off title you get from squaring a 16:9 thumbnail.
        try:
            from services.thumbnail.canva_branding import render_premium_thumbnail
            cover = render_premium_thumbnail(cover_bg, title, subtitle, brand_text,
                                             accent_color, S, S, with_title=True,
                                             title_color=title_color,
                                             title_scale=title_scale,
                                             cjk_subtext=cjk_subtext)
        except Exception:
            cover = None
    if cover is None:
        src = Path(source_thumbnail_path)
        if src.exists():
            cover = crop_to_square(source_thumbnail_path, S, crop_mode)
        else:
            cover = _render_square_cover(bg_path, title, subtitle, brand_text, accent_color, S)

    if cover is None:
        return None

    out = _exports_dir(session_id) / AT.EXPORT_FILENAMES[AT.STREAMING_COVER_1X1]
    cover.save(out)
    try:
        cover.save(out.with_suffix(".jpg"), quality=95)
    except Exception:
        pass
    return str(out)


def crop_to_square(image_path: str, size: int, crop_mode: str = "center_crop"):
    """
    Crop/resize an image to a square. Returns a PIL Image (or None).

    Modes:
      center_crop       — crop the center square
      smart_title_safe  — bias the crop to keep the lower-left title area
      fit_blur          — fit whole image, fill padding with blurred background
      manual            — same as center for now (UI provides offsets later)
    """
    try:
        from PIL import Image, ImageFilter
    except ImportError:
        return None

    src = Path(image_path)
    if not src.exists():
        return None

    img = Image.open(image_path).convert("RGB")
    w, h = img.size

    if crop_mode == "fit_blur":
        # Blurred fill background + centered fitted image
        bg = img.resize((size, size)).filter(ImageFilter.GaussianBlur(40))
        scale = min(size / w, size / h)
        fitted = img.resize((int(w * scale), int(h * scale)))
        bg.paste(fitted, ((size - fitted.width) // 2, (size - fitted.height) // 2))
        return bg

    # Determine square crop box
    side = min(w, h)
    if crop_mode == "smart_title_safe":
        # Keep the lower-left (where the title usually sits): crop from the left,
        # and bias the vertical box toward the bottom.
        left = 0
        top = h - side  # bottom-aligned
        if top < 0:
            top = 0
    else:  # center_crop / manual default
        left = (w - side) // 2
        top = (h - side) // 2

    box = (left, top, left + side, top + side)
    square = img.crop(box).resize((size, size))
    return square


def _render_square_cover(bg_path, title, subtitle, brand_text, accent_color, S):
    """Render a 1:1 branded cover from scratch (fallback when no thumbnail)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    img = _load_bg(bg_path, (S, S))
    draw = ImageDraw.Draw(img, "RGBA")
    for y in range(S):
        alpha = int(190 * (y / S) ** 1.5)
        draw.line([(0, y), (S, y)], fill=(0, 0, 0, alpha))
    margin = int(S * 0.06)
    accent_rgb = _hex_to_rgb(accent_color)
    draw.text((margin, margin), brand_text or "Seoul Records",
              font=_font(int(S * 0.045)), fill="#FFFFFF")
    draw.rectangle([margin, int(S * 0.70), margin + int(S * 0.08), int(S * 0.72)],
                   fill=accent_rgb)
    draw.text((margin, int(S * 0.74)), title, font=_font(int(S * 0.09)), fill="#FFFFFF")
    if subtitle:
        draw.text((margin, int(S * 0.88)), subtitle,
                  font=_font(int(S * 0.045)), fill=accent_rgb)
    return img


# ─── Asset manifest ──────────────────────────────────────────────────────────

def _make_asset_entry(session_id: str, asset_type: str, path: str) -> dict:
    return {
        "asset_id": uuid.uuid4().hex[:12],
        "session_id": session_id,
        "asset_type": asset_type,
        "path": path,
        "aspect_ratio": AT.ASPECT_RATIOS.get(asset_type, ""),
        **AT.default_content_flags(asset_type),
        "usage": AT.default_usage(asset_type),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def write_asset_manifest(session_id: str, assets: list[dict]) -> str:
    """Write asset_manifest.json listing all exported assets with their flags."""
    path = _exports_dir(session_id) / "asset_manifest.json"
    path.write_text(json.dumps(assets, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def load_asset_manifest(session_id: str) -> list[dict]:
    path = session_path(session_id) / "exports" / "asset_manifest.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def export_all_required_assets(
    session_id: str,
    bg_path: str,
    title: str,
    subtitle: str,
    brand_text: str,
    accent_color: str,
    crop_mode: str = "smart_title_safe",
    title_color: str = "#FFFFFF",
    title_scale: float = 1.0,
    cjk_subtext: str = "",
    square_bg_path: str = "",
) -> dict:
    """
    Export all three required deliverables + write the asset manifest.
    ``bg_path`` is the native 16:9 background; ``square_bg_path`` (optional) is the
    native 1:1 background used for the streaming cover so it isn't a squashed 16:9.
    Returns {asset_type: path} plus 'manifest'.
    """
    results: dict[str, str] = {}
    assets: list[dict] = []

    # A. YouTube thumbnail (the source for the streaming cover)
    yt = export_youtube_thumbnail(session_id, bg_path, title, subtitle, brand_text,
                                  accent_color, title_color, title_scale, cjk_subtext)
    if yt:
        results[AT.YOUTUBE_THUMBNAIL_16X9] = yt
        assets.append(_make_asset_entry(session_id, AT.YOUTUBE_THUMBNAIL_16X9, yt))

    # B. Video playback background (clean)
    vb = export_video_playback_background(session_id, bg_path, brand_text)
    if vb:
        results[AT.VIDEO_PLAYBACK_BACKGROUND_16X9] = vb
        assets.append(_make_asset_entry(session_id, AT.VIDEO_PLAYBACK_BACKGROUND_16X9, vb))

    # C. Streaming cover — prefer the native 1:1 background.
    sc = export_streaming_cover(session_id, yt or "", bg_path, title, subtitle,
                                brand_text, accent_color, crop_mode,
                                title_color, title_scale, cjk_subtext, square_bg_path)
    if sc:
        results[AT.STREAMING_COVER_1X1] = sc
        assets.append(_make_asset_entry(session_id, AT.STREAMING_COVER_1X1, sc))

    manifest = write_asset_manifest(session_id, assets)
    results["manifest"] = manifest
    return results
