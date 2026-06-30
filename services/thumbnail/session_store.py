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
                   volume: int = 1, subtitle: str = "",
                   project_folder: str | None = None) -> dict:
    """Create a new thumbnail session.

    If ``project_folder`` is given (an existing project directory), generated
    thumbnail images are saved INTO that project's ``02_thumbnail_cover/``
    subtree — keeping audio (``01_suno_song_generation/songs/``) and images in
    separate folders under the same project. If omitted, images stay inside the
    standalone studio session (backward compatible).
    """
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
        "project_folder": str(project_folder) if project_folder else None,
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
            "rating": "Keep",
            "notes": "",
            "status": "generated_prompt",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    (sdir / "candidates" / "thumbnail_candidate_metadata.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return candidates


def _resolve_project_image_dir(project_folder: str | None) -> Path | None:
    """Return the project's image dir (``<project>/thumbnails/``), creating it.

    Song-Lab projects live at ``outputs/song_projects/<slug>/`` with audio under
    ``songs/``; thumbnail images go in a sibling ``thumbnails/`` folder so audio
    (mp3) and images (png/jpg) stay in separate folders under the same project.
    """
    if not project_folder:
        return None
    pf = Path(project_folder)
    if not pf.exists():
        return None
    d = pf / "thumbnails"
    d.mkdir(parents=True, exist_ok=True)
    return d


def image_target_dir(session_id: str) -> Path:
    """Where generated image FILES go for this session.

    Bound to a project -> ``<project>/thumbnails/``; otherwise the standalone
    session's ``candidates/images/`` folder. (Candidate METADATA json always
    lives in the session dir so load_candidates works.)
    """
    session = load_session(session_id) or {}
    proj_dir = _resolve_project_image_dir(session.get("project_folder"))
    if proj_dir is not None:
        return proj_dir
    d = _session_dir(session_id) / "candidates" / "images"
    d.mkdir(parents=True, exist_ok=True)
    return d


def generate_images(session_id: str, prompts: list[dict],
                    use_real: bool = False, model: str | None = None) -> list[dict]:
    """Generate ACTUAL images for each prompt and link them to candidates.

    Saves prompt text first (reusing save_prompts), then renders one image per
    prompt via the image provider (mock by default; real Gemini/Nano Banana when
    use_real and an API key + SDK are present). Generated files land in the
    project's image folder when the session is project-bound. The image path is
    stored as ``uploaded_image_path`` so the existing select/brand pipeline works
    unchanged. Returns the updated candidate list.
    """
    from services.thumbnail.image_provider import get_image_provider

    # Base candidates + prompt files.
    save_prompts(session_id, prompts)
    target = image_target_dir(session_id)
    provider = get_image_provider(use_real=use_real, model=model)

    candidates = load_candidates(session_id)
    for i, (c, p) in enumerate(zip(candidates, prompts)):
        cid = c["candidate_id"]
        path_169 = target / f"{cid}_16x9.png"
        path_11 = target / f"{cid}_1x1.png"
        meta = {"scene": p.get("scene", ""), "country": p.get("country", ""),
                "theme": p.get("theme", "")}
        main = p.get("main_prompt", "")
        neg = p.get("negative_prompt", "")

        # 16:9 (primary, used for the YouTube thumbnail + gallery).
        r169 = provider.generate(main, str(path_169), negative_prompt=neg,
                                 index=i, meta=meta, aspect="16:9")
        c["gen_provider"] = r169.get("provider")
        c["gen_model"] = r169.get("model")
        if r169.get("ok"):
            # 1:1 of the SAME scene, generated natively. For real providers we pass
            # the 16:9 as a reference (image-to-image) so the square matches the wide
            # version instead of being a stretched/cropped copy.
            ref = r169["path"] if getattr(provider, "is_real", False) else None
            r11 = provider.generate(main, str(path_11), negative_prompt=neg,
                                    index=i, meta=meta, aspect="1:1", ref_image_path=ref)
            c["image_16x9"] = r169["path"]
            c["image_1x1"] = r11.get("path") if r11.get("ok") else None
            c["uploaded_image_path"] = r169["path"]   # default shown = 16:9
            c["generated_image_path"] = r169["path"]
            c["image_source"] = "generated"
            c["status"] = "image_generated"
            c["gen_error"] = None if r11.get("ok") else f"1:1 failed: {r11.get('error')}"
        else:
            c["image_source"] = "generation_failed"
            c["status"] = "generation_failed"
            c["gen_error"] = r169.get("error")
    save_candidates(session_id, candidates)
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

def inputs_match_session(session: dict, country: str, theme: str,
                         title: str, volume: int, subtitle: str) -> bool:
    """
    Return True if the given inputs match the session's saved inputs.
    Used to decide whether to reuse a session or create a fresh one.
    """
    if not session:
        return False
    return (
        session.get("country") == country
        and session.get("theme") == theme
        and session.get("title") == title
        and session.get("volume") == volume
        and session.get("subtitle") == subtitle
    )
