"""
services/library_labels.py — Shared Library naming (v1.0.0-alpha.43).

Single source of truth for how songs and thumbnail sessions are NAMED and
DESCRIBED across the app. The sidebar Library pages, the Video Renderer's
MP3/thumbnail-session pickers, and Song Lab's project import picker all call
these helpers, so an item shows the IDENTICAL name + meta description
everywhere it appears.

Design rules:
  * Song entry   →  "{project} · {title} ({m:ss})"      (no project → title only)
  * Image session →  "{title-or-theme} ({generated}/{total}장 생성됨) · {country} · {session_id}"
"""
from __future__ import annotations

import re
from pathlib import Path


# ─── Duration formatting ─────────────────────────────────────────────────────

def format_duration(seconds) -> str:
    """Seconds → 'm:ss' (or '—' when unknown)."""
    try:
        s = int(float(seconds))
    except (TypeError, ValueError):
        return "—"
    if s <= 0:
        return "—"
    return f"{s // 60}:{s % 60:02d}"


# ─── Song library index ──────────────────────────────────────────────────────

_HEX_SUFFIX = re.compile(r"-[0-9a-f]{6,}$", re.IGNORECASE)


def clean_track_stem(stem: str) -> str:
    """
    Strip trailing '-<hex-id>' download suffixes from an MP3 filename stem,
    e.g. '늦은 대답-8df69261a2' → '늦은 대답'. Applied repeatedly because Suno
    downloads may stack more than one id token.
    """
    prev = None
    while prev != stem:
        prev = stem
        stem = _HEX_SUFFIX.sub("", stem)
    return stem.strip() or prev


def build_song_library_index() -> dict:
    """
    Map resolved audio file path → {"project": name, "title": title}
    from every song-project manifest (the same data the sidebar
    Library's 곡 라이브러리 renders).
    """
    from app.project_manager import list_song_projects, get_song_project_songs

    index: dict[str, dict] = {}
    slug_to_name: dict[str, str] = {}
    titles_by_project: dict[str, list[str]] = {}

    for p in list_song_projects():
        slug_to_name[p.get("slug", "")] = p["name"]
        titles = []
        for s in get_song_project_songs(p["name"]):
            title = (s.get("title") or "").strip()
            if title:
                titles.append(title)
            fp = s.get("file_path") or ""
            if fp:
                try:
                    index[str(Path(fp).resolve())] = {
                        "project": p["name"], "title": title or Path(fp).stem,
                    }
                except Exception:
                    continue
        titles_by_project[p["name"]] = titles

    index["__slug_to_name__"] = slug_to_name          # type: ignore[assignment]
    index["__titles_by_project__"] = titles_by_project  # type: ignore[assignment]
    return index


def _project_from_path(path: str, slug_to_name: dict) -> str:
    """Infer the owning song project from a path under song_projects/<slug>/."""
    try:
        parts = Path(path).parts
    except Exception:
        return ""
    for i, part in enumerate(parts):
        if part == "song_projects" and i + 1 < len(parts):
            slug = parts[i + 1]
            return slug_to_name.get(slug, slug)
    return ""


def song_track_label(track: dict) -> str:
    """Library-identical label for one playlist track."""
    dur = format_duration(track.get("duration_sec"))
    title = track.get("title") or track.get("name") or "?"
    project = track.get("project") or ""
    if project:
        return f"{project} · {title} ({dur})"
    return f"{title} ({dur})"


def song_entry_label(project_name: str, song: dict) -> str:
    """Library-identical label for a manifest song entry (Song Lab picker)."""
    dur = format_duration(song.get("duration"))
    title = (song.get("title") or "제목 없음").strip()
    if project_name:
        return f"{project_name} · {title} ({dur})"
    return f"{title} ({dur})"


def enrich_tracks_with_song_library(tracks: list[dict]) -> list[dict]:
    """
    Attach Library-consistent metadata to scanned MP3 tracks:
      project        — owning song project name ('' when standalone)
      title          — manifest title when known, else cleaned filename stem
      library_label  — the exact label the Library / pickers display
    Original dicts are not mutated.
    """
    idx = build_song_library_index()
    slug_to_name = idx.pop("__slug_to_name__", {})       # type: ignore[arg-type]
    titles_by_project = idx.pop("__titles_by_project__", {})  # type: ignore[arg-type]

    out = []
    for t in tracks:
        t = dict(t)
        try:
            key = str(Path(t.get("path", "")).resolve())
        except Exception:
            key = t.get("path", "")
        meta = idx.get(key)
        if meta:
            t["project"] = meta["project"]
            t["title"] = meta["title"]
        else:
            project = _project_from_path(t.get("path", ""), slug_to_name)
            stem = clean_track_stem(Path(t.get("name", t.get("path", ""))).stem)
            # Prefer the manifest title when the filename starts with it
            # (Suno downloads are named '{title}-{id}.mp3').
            title = stem
            for cand in titles_by_project.get(project, []):
                if cand and stem.startswith(cand):
                    title = cand
                    break
            t["project"] = project
            t["title"] = title
        t["library_label"] = song_track_label(t)
        out.append(t)
    return out


def group_track_indices_by_project(tracks: list[dict]) -> dict[str, list[int]]:
    """{project name → [track indices]} for project-folder bulk selection."""
    groups: dict[str, list[int]] = {}
    for i, t in enumerate(tracks):
        proj = t.get("project") or ""
        if proj:
            groups.setdefault(proj, []).append(i)
    return groups


# ─── Image (thumbnail) library ───────────────────────────────────────────────

def thumbnail_session_library_label(sess: dict,
                                    generated: int | None = None,
                                    total: int | None = None) -> str:
    """
    Library-identical label for a thumbnail session. When counts are not
    supplied they are read from the session's candidate metadata.
    """
    sid = sess.get("session_id", "")
    title = sess.get("title") or sess.get("theme") or sid
    country = sess.get("country", "")
    if generated is None or total is None:
        try:
            from services.thumbnail.session_store import load_candidates
            cands = load_candidates(sid)
            total = len(cands)
            generated = sum(1 for c in cands if c.get("uploaded_image_path"))
        except Exception:
            generated, total = 0, 0
    label = f"{title} ({generated}/{total}장 생성됨)"
    if country:
        label += f" · {country}"
    return f"{label} · {sid}"


def list_image_library_sessions(limit: int = 30) -> list[dict]:
    """
    Sessions enriched with generated/candidate counts + library_label —
    the exact list the sidebar Library's 이미지 라이브러리 shows.
    """
    from services.thumbnail.session_store import list_sessions, load_candidates

    out = []
    for sess in list_sessions(limit=limit):
        sid = sess.get("session_id", "")
        try:
            cands = load_candidates(sid)
        except Exception:
            cands = []
        generated = sum(1 for c in cands if c.get("uploaded_image_path"))
        sess = dict(sess)
        sess["candidate_count"] = len(cands)
        sess["generated_count"] = generated
        sess["library_label"] = thumbnail_session_library_label(
            sess, generated=generated, total=len(cands)
        )
        out.append(sess)
    return out
