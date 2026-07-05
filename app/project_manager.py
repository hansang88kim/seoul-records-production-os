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


# ─── Lightweight Song-Project Layer (for Song Lab) ───────────────────────────
# Simple project folders + JSON manifest for grouping generated songs.
# Independent of the heavy ProjectManifest schema above.

def _song_projects_root() -> Path:
    d = OUTPUTS_DIR / "song_projects"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _song_slug(name: str) -> str:
    """Slug that preserves Korean characters for readable folder names."""
    if not name or not name.strip():
        return "default"
    s = name.strip()
    s = re.sub(r'[/\\:*?"<>|]', "_", s)
    s = re.sub(r"\s+", "-", s)
    return s[:60] or "default"


def song_project_dir(project_name: str) -> Path:
    """Get (and create) a song-project folder with a songs/ subfolder."""
    d = _song_projects_root() / _song_slug(project_name)
    (d / "songs").mkdir(parents=True, exist_ok=True)
    return d


def _song_manifest_path(project_name: str) -> Path:
    return song_project_dir(project_name) / "manifest.json"


def load_song_manifest(project_name: str) -> dict:
    p = _song_manifest_path(project_name)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "name": project_name,
        "slug": _song_slug(project_name),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "songs": [],
    }


def save_song_manifest(project_name: str, manifest: dict) -> None:
    p = _song_manifest_path(project_name)
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    p.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def list_song_projects() -> list[dict]:
    """List all song projects with counts, newest first."""
    out = []
    root = _song_projects_root()
    for d in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        name, songs = d.name, []
        mp = d / "manifest.json"
        if mp.exists():
            try:
                data = json.loads(mp.read_text(encoding="utf-8"))
                name = data.get("name", d.name)
                songs = data.get("songs", [])
            except Exception:
                pass
        out.append({"name": name, "slug": d.name, "song_count": len(songs), "path": str(d)})
    return out


def song_project_download_dir(project_name: str, title: str) -> Path:
    """
    Download dir for songs — the project's songs/ folder DIRECTLY.
    All songs in a project download as mp3 files into this one folder
    (no per-song subfolders), so they group together for upload.
    """
    pdir = song_project_dir(project_name)
    d = pdir / "songs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def add_song_to_project(project_name: str, song: dict) -> dict:
    """Record a song in the project manifest (file already in project folder)."""
    song = dict(song)
    song["project"] = project_name
    song["project_slug"] = _song_slug(project_name)
    manifest = load_song_manifest(project_name)
    manifest["songs"].insert(0, song)
    save_song_manifest(project_name, manifest)
    return song


def get_song_project_songs(project_name: str) -> list[dict]:
    return load_song_manifest(project_name).get("songs", [])


def find_song_file(project_name: str, song: dict) -> str:
    """
    Resolve a song's playable audio file (v1.0.0-alpha.48).

    1. song["file_path"] when it exists on disk.
    2. Else scan the project's songs/ folder for an mp3/wav whose cleaned
       filename stem starts with the song title (Suno downloads are named
       '{title}-{id}.mp3', so submitted-then-manually-downloaded songs
       resolve too). Returns "" when nothing matches.
    """
    fp = song.get("file_path") or ""
    if fp and Path(fp).exists():
        return fp

    title = (song.get("title") or "").strip()
    if not title or not project_name:
        return ""
    try:
        from services.library_labels import clean_track_stem
    except Exception:
        clean_track_stem = lambda s: s  # noqa: E731

    songs_dir = _song_projects_root() / _song_slug(project_name) / "songs"
    if not songs_dir.exists():
        return ""
    for f in sorted(songs_dir.iterdir()):
        if f.suffix.lower() not in (".mp3", ".wav"):
            continue
        stem = clean_track_stem(f.stem)
        if stem == title or f.stem.startswith(title):
            return str(f)
    return ""


def update_song_in_project(project_name: str, song: dict, patch: dict) -> bool:
    """
    Merge `patch` into one manifest song entry (matched by title +
    created_at when available, else first title match). v1.0.0-alpha.50.
    """
    manifest = load_song_manifest(project_name)
    songs = manifest.get("songs", [])
    target_title = (song.get("title") or "").strip()
    target_created = song.get("created_at", "")
    for s in songs:
        if (s.get("title") or "").strip() != target_title:
            continue
        if target_created and s.get("created_at") != target_created:
            continue
        s.update(patch)
        save_song_manifest(project_name, manifest)
        return True
    return False


def remove_song_from_project(project_name: str, song: dict,
                             delete_file: bool = True) -> bool:
    """
    Remove one song from a project's manifest (and optionally its audio
    file on disk). Matches by title + created_at when available, else by
    title alone (first match). Returns True when an entry was removed.
    """
    manifest = load_song_manifest(project_name)
    songs = manifest.get("songs", [])
    target_title = (song.get("title") or "").strip()
    target_created = song.get("created_at", "")

    idx = None
    for i, s in enumerate(songs):
        if (s.get("title") or "").strip() != target_title:
            continue
        if target_created and s.get("created_at") != target_created:
            continue
        idx = i
        break
    if idx is None:
        return False

    removed = songs.pop(idx)
    save_song_manifest(project_name, manifest)

    if delete_file:
        fp = removed.get("file_path") or find_song_file(project_name, removed)
        if fp:
            try:
                Path(fp).unlink(missing_ok=True)
            except Exception:
                pass
    return True


def copy_song_to_project(target_project: str, song: dict) -> dict | None:
    """
    Copy a Library song into another project (v1.0.0-alpha.43).

    The audio file (when it exists on disk) is copied into the target
    project's songs/ folder and a manifest entry is added, so the song shows
    up in 프로젝트 관리 / Library / Video Renderer under the target project
    with the SAME title. Returns the new manifest entry, or None when the
    copy was skipped (no source file, or an identically-named file is
    already in the target project).
    """
    src = song.get("file_path") or ""
    src_path = Path(src) if src else None
    dest_dir = song_project_dir(target_project) / "songs"
    dest_dir.mkdir(parents=True, exist_ok=True)

    new_song = dict(song)
    new_song["imported_from_project"] = song.get("project", "")

    if src_path and src_path.exists():
        dest = dest_dir / src_path.name
        # Skip duplicates: same file already recorded in the target manifest
        existing = load_song_manifest(target_project).get("songs", [])
        for e in existing:
            efp = e.get("file_path") or ""
            if efp and Path(efp).name == dest.name:
                return None
        if src_path.resolve() != dest.resolve():
            shutil.copy2(src_path, dest)
        new_song["file_path"] = str(dest)
    elif not src_path:
        # Metadata-only song (e.g. submitted-on-Suno, not downloaded yet):
        # still record it so the target project lists the title.
        titles = {
            (e.get("title") or "").strip()
            for e in load_song_manifest(target_project).get("songs", [])
        }
        if (new_song.get("title") or "").strip() in titles:
            return None
    else:
        return None  # file_path set but missing on disk

    return add_song_to_project(target_project, new_song)


def delete_song_project(project_name: str) -> bool:
    pdir = _song_projects_root() / _song_slug(project_name)
    if pdir.exists():
        try:
            shutil.rmtree(pdir)
            return True
        except Exception:
            return False
    return False
