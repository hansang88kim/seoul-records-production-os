"""
services/thumbnail/session_store.py — Thumbnail Studio session persistence.

Independent from the music package. Stores prompts, uploaded Flow images,
candidate metadata, Canva payloads, and final exports under:
    outputs/thumbnail_studio/<session_id>/
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _studio_root() -> Path:
    d = Path(__file__).resolve().parent.parent.parent / "outputs" / "thumbnail_studio"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _session_dir(session_id: str) -> Path:
    d = _studio_root() / session_id
    for sub in ("prompts", "flow_uploads", "candidates", "canva", "branded", "exports"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    return d


def create_session(country: str, theme: str, title: str,
                   volume: int = 1, subtitle: str = "") -> dict:
    """Create a new thumbnail session."""
    session_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    sdir = _session_dir(session_id)

    manifest = {
        "session_id": session_id,
        "style": "Citypop",
        "country": country,
        "theme": theme,
        "title": title,
        "volume": volume,
        "subtitle": subtitle,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    (sdir / "session_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def load_session(session_id: str) -> dict | None:
    path = _studio_root() / session_id / "session_manifest.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def list_sessions(limit: int = 20) -> list[dict]:
    """List sessions, newest first."""
    sessions = []
    root = _studio_root()
    if not root.exists():
        return []
    for d in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if d.is_dir():
            m = load_session(d.name)
            if m:
                sessions.append(m)
            if len(sessions) >= limit:
                break
    return sessions


def save_prompts(session_id: str, prompts: list[dict]):
    """Save a batch of prompts to disk and to candidate metadata."""
    sdir = _session_dir(session_id)
    for i, p in enumerate(prompts, 1):
        (sdir / "prompts" / f"prompt_{i:03d}.txt").write_text(
            p["main_prompt"], encoding="utf-8"
        )
        (sdir / "prompts" / f"negative_prompt_{i:03d}.txt").write_text(
            p["negative_prompt"], encoding="utf-8"
        )

    # Build / update candidate metadata
    candidates = []
    for i, p in enumerate(prompts, 1):
        candidates.append({
            "candidate_id": f"cand_{i:03d}",
            "prompt_id": f"prompt_{i:03d}",
            "country": p.get("country", ""),
            "theme": p.get("theme", ""),
            "concept": p.get("scene", ""),
            "prompt_path": f"prompts/prompt_{i:03d}.txt",
            "negative_prompt_path": f"prompts/negative_prompt_{i:03d}.txt",
            "title_safe_area": p.get("title_safe_area", ""),
            "color_palette": p.get("color_palette", []),
            "canva_accent_color": p.get("canva_accent_color", ""),
            "uploaded_image_path": None,
            "selected_for_branding": False,
            "rating": None,
            "notes": "",
            "status": "generated_prompt",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    (sdir / "candidates" / "thumbnail_candidate_metadata.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return candidates


def load_candidates(session_id: str) -> list[dict]:
    path = _studio_root() / session_id / "candidates" / "thumbnail_candidate_metadata.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_candidates(session_id: str, candidates: list[dict]):
    sdir = _session_dir(session_id)
    for c in candidates:
        c["updated_at"] = datetime.now(timezone.utc).isoformat()
    (sdir / "candidates" / "thumbnail_candidate_metadata.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def upload_flow_image(session_id: str, candidate_id: str, src_path: str) -> str | None:
    """
    Copy an uploaded Flow image into the session and link it to a candidate.
    Returns the stored image path.
    """
    sdir = _session_dir(session_id)
    src = Path(src_path)
    if not src.exists():
        return None

    dest = sdir / "flow_uploads" / f"{candidate_id}{src.suffix}"
    shutil.copy2(src, dest)

    # Link to candidate
    candidates = load_candidates(session_id)
    for c in candidates:
        if c["candidate_id"] == candidate_id:
            c["uploaded_image_path"] = str(dest)
            c["status"] = "image_uploaded"
            break
    save_candidates(session_id, candidates)
    return str(dest)


def upload_flow_image_bytes(session_id: str, candidate_id: str,
                            data: bytes, suffix: str = ".png") -> str:
    """Save uploaded image bytes (from Streamlit uploader) and link to candidate."""
    sdir = _session_dir(session_id)
    dest = sdir / "flow_uploads" / f"{candidate_id}{suffix}"
    dest.write_bytes(data)

    candidates = load_candidates(session_id)
    for c in candidates:
        if c["candidate_id"] == candidate_id:
            c["uploaded_image_path"] = str(dest)
            c["status"] = "image_uploaded"
            break
    save_candidates(session_id, candidates)
    return str(dest)


def set_candidate_rating(session_id: str, candidate_id: str, rating: str):
    """Rate a candidate: Keep / Maybe / Reject."""
    candidates = load_candidates(session_id)
    for c in candidates:
        if c["candidate_id"] == candidate_id:
            c["rating"] = rating
            if rating == "Reject":
                c["status"] = "rejected"
                c["selected_for_branding"] = False
            break
    save_candidates(session_id, candidates)


def select_for_branding(session_id: str, candidate_id: str, selected: bool = True):
    """Mark a candidate as selected for Canva branding."""
    candidates = load_candidates(session_id)
    for c in candidates:
        if c["candidate_id"] == candidate_id:
            # Only allow selecting if not rejected and has an image
            if selected and c.get("status") == "rejected":
                break
            c["selected_for_branding"] = selected
            if selected:
                c["status"] = "selected_for_branding"
            break
    save_candidates(session_id, candidates)


def get_selected_candidates(session_id: str) -> list[dict]:
    """Get candidates selected for branding (and not rejected, with an image)."""
    return [
        c for c in load_candidates(session_id)
        if c.get("selected_for_branding")
        and c.get("status") != "rejected"
        and c.get("uploaded_image_path")
    ]


def session_path(session_id: str) -> Path:
    return _studio_root() / session_id
