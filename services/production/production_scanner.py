"""
services/production/production_scanner.py — outputs/ asset scanner (v0.8.4).

Scans the global outputs/ folder for every artifact needed to produce one
YouTube CityPop playlist end-to-end, and returns a structured snapshot. Read
only — never modifies anything.
"""
from __future__ import annotations

from pathlib import Path


def _outputs_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "outputs"


def _exists_glob(root: Path, pattern: str) -> list[str]:
    if not root.exists():
        return []
    return [str(p) for p in root.rglob(pattern) if p.is_file()]


def _mp3_duration(path: str) -> float:
    try:
        import mutagen.mp3
        return float(mutagen.mp3.MP3(path).info.length or 0.0)
    except Exception:
        try:
            return Path(path).stat().st_size / (128 * 1024 / 8)
        except Exception:
            return 0.0


def scan_song_assets() -> dict:
    """MP3 files across outputs/ + total duration."""
    root = _outputs_root()
    mp3s = _exists_glob(root, "*.mp3")
    total = sum(_mp3_duration(m) for m in mp3s)
    return {
        "mp3_files": mp3s,
        "mp3_count": len(mp3s),
        "total_duration_sec": round(total, 1),
    }


def _first(paths: list[str]) -> str | None:
    return paths[0] if paths else None


def scan_thumbnail_assets() -> dict:
    """YouTube thumbnail / playback background / streaming cover / manifest."""
    root = _outputs_root() / "thumbnail_studio"
    return {
        "youtube_thumbnail": _first(
            _exists_glob(root, "youtube_thumbnail_16x9.png")
            + _exists_glob(root, "youtube_thumbnail_16x9.jpg")
            + _exists_glob(root, "youtube_thumbnail_16x9.jpeg")),
        "video_playback_background": _first(
            _exists_glob(root, "video_playback_background_16x9.png")
            + _exists_glob(root, "video_playback_background_16x9.jpg")),
        "streaming_cover": _first(
            _exists_glob(root, "streaming_cover_1x1.png")
            + _exists_glob(root, "streaming_cover_1x1.jpg")),
        "asset_manifest": _first(_exists_glob(root, "asset_manifest.json")),
    }


def scan_canva_overlays() -> dict:
    """CTA / Now Playing / visualizer frame / center title PNGs."""
    root = _outputs_root()
    now_playing = _exists_glob(root, "now_playing_*.png")
    return {
        "cta_sticker": _first(_exists_glob(root, "cta_sticker.png")),
        "now_playing_cards": now_playing,
        "now_playing_count": len(now_playing),
        "visualizer_frame": _first(_exists_glob(root, "visualizer_frame.png")),
        "center_title": _first(_exists_glob(root, "center_title.png")),
    }


def scan_video_render() -> dict:
    """Preview / final video / plans / chapters / render state."""
    root = _outputs_root() / "video_renderer"
    final_videos = _exists_glob(root, "final_video.mp4")
    # render_state completion
    render_completed = False
    for sp in _exists_glob(root, "render_state.json"):
        try:
            import json
            st = json.loads(Path(sp).read_text(encoding="utf-8"))
            if st.get("status") == "completed":
                render_completed = True
                break
        except Exception:
            pass
    return {
        "preview_30s": _first(_exists_glob(root, "preview_30s.mp4")),
        "preview_15s": _first(_exists_glob(root, "preview_15s.mp4")),
        "final_video": _first(final_videos),
        "final_video_count": len(final_videos),
        "chapters": _first(_exists_glob(root, "chapters.txt")),
        "playlist_plan": _first(_exists_glob(root, "playlist_plan.json")),
        "render_plan": _first(_exists_glob(root, "render_plan.json")),
        "overlay_plan": _first(_exists_glob(root, "overlay_plan.json")),
        "ffmpeg_progress": _first(_exists_glob(root, "ffmpeg_progress.jsonl")),
        "render_completed": render_completed,
    }


def scan_youtube_package() -> dict:
    """Package metadata files + zip + payload."""
    root = _outputs_root() / "youtube_package"
    return {
        "package_manifest": _first(_exists_glob(root, "package_manifest.json")),
        "title": _first(_exists_glob(root, "title.txt")),
        "description": _first(_exists_glob(root, "description.txt")),
        "tags": _first(_exists_glob(root, "tags.txt")),
        "hashtags": _first(_exists_glob(root, "hashtags.txt")),
        "pinned_comment": _first(_exists_glob(root, "pinned_comment.txt")),
        "thumbnail_upload_ready": _first(
            _exists_glob(root, "thumbnail_upload_ready.jpg")
            + _exists_glob(root, "thumbnail_upload_ready.png")),
        "manual_upload_package_zip": _first(_exists_glob(root, "manual_upload_package.zip")),
        "youtube_upload_payload": _first(_exists_glob(root, "youtube_upload_payload.json")),
    }


def scan_upload_readiness() -> dict:
    """OAuth / API deps / upload result."""
    from services.youtube.dependency_check import check_youtube_api_dependencies
    from services.youtube import token_store as ts

    dep = check_youtube_api_dependencies()
    status = ts.get_status()
    upload_result = _first(_exists_glob(_outputs_root() / "youtube_upload", "upload_result.json"))
    return {
        "api_dependencies_ready": dep["available"],
        "api_dependencies_missing": dep["missing"],
        "oauth_status": status.get("status", "not_configured"),
        "oauth_configured": status.get("status") in ("authorized", "client_secrets_loaded"),
        "upload_result": upload_result,
    }


def scan_unitedmasters() -> dict:
    """UnitedMasters package + distribution readiness."""
    root = _outputs_root() / "unitedmasters_package"
    manifest = _first(_exists_glob(root, "package_manifest.json"))
    distribution_ready = False
    mp3_only = False
    has_master = False
    if manifest:
        try:
            import json
            mf = json.loads(Path(manifest).read_text(encoding="utf-8"))
            distribution_ready = bool(mf.get("distribution_ready"))
            mp3_only = bool(mf.get("mp3_only"))
        except Exception:
            pass
    # Any real WAV/FLAC master present in a package?
    has_master = bool(_exists_glob(root, "*.wav") + _exists_glob(root, "*.flac"))
    return {
        "package_manifest": manifest,
        "tracklist_csv": _first(_exists_glob(root, "tracklist.csv")),
        "manual_checklist": _first(_exists_glob(root, "unitedmasters_manual_upload_checklist.md")),
        "distribution_ready": distribution_ready,
        "mp3_only": mp3_only,
        "has_wav_flac_master": has_master,
    }


def scan_all() -> dict:
    """Full production snapshot."""
    return {
        "songs": scan_song_assets(),
        "thumbnails": scan_thumbnail_assets(),
        "overlays": scan_canva_overlays(),
        "video": scan_video_render(),
        "youtube_package": scan_youtube_package(),
        "upload": scan_upload_readiness(),
        "unitedmasters": scan_unitedmasters(),
    }