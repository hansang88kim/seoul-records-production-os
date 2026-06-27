"""
Seoul Records Production OS — Project Manager
Handles creation, persistence, and resumption of projects.
"""
from __future__ import annotations
import json
import uuid
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.models import (
    ProjectManifest, TrackManifest, TrackPrompt,
    VisualManifest, VideoManifest, YouTubeManifest, DistributionManifest,
    LogEntry
)
from app.state_machine import ProjectStatus, TrackStatus
from app.config import OUTPUTS_DIR


# ─── Folder Layout ────────────────────────────────────────────────────────────

STEP_FOLDERS = [
    "01_suno_song_generation",
    "02_thumbnail_cover",
    "03_longform_video",
    "04_youtube_upload",
    "05_music_distribution",
    "export_package",
]

SONG_SUBFOLDERS = ["songs", "songs/.gitkeep"]
THUMBNAIL_SUBFOLDERS = [
    "flow_prompts", "source_images", "canva", "final"
]
VIDEO_SUBFOLDERS = ["input", "timestamps", "render_scripts", "output"]
YOUTUBE_SUBFOLDERS = ["metadata", "assets", "upload_result"]
DIST_SUBFOLDERS = [
    "unitedmasters/audio", "unitedmasters/cover",
    "unitedmasters/metadata", "unitedmasters/rights",
    "unitedmasters/upload_logs", "other_distributors"
]


def _slugify(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s_]+", "-", name)
    return name[:60]


def build_output_folder_name(project_name: str, language_pack: str) -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = _slugify(project_name)
    return f"{date_str}_{slug}_{language_pack}"


def create_project_folders(output_folder: Path) -> None:
    """Create the full step-folder tree for a new project."""
    output_folder.mkdir(parents=True, exist_ok=True)

    # Step 1: Song Generation
    songs_root = output_folder / "01_suno_song_generation"
    songs_root.mkdir(exist_ok=True)
    (songs_root / "songs").mkdir(exist_ok=True)

    # Step 2: Thumbnail
    thumb_root = output_folder / "02_thumbnail_cover"
    for sub in THUMBNAIL_SUBFOLDERS:
        (thumb_root / sub).mkdir(parents=True, exist_ok=True)

    # Step 3: Video
    video_root = output_folder / "03_longform_video"
    for sub in VIDEO_SUBFOLDERS:
        (video_root / sub).mkdir(parents=True, exist_ok=True)

    # Step 4: YouTube
    yt_root = output_folder / "04_youtube_upload"
    for sub in YOUTUBE_SUBFOLDERS:
        (yt_root / sub).mkdir(parents=True, exist_ok=True)

    # Step 5: Distribution
    dist_root = output_folder / "05_music_distribution"
    for sub in DIST_SUBFOLDERS:
        (dist_root / sub).mkdir(parents=True, exist_ok=True)

    # Export package
    (output_folder / "export_package").mkdir(exist_ok=True)


def create_track_folder(songs_root: Path, track_number: int, title: str) -> Path:
    """Create folder structure for a single track."""
    safe_title = _slugify(title) or f"track-{track_number:02d}"
    folder_name = f"{track_number:02d}_{safe_title}"
    track_folder = songs_root / "songs" / folder_name
    track_folder.mkdir(parents=True, exist_ok=True)
    (track_folder / "candidates").mkdir(exist_ok=True)
    (track_folder / "selected").mkdir(exist_ok=True)
    return track_folder


# ─── Manifest I/O ─────────────────────────────────────────────────────────────

def save_manifest(manifest: ProjectManifest, output_folder: Path) -> None:
    path = output_folder / "project_manifest.json"
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")


def load_manifest(output_folder: Path) -> ProjectManifest:
    path = output_folder / "project_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return ProjectManifest.model_validate(data)


def append_log(entry: LogEntry, output_folder: Path) -> None:
    log_path = output_folder / "project_log.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(entry.model_dump_json() + "\n")


def log_action(
    output_folder: Path,
    step: str,
    action: str,
    details: dict | None = None,
    level: str = "INFO",
    track_id: str | None = None,
    project_id: str | None = None,
) -> None:
    entry = LogEntry(
        level=level,
        step=step,
        action=action,
        details=details or {},
        track_id=track_id,
        project_id=project_id,
    )
    append_log(entry, output_folder)


# ─── Project Creation ─────────────────────────────────────────────────────────

def create_project(
    project_name: str,
    theme: str,
    track_count: int,
    production_mode: str,
    output_type: str,
    language_pack: str = "ko_kr_seoul",
    core_style: str = "Seoul Records City Pop Core",
) -> tuple[ProjectManifest, Path]:
    """
    Create a new project: folders, manifest, initial log entry.
    Returns (manifest, output_folder_path).
    """
    project_id = str(uuid.uuid4())
    folder_name = build_output_folder_name(project_name, language_pack)
    output_folder = OUTPUTS_DIR / folder_name

    create_project_folders(output_folder)

    # Initialise empty track manifests
    tracks = []
    for i in range(1, track_count + 1):
        track = TrackManifest(
            track_number=i,
            track_id=str(uuid.uuid4()),
            status=TrackStatus.DRAFT_CREATED,
            prompt=TrackPrompt(),
        )
        tracks.append(track)

    manifest = ProjectManifest(
        project_id=project_id,
        project_name=project_name,
        core_style=core_style,
        language_pack=language_pack,
        theme=theme,
        track_count=track_count,
        production_mode=production_mode,
        output_type=output_type,
        output_folder=str(output_folder),
        status=ProjectStatus.PROJECT_CREATED,
        tracks=tracks,
    )

    save_manifest(manifest, output_folder)
    log_action(
        output_folder,
        step="project_creation",
        action="project_created",
        details={
            "project_name": project_name,
            "folder": folder_name,
            "track_count": track_count,
            "production_mode": production_mode,
        },
        project_id=project_id,
    )

    return manifest, output_folder


# ─── Project Discovery ────────────────────────────────────────────────────────

def list_projects() -> list[dict]:
    """Return metadata for all projects found in outputs/."""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    projects = []
    for folder in sorted(OUTPUTS_DIR.iterdir(), reverse=True):
        manifest_path = folder / "project_manifest.json"
        if manifest_path.exists():
            try:
                m = load_manifest(folder)
                projects.append({
                    "folder_name": folder.name,
                    "project_name": m.project_name,
                    "status": m.status,
                    "track_count": m.track_count,
                    "created_at": m.created_at,
                    "output_folder": str(folder),
                })
            except Exception:
                pass
    return projects


def resume_project(output_folder: Path) -> ProjectManifest:
    """Load an existing project manifest for resumption."""
    manifest = load_manifest(output_folder)
    log_action(
        output_folder,
        step="project_management",
        action="project_resumed",
        details={"status": manifest.status},
        project_id=manifest.project_id,
    )
    return manifest
