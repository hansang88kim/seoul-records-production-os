"""
services/thumbnail/video_renderer_rules.py — Video Renderer background rules.

The Video Renderer uses the branded youtube_thumbnail_16x9 as the background
(same image the viewer sees as the thumbnail). The track title changes at the
bottom via FFmpeg drawtext. A clean video_playback_background is used only
when no branded thumbnail exists.
"""
from __future__ import annotations

from services.thumbnail import asset_types as AT
from services.thumbnail.asset_exporter import load_asset_manifest


# Default overlay/feature settings for video playback
VIDEO_DEFAULTS = {
    "center_playlist_title": False,
    "now_playing_card": True,
    "waveform": True,
    "cta_sticker": False,
    "cta_interval_minutes": 5,
    "film_grain": True,
}


# Marker asset_type for a clean generated source image used directly as the
# playback background (16:9, no title text) — not an Exports deliverable.
CLEAN_SOURCE_16X9 = "clean_source_16x9"


def list_video_backgrounds(limit: int = 30) -> list[dict]:
    """
    All directly-selectable 16:9 playback backgrounds across thumbnail
    sessions, newest session first (v1.0.0-alpha.47). Rendering only ever
    needs a 16:9 playback background, so the Video Renderer lets the user
    pick one of these directly instead of picking a thumbnail session and
    trusting an auto rule. Two kinds, both clean (no title text):

      1. "export" — exports/video_playback_background_16x9.png (권장)
      2. "source" — a candidate's clean generated 16:9 image

    Each option: {label, path, asset_type, is_clean_playback, session_id,
    kind, candidate_id}. Labels reuse the Library-identical session label.
    """
    from pathlib import Path
    from services.thumbnail import session_store as ss
    from services.library_labels import thumbnail_session_library_label

    options: list[dict] = []
    for sess in ss.list_sessions(limit=limit):
        sid = sess.get("session_id", "")
        try:
            cands = ss.load_candidates(sid)
        except Exception:
            cands = []
        generated = [c for c in cands if c.get("uploaded_image_path")]
        sess_label = thumbnail_session_library_label(
            sess, generated=len(generated), total=len(cands)
        )

        export = (ss.session_path(sid) / "exports"
                  / AT.EXPORT_FILENAMES[AT.VIDEO_PLAYBACK_BACKGROUND_16X9])
        if export.exists():
            options.append({
                "label": f"🎬 영상 배경 16:9 · {sess_label}",
                "path": str(export),
                "asset_type": AT.VIDEO_PLAYBACK_BACKGROUND_16X9,
                "is_clean_playback": True,
                "session_id": sid,
                "kind": "export",
                "candidate_id": None,
            })
        for c in generated:
            p = c.get("uploaded_image_path")
            if p and Path(p).exists():
                options.append({
                    "label": f"🖼️ 원본 16:9 ({c.get('candidate_id', '?')}) · {sess_label}",
                    "path": str(p),
                    "asset_type": CLEAN_SOURCE_16X9,
                    "is_clean_playback": True,
                    "session_id": sid,
                    "kind": "source",
                    "candidate_id": c.get("candidate_id"),
                })
    return options


def select_video_background(session_id: str) -> dict:
    """
    Choose the background for the Video Renderer.

    Preference order:
      1. youtube_thumbnail_16x9 (branded — same as what viewers click on)
      2. video_playback_background_16x9 (clean fallback)
    """
    manifest = load_asset_manifest(session_id)
    by_type = {a["asset_type"]: a for a in manifest}

    thumb = by_type.get(AT.YOUTUBE_THUMBNAIL_16X9)
    if thumb:
        return {
            "asset_type": AT.YOUTUBE_THUMBNAIL_16X9,
            "path": thumb["path"],
            "is_clean_playback": False,
            "warning": None,
        }

    clean = by_type.get(AT.VIDEO_PLAYBACK_BACKGROUND_16X9)
    if clean:
        return {
            "asset_type": AT.VIDEO_PLAYBACK_BACKGROUND_16X9,
            "path": clean["path"],
            "is_clean_playback": True,
            "warning": None,
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
