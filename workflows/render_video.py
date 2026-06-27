"""
Seoul Records Production OS — Video Render Workflow (FFmpeg)
"""
from __future__ import annotations
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime, timezone

from app.models import ProjectManifest
from app.project_manager import save_manifest, log_action
from app.state_machine import ProjectStatus


def _format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def _get_audio_duration_ffprobe(wav_path: Path) -> float | None:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(wav_path)],
            capture_output=True, text=True, timeout=10
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def generate_timestamps(manifest: ProjectManifest, output_folder: Path) -> tuple[str, str]:
    """
    Generate timestamps.txt and youtube_chapters.txt.
    Returns (timestamps_text, chapters_text).
    """
    tracks = manifest.approved_tracks()
    # Fix 7: chapters start at 00:00 with first track — NO "Intro" prefix
    timestamp_lines = []
    chapter_lines = []
    current = 0.0

    for t in tracks:
        ts = _format_timestamp(current)
        timestamp_lines.append(f"{ts} — {t.track_number:02d}. {t.prompt.title}")
        chapter_lines.append(f"{ts} {t.track_number:02d}. {t.prompt.title}")
        dur = t.duration_seconds or 210.0
        current += dur

    timestamps_text = "\n".join(timestamp_lines)
    chapters_text = "\n".join(chapter_lines)
    return timestamps_text, chapters_text


def build_ffmpeg_command(
    audio_list_path: Path,
    background_image_path: Path,
    output_video_path: Path,
) -> str:
    """Build the FFmpeg render command string."""
    return (
        f'ffmpeg -loop 1 -i "{background_image_path}" '
        f'-f concat -safe 0 -i "{audio_list_path}" '
        f'-c:v libx264 -tune stillimage -c:a aac -b:a 320k '
        f'-pix_fmt yuv420p -shortest '
        f'"{output_video_path}"'
    )


def export_video_package(
    manifest: ProjectManifest,
    output_folder: Path,
    background_image_path: Path | None = None,
) -> dict:
    """
    Generate timestamps, chapters, FFmpeg command, and optionally render video.
    Returns result dict.
    """
    video_root = output_folder / "03_longform_video"
    input_dir = video_root / "input"
    timestamps_dir = video_root / "timestamps"
    scripts_dir = video_root / "render_scripts"
    out_dir = video_root / "output"

    for d in [input_dir, timestamps_dir, scripts_dir, out_dir]:
        d.mkdir(parents=True, exist_ok=True)

    tracks = manifest.approved_tracks()

    # Audio list for FFmpeg concat — always use absolute paths
    audio_lines = []
    for t in tracks:
        if t.selected_wav_path and Path(t.selected_wav_path).exists():
            abs_path = Path(t.selected_wav_path).resolve()
            audio_lines.append(f"file '{abs_path}'")
    audio_list_path = input_dir / "selected_audio_list.txt"
    audio_list_path.write_text("\n".join(audio_lines), encoding="utf-8")

    # Background image
    if background_image_path and background_image_path.exists():
        dest_bg = input_dir / "background_image.jpg"
        shutil.copy2(background_image_path, dest_bg)
        bg_path = dest_bg
    else:
        # Check for thumbnail from step 2
        thumb = output_folder / "02_thumbnail_cover" / "final" / "youtube_thumbnail_16x9.png"
        bg_path = thumb if thumb.exists() else input_dir / "background_image.jpg"

    # Timestamps
    timestamps_text, chapters_text = generate_timestamps(manifest, output_folder)
    (timestamps_dir / "timestamps.txt").write_text(timestamps_text, encoding="utf-8")
    (timestamps_dir / "youtube_chapters.txt").write_text(chapters_text, encoding="utf-8")

    # FFmpeg command
    output_video_path = out_dir / "final_video.mp4"
    ffmpeg_cmd = build_ffmpeg_command(audio_list_path, bg_path, output_video_path)
    (scripts_dir / "ffmpeg_render_command.txt").write_text(ffmpeg_cmd, encoding="utf-8")

    total_duration = sum((t.duration_seconds or 210.0) for t in tracks)

    render_config = {
        "track_count": len(tracks),
        "total_duration_seconds": total_duration,
        "total_duration_formatted": _format_timestamp(total_duration),
        "output_type": manifest.output_type,
        "ffmpeg_available": _ffmpeg_available(),
        "ffprobe_available": _ffprobe_available(),
        "background_image": str(bg_path),
        "audio_list": str(audio_list_path),
        "output_video": str(output_video_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (scripts_dir / "render_config.json").write_text(json.dumps(render_config, indent=2), encoding="utf-8")

    # Attempt real render if FFmpeg is available and we have audio
    rendered = False
    audio_mix_path: Path | None = None

    if _ffmpeg_available() and audio_lines:
        # ── 4a: Render final_video.mp4 ────────────────────────────────────────
        try:
            result = subprocess.run(
                ffmpeg_cmd, shell=True, capture_output=True, text=True, timeout=600
            )
            if result.returncode == 0 and output_video_path.exists():
                rendered = True
                log_action(output_folder, "video_render", "ffmpeg_render_success",
                           {"output": str(output_video_path)}, project_id=manifest.project_id)
            else:
                log_action(output_folder, "video_render", "ffmpeg_render_failed",
                           {"returncode": result.returncode, "stderr": result.stderr[:300]},
                           level="WARNING", project_id=manifest.project_id)
        except subprocess.TimeoutExpired:
            log_action(output_folder, "video_render", "ffmpeg_render_timeout",
                       {}, level="WARNING", project_id=manifest.project_id)
        except Exception as e:
            log_action(output_folder, "video_render", "ffmpeg_render_failed",
                       {"error": str(e)}, level="WARNING", project_id=manifest.project_id)

        # ── 4b: Generate final_audio_mix.wav (audio-only concat pass) ────────
        try:
            audio_mix_path = out_dir / "final_audio_mix.wav"
            audio_mix_cmd = (
                f'ffmpeg -y -f concat -safe 0 -i "{audio_list_path}" '
                f'-c:a pcm_s16le "{audio_mix_path}"'
            )
            mix_result = subprocess.run(
                audio_mix_cmd, shell=True, capture_output=True, text=True, timeout=300
            )
            if mix_result.returncode != 0 or not audio_mix_path.exists():
                audio_mix_path = None
        except Exception:
            audio_mix_path = None
    elif not _ffmpeg_available():
        log_action(output_folder, "video_render", "ffmpeg_not_available",
                   {"note": "install ffmpeg to render video"},
                   level="WARNING", project_id=manifest.project_id)

    # Video manifest
    video_manifest = {
        "status": "rendered" if rendered else "command_ready",
        "final_video_path": str(output_video_path) if rendered else None,
        "final_audio_mix_path": str(audio_mix_path) if audio_mix_path else None,
        "render_command_path": str(scripts_dir / "ffmpeg_render_command.txt"),
        "timestamps_generated": True,
        "chapters_generated": True,
        "total_duration_seconds": total_duration,
        "track_count": len(tracks),
        "manual_required": not rendered,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / "video_manifest.json").write_text(json.dumps(video_manifest, indent=2), encoding="utf-8")

    manifest.video.status = "rendered" if rendered else "command_ready"
    manifest.video.final_video_path = str(output_video_path) if rendered else None
    manifest.video.final_audio_mix_path = str(audio_mix_path) if audio_mix_path else None
    manifest.video.render_command_path = str(scripts_dir / "ffmpeg_render_command.txt")
    manifest.video.timestamps_generated = True
    manifest.video.chapters_generated = True
    manifest.video.total_duration_seconds = total_duration
    manifest.video.track_count = len(tracks)
    manifest.video.manual_required = not rendered
    manifest.video.updated_at = datetime.now(timezone.utc).isoformat()

    if rendered:
        manifest.update_status(ProjectStatus.VIDEO_RENDERED)
    else:
        manifest.update_status(ProjectStatus.VIDEO_READY)

    save_manifest(manifest, output_folder)
    log_action(output_folder, "video_export", "package_generated",
               {"rendered": rendered, "total_duration": _format_timestamp(total_duration)},
               project_id=manifest.project_id)

    return {**render_config, "rendered": rendered, "ffmpeg_command": ffmpeg_cmd}
