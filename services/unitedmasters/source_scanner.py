"""
services/unitedmasters/source_scanner.py — locate Video Renderer + cover sources (v0.9.0).

Finds the latest playlist_plan.json from the Video Renderer and the streaming
cover from the Thumbnail Studio. Read-only.
"""
from __future__ import annotations

import json
from pathlib import Path


def _outputs_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "outputs"


def find_playlist_plans() -> list[dict]:
    """Return [{path, mtime, entries_count}] for every playlist_plan.json found."""
    root = _outputs_root() / "video_renderer"
    out = []
    if not root.exists():
        return out
    for p in root.rglob("playlist_plan.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            out.append({
                "path": str(p),
                "mtime": p.stat().st_mtime,
                "entries_count": len(data.get("entries", [])),
            })
        except Exception:
            pass
    return sorted(out, key=lambda x: x["mtime"], reverse=True)


def latest_playlist_plan() -> dict | None:
    """Load the most recent playlist_plan.json, or None."""
    plans = find_playlist_plans()
    if not plans:
        return None
    try:
        return json.loads(Path(plans[0]["path"]).read_text(encoding="utf-8"))
    except Exception:
        return None


def find_streaming_covers() -> list[str]:
    """All streaming_cover_1x1 images under thumbnail_studio."""
    root = _outputs_root() / "thumbnail_studio"
    if not root.exists():
        return []
    found = []
    for ext in ("png", "jpg", "jpeg"):
        found += [str(p) for p in root.rglob(f"streaming_cover_1x1.{ext}")]
    return found


def find_chapters() -> list[str]:
    root = _outputs_root() / "video_renderer"
    if not root.exists():
        return []
    return [str(p) for p in root.rglob("chapters.txt")]
