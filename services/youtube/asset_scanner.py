"""
services/youtube/asset_scanner.py — Scan outputs for YouTube package inputs (v0.8.0).

Finds final_video.mp4 (Video Renderer), youtube_thumbnail_16x9 (Thumbnail
Studio exports), and chapters.txt. Read-only — never modifies existing assets.
"""
from __future__ import annotations

from pathlib import Path


def _outputs_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "outputs"


def _file_size_mb(path: str) -> float:
    try:
        return Path(path).stat().st_size / (1024 * 1024)
    except Exception:
        return 0.0


def _video_duration(path: str) -> float:
    """Best-effort MP4 duration via ffprobe; 0 if unavailable."""
    try:
        import subprocess, json
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", path],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )
        if out.returncode == 0:
            data = json.loads(out.stdout)
            return float(data.get("format", {}).get("duration", 0) or 0)
    except Exception:
        pass
    return 0.0


def scan_final_videos() -> list[dict]:
    """Scan outputs for final_video.mp4 files (Video Renderer + jobs)."""
    root = _outputs_root()
    found: dict[str, dict] = {}
    if not root.exists():
        return []
    for mp4 in root.rglob("final_video.mp4"):
        key = str(mp4.resolve())
        if key in found:
            continue
        found[key] = {
            "path": str(mp4),
            "name": mp4.name,
            "size_mb": round(_file_size_mb(str(mp4)), 2),
            "duration_sec": _video_duration(str(mp4)),
            "parent": mp4.parent.name,
        }
    # Also include preview MP4s as a fallback option
    for mp4 in root.rglob("preview_*.mp4"):
        key = str(mp4.resolve())
        if key in found:
            continue
        found[key] = {
            "path": str(mp4),
            "name": mp4.name,
            "size_mb": round(_file_size_mb(str(mp4)), 2),
            "duration_sec": _video_duration(str(mp4)),
            "parent": mp4.parent.name,
            "is_preview": True,
        }
    return sorted(found.values(), key=lambda x: x["path"])


def scan_youtube_thumbnails() -> list[dict]:
    """Scan Thumbnail Studio exports for youtube_thumbnail_16x9 (png/jpg)."""
    root = _outputs_root()
    found: dict[str, dict] = {}
    if not root.exists():
        return []
    for pattern in ("youtube_thumbnail_16x9.png", "youtube_thumbnail_16x9.jpg",
                    "youtube_thumbnail_16x9.jpeg"):
        for img in root.rglob(pattern):
            key = str(img.resolve())
            if key in found:
                continue
            found[key] = {
                "path": str(img),
                "name": img.name,
                "size_mb": round(_file_size_mb(str(img)), 2),
                "session": img.parent.parent.name if img.parent.name == "exports" else img.parent.name,
            }
    return sorted(found.values(), key=lambda x: x["path"])


def scan_chapters() -> list[dict]:
    """Scan Video Renderer outputs for chapters.txt."""
    root = _outputs_root()
    found: dict[str, dict] = {}
    if not root.exists():
        return []
    for ch in root.rglob("chapters.txt"):
        key = str(ch.resolve())
        if key in found:
            continue
        found[key] = {
            "path": str(ch),
            "name": ch.name,
            "parent": ch.parent.name,
        }
    return sorted(found.values(), key=lambda x: x["path"])


def scan_streaming_covers() -> list[dict]:
    """Scan for optional streaming_cover_1x1 images."""
    root = _outputs_root()
    found: dict[str, dict] = {}
    if not root.exists():
        return []
    for pattern in ("streaming_cover_1x1.png", "streaming_cover_1x1.jpg"):
        for img in root.rglob(pattern):
            key = str(img.resolve())
            if key in found:
                continue
            found[key] = {"path": str(img), "name": img.name}
    return sorted(found.values(), key=lambda x: x["path"])
