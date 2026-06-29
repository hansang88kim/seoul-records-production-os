"""
services/thumbnail/video_renderer_rules.py — Video Renderer background rules (v0.7.0).

The Video Renderer must use the CLEAN video_playback_background_16x9 by
default — NOT the click-bait youtube_thumbnail_16x9. This module picks the
right background and surfaces a warning when only a thumbnail is available.

It also defines the overlay defaults (Now Playing / waveform / CTA are
overlays, NOT baked into the background; the large center Playlist title is
OFF by default for video).
"""
from __future__ import annotations

from services.thumbnail import asset_types as AT
from services.thumbnail.asset_exporter import load_asset_manifest


# Default overlay/feature settings for video playback
VIDEO_DEFAULTS = {
    "center_playlist_title": False,   # OFF by default — no clickbait title in video
    "now_playing_card": True,         # top-left current track
    "waveform": True,                 # bottom equalizer
    "cta_sticker": True,              # top-right, on schedule
    "cta_interval_minutes": 5,
    "film_grain": False,
}


def select_video_background(session_id: str) -> dict:
    """
    Choose the background for the Video Renderer.

    Preference order:
      1. video_playback_background_16x9 (clean — preferred)
      2. youtube_thumbnail_16x9 (fallback — WARN: has title text)

    Returns:
      {
        "asset_type": ...,
        "path": ...,
        "is_clean_playback": bool,
        "warning": str | None,
      }
    """
    manifest = load_asset_manifest(session_id)
    by_type = {a["asset_type"]: a for a in manifest}

    clean = by_type.get(AT.VIDEO_PLAYBACK_BACKGROUND_16X9)
    if clean:
        return {
            "asset_type": AT.VIDEO_PLAYBACK_BACKGROUND_16X9,
            "path": clean["path"],
            "is_clean_playback": True,
            "warning": None,
        }

    thumb = by_type.get(AT.YOUTUBE_THUMBNAIL_16X9)
    if thumb:
        return {
            "asset_type": AT.YOUTUBE_THUMBNAIL_16X9,
            "path": thumb["path"],
            "is_clean_playback": False,
            "warning": (
                "이 이미지는 썸네일 제목 텍스트를 포함합니다. 더 깨끗한 재생 화면을 위해 "
                "Video Playback Background를 사용하세요. "
                "(This image contains thumbnail title text. For cleaner playback, "
                "use a video playback background.)"
            ),
        }

    return {
        "asset_type": None,
        "path": None,
        "is_clean_playback": False,
        "warning": "사용 가능한 배경이 없습니다. Thumbnail Studio에서 Video Playback Background를 내보내세요.",
    }


def build_video_overlay_plan(
    now_playing: bool = True,
    waveform: bool = True,
    cta_sticker: bool = True,
    center_playlist_title: bool = False,
    film_grain: bool = False,
    cta_interval_minutes: int = 5,
) -> dict:
    """
    Build the overlay plan for the Video Renderer. Now Playing / waveform /
    CTA are overlays applied on top of the clean background. The center
    playlist title is OFF by default.
    """
    return {
        "center_playlist_title": bool(center_playlist_title),
        "overlays": {
            AT.NOW_PLAYING_CARD_ASSET: bool(now_playing),
            AT.DYNAMIC_VISUALIZER_OVERLAY: bool(waveform),
            AT.CTA_STICKER_ASSET: bool(cta_sticker),
            AT.FILM_GRAIN_OVERLAY: bool(film_grain),
        },
        "cta_interval_minutes": int(cta_interval_minutes),
    }
