"""
services/video/overlay_assets.py — Canva overlay asset library (v0.7.1).

All static text/sticker/brand elements in the video are Canva-exported PNG
images — NOT FFmpeg drawtext. This module manages:
  - center_title PNG (optional, off by default for playback)
  - now_playing_card PNG (one per track)
  - cta_sticker PNG (subscribe/like/save)
  - visualizer_frame PNG (frame the waveform sits inside)

Provides a mock generator (PIL) so the pipeline works without a real Canva
call; in production these are replaced by Canva exports.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from services.thumbnail import asset_types as AT


def overlay_dir(session_path: str) -> Path:
    d = Path(session_path) / "overlay_assets"
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


# ─── Now Playing card (one per track) ────────────────────────────────────────

def make_now_playing_card(
    session_path: str,
    track_no: int,
    track_title: str,
    accent_color: str = "#ff4d6d",
) -> str | None:
    """
    Mock a 'Now Playing' card PNG (transparent) for the top-left of the video.
    In production this is a Canva-exported per-track PNG. Returns the path.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    W, H = 720, 160
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded translucent panel
    draw.rounded_rectangle([0, 0, W, H], radius=24, fill=(0, 0, 0, 150))
    accent_rgb = _hex_to_rgb(accent_color)
    draw.rounded_rectangle([0, 0, 12, H], radius=6, fill=accent_rgb + (255,))

    draw.text((40, 28), "NOW PLAYING", font=_font(28), fill=accent_rgb + (255,))
    # Truncate long titles
    title = track_title if len(track_title) <= 28 else track_title[:27] + "…"
    draw.text((40, 74), title, font=_font(44), fill=(255, 255, 255, 255))

    out = overlay_dir(session_path) / f"now_playing_{track_no:03d}.png"
    img.save(out)
    return str(out)


# ─── CTA sticker (subscribe / like / save) ───────────────────────────────────

def make_cta_sticker(
    session_path: str,
    text: str = "구독 + 좋아요",
    accent_color: str = "#ff4d6d",
) -> str | None:
    """Mock a CTA sticker PNG (transparent) for the top-right, shown on schedule."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    W, H = 420, 120
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    accent_rgb = _hex_to_rgb(accent_color)
    draw.rounded_rectangle([0, 0, W, H], radius=60, fill=accent_rgb + (235,))
    draw.text((40, 38), text, font=_font(42), fill=(255, 255, 255, 255))

    out = overlay_dir(session_path) / "cta_sticker.png"
    img.save(out)
    return str(out)


# ─── Visualizer frame (the waveform sits inside this) ────────────────────────

def make_visualizer_frame(
    session_path: str,
    accent_color: str = "#ff4d6d",
) -> str | None:
    """Mock a visualizer frame PNG (transparent) for the bottom of the video."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    W, H = 1920, 220
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Subtle baseline + side caps
    accent_rgb = _hex_to_rgb(accent_color)
    draw.line([(80, H - 40), (W - 80, H - 40)], fill=accent_rgb + (90,), width=2)

    out = overlay_dir(session_path) / "visualizer_frame.png"
    img.save(out)
    return str(out)


# ─── Center title (optional, OFF by default for playback) ────────────────────

def make_center_title(
    session_path: str,
    title: str,
    accent_color: str = "#ff4d6d",
) -> str | None:
    """
    Mock an OPTIONAL center title PNG. Off by default for video playback —
    only used if the user explicitly enables it.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    W, H = 1920, 400
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((W // 2, H // 2), title, font=_font(120), fill=(255, 255, 255, 255), anchor="mm")

    out = overlay_dir(session_path) / "center_title.png"
    img.save(out)
    return str(out)


# ─── Asset library manifest ──────────────────────────────────────────────────

def build_overlay_asset_library(
    session_path: str,
    playlist_plan: dict,
    accent_color: str = "#ff4d6d",
    cta_text: str = "구독 + 좋아요",
    make_center: bool = False,
    center_title_text: str = "",
) -> dict:
    """
    Build the full overlay asset library for a render. Generates a Now Playing
    card per unique track, one CTA sticker, one visualizer frame, and
    (optionally) a center title.

    Returns a dict describing each asset (type + path), forming the basis of
    overlay_plan.json.
    """
    library = {
        AT.NOW_PLAYING_CARD_ASSET: [],
        AT.CTA_STICKER_ASSET: None,
        AT.VISUALIZER_FRAME_ASSET: None,
        AT.CENTER_TITLE_ASSET: None,
    }

    # Now Playing card per unique track (by name)
    seen = {}
    for entry in playlist_plan.get("entries", []):
        name = entry["name"]
        if name in seen:
            continue
        track_no = len(seen) + 1
        seen[name] = track_no
        path = make_now_playing_card(session_path, track_no, name, accent_color)
        if path:
            library[AT.NOW_PLAYING_CARD_ASSET].append({
                "track_no": track_no, "track_name": name, "path": path,
            })

    library[AT.CTA_STICKER_ASSET] = make_cta_sticker(session_path, cta_text, accent_color)
    library[AT.VISUALIZER_FRAME_ASSET] = make_visualizer_frame(session_path, accent_color)

    if make_center and center_title_text:
        library[AT.CENTER_TITLE_ASSET] = make_center_title(
            session_path, center_title_text, accent_color
        )

    return library


def list_overlay_assets(session_path: str) -> list[dict]:
    """List PNG overlay assets that exist on disk."""
    d = Path(session_path) / "overlay_assets"
    if not d.exists():
        return []
    return [{"name": p.name, "path": str(p)} for p in sorted(d.glob("*.png"))]

def save_uploaded_asset(session_path: str, role: str, data: bytes,
                        track_no: int | None = None) -> str:
    """Save an uploaded Canva PNG to the overlay_assets folder."""
    d = overlay_dir(session_path)
    if role == "cta":
        name = "cta_sticker.png"
    elif role == "frame":
        name = "visualizer_frame.png"
    elif role == "now_playing":
        name = f"now_playing_{track_no:03d}.png"
    elif role == "center":
        name = "center_title.png"
    else:
        name = f"{role}.png"
    path = d / name
    path.write_bytes(data)
    return str(path)


def build_overlay_asset_library_with_uploads(
    session_path: str,
    playlist_plan: dict,
    accent_color: str = "#ff4d6d",
    cta_text: str = "구독 + 좋아요",
    uploaded: dict | None = None,
    make_center: bool = False,
    center_title_text: str = "",
) -> dict:
    """
    Build the overlay asset library, preferring UPLOADED Canva PNGs and falling
    back to mock generation for anything not uploaded.

    uploaded: {
      "cta": bytes,
      "frame": bytes,
      "now_playing": [bytes, bytes, ...]   # per track, in order
    }
    """
    uploaded = uploaded or {}

    library = {
        AT.NOW_PLAYING_CARD_ASSET: [],
        AT.CTA_STICKER_ASSET: None,
        AT.VISUALIZER_FRAME_ASSET: None,
        AT.CENTER_TITLE_ASSET: None,
    }

    # Unique tracks in order
    seen = {}
    for entry in playlist_plan.get("entries", []):
        name = entry["name"]
        if name in seen:
            continue
        seen[name] = len(seen) + 1

    # Now Playing — use uploaded per-track PNGs if provided, else mock
    np_uploads = uploaded.get("now_playing") or []
    for name, track_no in seen.items():
        if track_no - 1 < len(np_uploads):
            path = save_uploaded_asset(session_path, "now_playing",
                                       np_uploads[track_no - 1], track_no)
        else:
            path = make_now_playing_card(session_path, track_no, name, accent_color)
        if path:
            library[AT.NOW_PLAYING_CARD_ASSET].append({
                "track_no": track_no, "track_name": name, "path": path,
            })

    # CTA
    if uploaded.get("cta"):
        library[AT.CTA_STICKER_ASSET] = save_uploaded_asset(session_path, "cta", uploaded["cta"])
    else:
        library[AT.CTA_STICKER_ASSET] = make_cta_sticker(session_path, cta_text, accent_color)

    # Visualizer frame
    if uploaded.get("frame"):
        library[AT.VISUALIZER_FRAME_ASSET] = save_uploaded_asset(session_path, "frame", uploaded["frame"])
    else:
        library[AT.VISUALIZER_FRAME_ASSET] = make_visualizer_frame(session_path, accent_color)

    # Center title (optional)
    if make_center and center_title_text:
        library[AT.CENTER_TITLE_ASSET] = make_center_title(session_path, center_title_text, accent_color)

    return library
