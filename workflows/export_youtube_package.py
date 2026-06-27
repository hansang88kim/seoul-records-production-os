"""
Seoul Records Production OS — YouTube Export Package (v0.1.1)

Fix 6: Include youtube_thumbnail_16x9 image in zip.
       Add final_video_path.txt if video exists (don't zip huge MP4 by default).
Fix 7: YouTube chapters start at 00:00 with first track — no "Intro" prefix.
Fix 8: CSV via csv module (tags written as proper CSV).
Fix 9: timezone-aware datetime.
"""
from __future__ import annotations

import csv
import io
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from app.models import ProjectManifest
from app.project_manager import save_manifest, log_action
from app.state_machine import ProjectStatus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fmt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"


def generate_youtube_metadata(
    manifest: ProjectManifest,
    output_folder: Path,
) -> dict:
    """Generate YouTube title, description, tags, and hashtags."""
    project_name = manifest.project_name
    tracks = manifest.approved_tracks()
    track_count = len(tracks)

    title = f"{project_name} — City Pop Seoul Mix ({track_count} tracks)"

    # ── Fix 7: chapters start at 00:00 with first track, NO "Intro" line ──────
    description_lines = [
        title,
        "",
        "🌙 Seoul Records City Pop — Nostalgic Japanese-influenced urban pop",
        "🎵 1990s city sound • Female vocal • Night city mood",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "TRACKLIST",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    current_seconds = 0.0
    for t in tracks:
        ts = _fmt_ts(current_seconds)
        description_lines.append(f"{ts} {t.track_number:02d}. {t.prompt.title}")
        current_seconds += (t.duration_seconds or 210.0)

    description_lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "Seoul Records — AI-assisted music production",
        f"Generated with Seoul Records Production OS v{manifest.app_version}",
        "",
        "#CityPop #SeoulRecords #シティポップ #서울레코드",
    ]

    description = "\n".join(description_lines)

    tags = [
        "city pop", "city pop 2024", "japanese city pop", "citypop",
        "korean city pop", "night drive music", "lo-fi city pop",
        "chill music", "urban pop", "80s city pop", "90s pop",
        "female vocal", "korean music", "seoul records",
        manifest.project_name,
    ]

    hashtags = [
        "#CityPop", "#SeoulRecords", "#シティポップ",
        "#서울", "#NightDrive", "#ChillMusic",
    ]

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "hashtags": hashtags,
    }


def _generate_chapters(manifest: ProjectManifest) -> str:
    """
    Fix 7: YouTube chapters start at 00:00 with the first track title.
    No extra "Intro" line prepended.
    """
    tracks = manifest.approved_tracks()
    lines = []
    current = 0.0
    for t in tracks:
        ts = _fmt_ts(current)
        lines.append(f"{ts} {t.track_number:02d}. {t.prompt.title}")
        current += (t.duration_seconds or 210.0)
    return "\n".join(lines)


def export_youtube_package(
    manifest: ProjectManifest,
    output_folder: Path,
) -> Path:
    """
    Export all YouTube upload assets.

    Fix 6: copies thumbnail into zip; adds final_video_path.txt instead of
           bundling the large MP4.
    Fix 7: chapters start at 00:00 with first track, no "Intro".
    Fix 8: tags written with csv module.
    Fix 9: timezone-aware datetime.

    Returns path to ZIP.
    """
    yt_root   = output_folder / "04_youtube_upload"
    meta_dir  = yt_root / "metadata"
    assets_dir = yt_root / "assets"
    meta_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    meta = generate_youtube_metadata(manifest, output_folder)
    chapters = _generate_chapters(manifest)

    manifest.youtube.title = meta["title"]
    manifest.youtube.description = meta["description"]
    manifest.youtube.tags = meta["tags"]
    manifest.youtube.hashtags = meta["hashtags"]

    # ── Text metadata files ───────────────────────────────────────────────────
    (meta_dir / "youtube_title.txt").write_text(meta["title"], encoding="utf-8")
    (meta_dir / "youtube_description.txt").write_text(meta["description"], encoding="utf-8")
    (meta_dir / "youtube_chapters.txt").write_text(chapters, encoding="utf-8")

    # Fix 8: tags as proper CSV (one tag per line for readability, or single-row CSV)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["tag"])
    for tag in meta["tags"]:
        writer.writerow([tag])
    (meta_dir / "youtube_tags.csv").write_text(buf.getvalue(), encoding="utf-8")
    # Also plain text for copy-paste into YouTube UI
    (meta_dir / "youtube_tags.txt").write_text(
        ", ".join(meta["tags"]), encoding="utf-8"
    )
    (meta_dir / "youtube_hashtags.txt").write_text(
        " ".join(meta["hashtags"]), encoding="utf-8"
    )

    upload_config = {
        "title": meta["title"],
        "description": meta["description"],
        "tags": meta["tags"],
        "privacy": "private",
        "category": "Music",
        "language": manifest.language_pack,
        "project_id": manifest.project_id,
        "generated_at": _now(),
    }
    (meta_dir / "upload_config.json").write_text(
        json.dumps(upload_config, indent=2), encoding="utf-8"
    )

    # ── Fix 6: Copy thumbnail into assets/ ───────────────────────────────────
    thumb_src = output_folder / "02_thumbnail_cover" / "final" / "youtube_thumbnail_16x9.png"
    thumb_jpg  = output_folder / "02_thumbnail_cover" / "final" / "youtube_thumbnail_16x9.jpg"
    thumb_dest = None
    for candidate in [thumb_src, thumb_jpg]:
        if candidate.exists():
            dest = assets_dir / candidate.name
            shutil.copy2(candidate, dest)
            thumb_dest = dest
            break

    if thumb_dest is None:
        (assets_dir / "THUMBNAIL_MISSING.txt").write_text(
            "Generate thumbnail in Tab 2 before uploading.", encoding="utf-8"
        )

    # ── Fix 6: final_video_path.txt instead of bundling MP4 ─────────────────
    video_path = output_folder / "03_longform_video" / "output" / "final_video.mp4"
    if video_path.exists():
        (assets_dir / "final_video_path.txt").write_text(
            str(video_path.resolve()), encoding="utf-8"
        )
    else:
        (assets_dir / "VIDEO_NOT_RENDERED.txt").write_text(
            "Run video render in Tab 3 before uploading.", encoding="utf-8"
        )

    # ── ZIP package (no MP4 unless explicitly requested) ─────────────────────
    zip_path = output_folder / "export_package" / "youtube_upload_package.zip"
    zip_path.parent.mkdir(exist_ok=True)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in meta_dir.iterdir():
            if file.is_file():
                zf.write(file, Path("metadata") / file.name)
        for file in assets_dir.iterdir():
            # Never bundle MP4 in zip by default
            if file.is_file() and file.suffix.lower() != ".mp4":
                zf.write(file, Path("assets") / file.name)

    manifest.youtube.status = "package_ready"
    manifest.youtube.package_path = str(zip_path)
    manifest.youtube.updated_at = _now()
    manifest.update_status(ProjectStatus.YOUTUBE_METADATA_READY)
    save_manifest(manifest, output_folder)

    log_action(
        output_folder, "youtube_export", "package_exported",
        {"zip_path": str(zip_path), "title": meta["title"],
         "thumbnail_included": thumb_dest is not None,
         "video_path_included": video_path.exists()},
        project_id=manifest.project_id,
    )

    return zip_path
