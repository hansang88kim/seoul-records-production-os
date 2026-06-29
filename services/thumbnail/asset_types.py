"""
services/thumbnail/asset_types.py — Output asset type definitions (v0.7.0).

Separates the three final deliverables so they never get mixed:
  - YouTube Thumbnail (광고판)  : click-bait, branded title, 16:9
  - Video Playback Background (무대): clean, no center title, 16:9
  - Streaming Cover (앨범 자켓)  : derived from thumbnail, title kept, 1:1

Each asset carries explicit content flags (contains_playlist_title,
contains_song_title, contains_waveform, contains_cta_sticker) so the
Video Renderer and distribution steps can pick the right one.
"""
from __future__ import annotations


# Asset type constants
YOUTUBE_THUMBNAIL_16X9 = "youtube_thumbnail_16x9"
VIDEO_PLAYBACK_BACKGROUND_16X9 = "video_playback_background_16x9"
STREAMING_COVER_1X1 = "streaming_cover_1x1"
CENTER_TITLE_ASSET = "center_title_asset"
NOW_PLAYING_CARD_ASSET = "now_playing_card_asset"
CTA_STICKER_ASSET = "cta_sticker_asset"
VISUALIZER_FRAME_ASSET = "visualizer_frame_asset"
DYNAMIC_VISUALIZER_OVERLAY = "dynamic_visualizer_overlay"
FILM_GRAIN_OVERLAY = "film_grain_overlay"


# All known asset types
ASSET_TYPES = [
    YOUTUBE_THUMBNAIL_16X9,
    VIDEO_PLAYBACK_BACKGROUND_16X9,
    STREAMING_COVER_1X1,
    CENTER_TITLE_ASSET,
    NOW_PLAYING_CARD_ASSET,
    CTA_STICKER_ASSET,
    VISUALIZER_FRAME_ASSET,
    DYNAMIC_VISUALIZER_OVERLAY,
    FILM_GRAIN_OVERLAY,
]

# The three required image deliverables
REQUIRED_OUTPUT_TYPES = [
    YOUTUBE_THUMBNAIL_16X9,
    VIDEO_PLAYBACK_BACKGROUND_16X9,
    STREAMING_COVER_1X1,
]

# Canonical export filenames per asset type
EXPORT_FILENAMES = {
    YOUTUBE_THUMBNAIL_16X9: "youtube_thumbnail_16x9.png",
    VIDEO_PLAYBACK_BACKGROUND_16X9: "video_playback_background_16x9.png",
    STREAMING_COVER_1X1: "streaming_cover_1x1.png",
}

# Recommended canvas sizes
CANVAS_SIZES = {
    YOUTUBE_THUMBNAIL_16X9: (1920, 1080),
    VIDEO_PLAYBACK_BACKGROUND_16X9: (1920, 1080),
    STREAMING_COVER_1X1: (3000, 3000),
}

# Aspect ratios
ASPECT_RATIOS = {
    YOUTUBE_THUMBNAIL_16X9: "16:9",
    VIDEO_PLAYBACK_BACKGROUND_16X9: "16:9",
    STREAMING_COVER_1X1: "1:1",
}


def default_content_flags(asset_type: str) -> dict:
    """
    Return the correct content flags for an asset type.
    These encode WHAT each deliverable is allowed to contain.
    """
    if asset_type == YOUTUBE_THUMBNAIL_16X9:
        return {
            "contains_playlist_title": True,   # branded title
            "contains_song_title": False,
            "contains_waveform": False,
            "contains_cta_sticker": False,
        }
    elif asset_type == VIDEO_PLAYBACK_BACKGROUND_16X9:
        return {
            "contains_playlist_title": False,  # clean — no center title
            "contains_song_title": False,
            "contains_waveform": False,
            "contains_cta_sticker": False,
        }
    elif asset_type == STREAMING_COVER_1X1:
        return {
            "contains_playlist_title": True,   # title preserved from thumbnail
            "contains_song_title": False,
            "contains_waveform": False,
            "contains_cta_sticker": False,
        }
    # Overlay assets
    return {
        "contains_playlist_title": False,
        "contains_song_title": False,
        "contains_waveform": False,
        "contains_cta_sticker": False,
    }


def default_usage(asset_type: str) -> list[str]:
    """Return the usage tags for an asset type."""
    usage_map = {
        YOUTUBE_THUMBNAIL_16X9: ["youtube_thumbnail"],
        VIDEO_PLAYBACK_BACKGROUND_16X9: ["video_background"],
        STREAMING_COVER_1X1: ["streaming_cover", "playlist_cover"],
        CENTER_TITLE_ASSET: ["video_overlay"],
        NOW_PLAYING_CARD_ASSET: ["video_overlay"],
        CTA_STICKER_ASSET: ["video_overlay"],
        VISUALIZER_FRAME_ASSET: ["video_overlay"],
        DYNAMIC_VISUALIZER_OVERLAY: ["video_overlay"],
        FILM_GRAIN_OVERLAY: ["video_overlay"],
    }
    return usage_map.get(asset_type, [])
