"""
services/video/playlist_builder.py — MP3-first playlist builder (v0.7.1).

Scans outputs/ for MP3 files (NO WAV required), lets the user assemble a
playlist, and builds a plan that plays each track exactly once, in order.
The total length is simply the sum of the tracks. Produces chapters + a
concat plan for FFmpeg.
"""
from __future__ import annotations

import json
from pathlib import Path


def _outputs_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "outputs"


def _mp3_duration(path: str) -> float:
    """Get MP3 duration in seconds (mutagen, with graceful fallback)."""
    try:
        import mutagen.mp3
        return float(mutagen.mp3.MP3(path).info.length or 0.0)
    except Exception:
        # Fallback: rough estimate from file size (128kbps assumption)
        try:
            size = Path(path).stat().st_size
            return size / (128 * 1024 / 8)
        except Exception:
            return 0.0


def scan_mp3_files(extra_dirs: list[str] | None = None) -> list[dict]:
    """
    Scan outputs/ (and optional extra dirs) for MP3 files.
    Returns [{path, name, duration_sec, source}] sorted by name.
    Recognizes selected_preview.mp3 and suno_cli download folders.
    """
    roots = [_outputs_root()]
    if extra_dirs:
        roots += [Path(d) for d in extra_dirs]

    found: dict[str, dict] = {}
    for root in roots:
        if not root.exists():
            continue
        for mp3 in root.rglob("*.mp3"):
            key = str(mp3.resolve())
            if key in found:
                continue
            # Tag the source for clarity (filename takes priority)
            parts = mp3.parts
            if mp3.name == "selected_preview.mp3":
                source = "selected_preview"
            elif "song_projects" in parts:
                source = "song_project"
            elif "jobs" in parts:
                source = "job_download"
            else:
                source = "other"
            found[key] = {
                "path": str(mp3),
                "name": mp3.name,
                "duration_sec": _mp3_duration(str(mp3)),
                "source": source,
            }

    return sorted(found.values(), key=lambda x: x["name"])


def build_playlist_plan(tracks: list[dict]) -> dict:
    """
    Build a playlist plan from the given tracks — each track plays ONCE, in order.

    v1.0.0-alpha.121: the old "repeat until target minutes" behaviour is gone.
    The playlist length is simply the sum of the uploaded tracks' durations.

    tracks: [{path, name, duration_sec}] in the desired order.

    Returns:
      {
        "entries": [{path, name, duration_sec, start_sec, end_sec}],
        "total_seconds": float,
        "chapters": [{title, start_sec, end_sec}],
      }
    """
    base = [t for t in tracks if t.get("path") and t.get("duration_sec", 0) > 0]

    entries: list[dict] = []
    chapters: list[dict] = []
    cursor = 0.0

    for track in base:
        dur = track["duration_sec"]
        start = cursor
        end = cursor + dur

        entries.append({
            "path": track["path"],
            "name": track["name"],
            "duration_sec": dur,
            "start_sec": round(start, 2),
            "end_sec": round(end, 2),
        })
        chapters.append({
            "title": track["name"],
            "start_sec": round(start, 2),
            "end_sec": round(end, 2),
        })
        cursor = end

    return {
        "entries": entries,
        "total_seconds": round(cursor, 2),
        "chapters": chapters,
    }


def format_chapters_txt(plan: dict) -> str:
    """Format a YouTube-style chapters.txt (timestamp + title)."""
    lines = []
    for ch in plan.get("chapters", []):
        s = int(ch["start_sec"])
        h, m, sec = s // 3600, (s % 3600) // 60, s % 60
        ts = f"{h:02d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"
        lines.append(f"{ts} {ch['title']}")
    return "\n".join(lines)


def save_playlist_plan(out_dir: str, plan: dict) -> str:
    """Save playlist_plan.json."""
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "playlist_plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
