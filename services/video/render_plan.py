"""
services/video/render_plan.py — MP3-first video render orchestration (v0.7.1).

Builds the render plan and FFmpeg commands for a longform music video:
  - audio: MP3 concat (NO WAV required, NO fake WAV created)
  - background: prefers video_playback_background_16x9 (clean), warns on thumbnail
  - overlays: Canva PNGs (Now Playing / CTA / visualizer frame) — NOT drawtext
  - visualizer: audio-reactive from the real MP3
  - preview: 15s / 30s / full

Layer order (bottom → top):
  background → visualizer → visualizer_frame → now_playing → cta_sticker
  → (optional center_title) → (optional film_grain)

This module produces plans + commands. Actual FFmpeg execution is done by the
caller; tests assert on the plan/commands without running long renders.
"""
from __future__ import annotations

import json
from pathlib import Path

from services.thumbnail import asset_types as AT


# Canonical overlay layer order (bottom to top)
LAYER_ORDER = [
    "background",
    AT.DYNAMIC_VISUALIZER_OVERLAY,
    AT.VISUALIZER_FRAME_ASSET,
    AT.NOW_PLAYING_CARD_ASSET,
    AT.CTA_STICKER_ASSET,
    AT.CENTER_TITLE_ASSET,   # optional, off by default
    AT.FILM_GRAIN_OVERLAY,   # optional
]


def build_mp3_concat_list(out_dir: str, playlist_plan: dict) -> str:
    """
    Write an FFmpeg concat-demuxer list file referencing MP3s (no WAV).
    Returns the path to the concat list.
    """
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    lines = []
    for entry in playlist_plan.get("entries", []):
        p = entry["path"].replace("'", "'\\''")
        lines.append(f"file '{p}'")
    list_path = d / "mp3_concat_list.txt"
    list_path.write_text("\n".join(lines), encoding="utf-8")
    return str(list_path)


def build_audio_mix_command(
    concat_list: str,
    out_dir: str,
    make_mp3_mix: bool = False,
) -> dict:
    """
    Build the audio concat command. By default NO audio mix file is created
    (the MP3 concat list feeds the video directly). Optionally produce
    final_audio_mix.mp3 (NEVER a WAV, NEVER a fake WAV).

    Returns {"command": [...], "output": path|None}.
    """
    if not make_mp3_mix:
        return {"command": [], "output": None}

    out_path = str(Path(out_dir) / "final_audio_mix.mp3")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
        "-c:a", "libmp3lame", "-q:a", "2", out_path,
    ]
    return {"command": cmd, "output": out_path}


def select_background(session_path: str) -> dict:
    """
    Pick the video background. Prefers the clean playback background; warns if
    only the thumbnail (with title text) is available.
    Delegates to video_renderer_rules.select_video_background by session_id.
    """
    from services.thumbnail.video_renderer_rules import select_video_background as _sel
    # session_path may be a full path; derive the session_id (folder name)
    session_id = Path(session_path).name
    return _sel(session_id)


def build_render_plan(
    out_dir: str,
    playlist_plan: dict,
    background: dict,
    overlay_library: dict,
    visualizer_cfg: dict,
    enable_now_playing: bool = True,
    enable_cta: bool = True,
    enable_visualizer: bool = True,
    enable_center_title: bool = False,
    enable_film_grain: bool = False,
    cta_interval_minutes: int = 5,
    cta_duration_seconds: int = 12,
) -> dict:
    """
    Build the full render plan (overlay_plan + render_plan in one structure).
    """
    # Compute CTA schedule across the total duration
    total = playlist_plan.get("total_seconds", 0)
    cta_schedule = []
    if enable_cta:
        t = cta_interval_minutes * 60
        while t < total:
            cta_schedule.append({"start_sec": t, "end_sec": t + cta_duration_seconds})
            t += cta_interval_minutes * 60

    # Now Playing schedule follows chapter timing
    now_playing_schedule = []
    if enable_now_playing:
        np_assets = {a["track_name"]: a["path"]
                     for a in overlay_library.get(AT.NOW_PLAYING_CARD_ASSET, [])}
        for ch in playlist_plan.get("chapters", []):
            # match by base name (strip repeat suffix)
            base = ch["title"].split(" (반복")[0]
            png = np_assets.get(base)
            now_playing_schedule.append({
                "track_name": base,
                "png": png,
                "start_sec": ch["start_sec"],
                "end_sec": ch["end_sec"],
            })

    # Build the active layer order (only enabled layers)
    active_layers = ["background"]
    if enable_visualizer:
        active_layers.append(AT.DYNAMIC_VISUALIZER_OVERLAY)
        if overlay_library.get(AT.VISUALIZER_FRAME_ASSET):
            active_layers.append(AT.VISUALIZER_FRAME_ASSET)
    if enable_now_playing:
        active_layers.append(AT.NOW_PLAYING_CARD_ASSET)
    if enable_cta:
        active_layers.append(AT.CTA_STICKER_ASSET)
    if enable_center_title and overlay_library.get(AT.CENTER_TITLE_ASSET):
        active_layers.append(AT.CENTER_TITLE_ASSET)
    if enable_film_grain:
        active_layers.append(AT.FILM_GRAIN_OVERLAY)

    overlay_plan = {
        "layer_order": active_layers,
        "now_playing": {
            "enabled": enable_now_playing,
            "position": "top-left",
            "uses_png": True,           # Canva PNG, not drawtext
            "schedule": now_playing_schedule,
        },
        "cta_sticker": {
            "enabled": enable_cta,
            "position": "top-right",
            "uses_png": True,           # Canva PNG, not drawtext
            "png": overlay_library.get(AT.CTA_STICKER_ASSET),
            "interval_minutes": cta_interval_minutes,
            "duration_seconds": cta_duration_seconds,
            "schedule": cta_schedule,
        },
        "visualizer": {
            "enabled": enable_visualizer,
            "audio_reactive": True,
            "config": visualizer_cfg,
            "frame_png": overlay_library.get(AT.VISUALIZER_FRAME_ASSET),
        },
        "center_title": {
            "enabled": enable_center_title,   # OFF by default
            "uses_png": True,
            "png": overlay_library.get(AT.CENTER_TITLE_ASSET),
        },
        "film_grain": {"enabled": enable_film_grain},
    }

    render_plan = {
        "background": background,
        "audio_source": "mp3",            # MP3-first, no WAV
        "no_fake_wav": True,
        "output": str(Path(out_dir) / "final_video.mp4"),
        "resolution": [1920, 1080],
        "aspect_ratio": "16:9",
        "total_seconds": total,
    }

    return {"overlay_plan": overlay_plan, "render_plan": render_plan}


def build_preview_command(
    concat_list: str,
    background_path: str,
    out_dir: str,
    seconds: int = 30,
) -> dict:
    """
    Build a short preview render command (15s / 30s) so the user can check the
    visual effects before the full render. MP3 input, no WAV.
    Returns {"command": [...], "output": path}.
    """
    out_path = str(Path(out_dir) / f"preview_{seconds}s.mp4")
    bg = background_path or ""
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", bg,                         # background image
        "-f", "concat", "-safe", "0", "-i", concat_list,  # MP3 audio
        "-t", str(seconds),
        "-vf", "scale=1920:1080",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        out_path,
    ]
    return {"command": cmd, "output": out_path, "seconds": seconds}


def build_full_render_command(
    concat_list: str,
    background_path: str,
    out_dir: str,
    total_seconds: float,
) -> dict:
    """Build the full-length render command. MP3 input, 16:9, no WAV."""
    out_path = str(Path(out_dir) / "final_video.mp4")
    bg = background_path or ""
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", bg,
        "-f", "concat", "-safe", "0", "-i", concat_list,
        "-t", str(int(total_seconds)),
        "-vf", "scale=1920:1080",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        out_path,
    ]
    return {"command": cmd, "output": out_path}


def save_plans(out_dir: str, plans: dict, playlist_plan: dict) -> dict:
    """Save render_plan.json, overlay_plan.json, playlist_plan.json, chapters.txt."""
    from services.video.playlist_builder import format_chapters_txt
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)

    paths = {}
    (d / "render_plan.json").write_text(
        json.dumps(plans["render_plan"], ensure_ascii=False, indent=2), encoding="utf-8")
    paths["render_plan"] = str(d / "render_plan.json")

    (d / "overlay_plan.json").write_text(
        json.dumps(plans["overlay_plan"], ensure_ascii=False, indent=2), encoding="utf-8")
    paths["overlay_plan"] = str(d / "overlay_plan.json")

    (d / "playlist_plan.json").write_text(
        json.dumps(playlist_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["playlist_plan"] = str(d / "playlist_plan.json")

    (d / "chapters.txt").write_text(format_chapters_txt(playlist_plan), encoding="utf-8")
    paths["chapters"] = str(d / "chapters.txt")

    return paths
