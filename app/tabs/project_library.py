"""
Seoul Records Production OS — Project Library (v0.2.0)

Renders inside the landing page (project_screen) as an "Open Existing Project"
panel. Also provides a compact sidebar summary when a project is open.
NOT a production tab — the 5-tab production console is preserved.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app.config import OUTPUTS_DIR
from app.state_machine import ProjectStatus


# ─── Step status mapping ──────────────────────────────────────────────────────

_STEP_STATUSES = {
    "Song Generation": [
        ProjectStatus.SONG_GENERATION_READY,
        ProjectStatus.SONG_GENERATION_IN_PROGRESS,
        ProjectStatus.SONG_GENERATION_COMPLETED,
        ProjectStatus.THUMBNAIL_READY,
        ProjectStatus.THUMBNAIL_COMPLETED,
        ProjectStatus.VIDEO_READY,
        ProjectStatus.VIDEO_RENDERED,
        ProjectStatus.YOUTUBE_METADATA_READY,
        ProjectStatus.YOUTUBE_UPLOADED_PRIVATE,
        ProjectStatus.DISTRIBUTION_PACKAGE_READY,
        ProjectStatus.DISTRIBUTION_UPLOAD_ASSISTED,
        ProjectStatus.COMPLETED,
    ],
    "Thumbnail": [
        ProjectStatus.THUMBNAIL_READY,
        ProjectStatus.THUMBNAIL_COMPLETED,
        ProjectStatus.VIDEO_READY,
        ProjectStatus.VIDEO_RENDERED,
        ProjectStatus.YOUTUBE_METADATA_READY,
        ProjectStatus.YOUTUBE_UPLOADED_PRIVATE,
        ProjectStatus.DISTRIBUTION_PACKAGE_READY,
        ProjectStatus.DISTRIBUTION_UPLOAD_ASSISTED,
        ProjectStatus.COMPLETED,
    ],
    "Video": [
        ProjectStatus.VIDEO_RENDERED,
        ProjectStatus.YOUTUBE_METADATA_READY,
        ProjectStatus.YOUTUBE_UPLOADED_PRIVATE,
        ProjectStatus.DISTRIBUTION_PACKAGE_READY,
        ProjectStatus.DISTRIBUTION_UPLOAD_ASSISTED,
        ProjectStatus.COMPLETED,
    ],
    "YouTube": [
        ProjectStatus.YOUTUBE_UPLOADED_PRIVATE,
        ProjectStatus.DISTRIBUTION_PACKAGE_READY,
        ProjectStatus.DISTRIBUTION_UPLOAD_ASSISTED,
        ProjectStatus.COMPLETED,
    ],
    "Distribution": [
        ProjectStatus.DISTRIBUTION_PACKAGE_READY,
        ProjectStatus.DISTRIBUTION_UPLOAD_ASSISTED,
        ProjectStatus.COMPLETED,
    ],
}


def get_step_statuses(project_status: str) -> dict[str, str]:
    """
    Return a dict mapping each step name to "done" | "in_progress" | "pending".
    """
    try:
        status_enum = ProjectStatus(project_status)
    except ValueError:
        return {k: "pending" for k in _STEP_STATUSES}

    result = {}
    for step, done_statuses in _STEP_STATUSES.items():
        if status_enum in done_statuses:
            result[step] = "done"
        elif step == "Song Generation" and status_enum in (
            ProjectStatus.SONG_GENERATION_IN_PROGRESS,
        ):
            result[step] = "in_progress"
        else:
            result[step] = "pending"
    return result


# ─── Scan outputs/ for existing projects ─────────────────────────────────────

def list_projects_library(outputs_dir: Optional[Path] = None) -> list[dict]:
    """
    Scan outputs/ for project_manifest.json files.
    Returns list of summary dicts, sorted newest-first.
    """
    base = outputs_dir or OUTPUTS_DIR
    projects = []
    for manifest_path in sorted(base.glob("*/project_manifest.json"), reverse=True):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            steps = get_step_statuses(data.get("status", ""))
            completed_tracks = sum(
                1 for t in data.get("tracks", [])
                if t.get("status") in ("saved", "approved")
            )
            total_tracks = data.get("track_count", 0)
            projects.append({
                "project_name": data.get("project_name", "Unknown"),
                "project_id": data.get("project_id", ""),
                "status": data.get("status", "unknown"),
                "app_version": data.get("app_version", "?"),
                "track_count": total_tracks,
                "completed_tracks": completed_tracks,
                "language_pack": data.get("language_pack", ""),
                "production_mode": data.get("production_mode", "Manual"),
                "output_type": data.get("output_type", ""),
                "folder_name": manifest_path.parent.name,
                "output_folder": str(manifest_path.parent),
                "manifest_path": str(manifest_path),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
                "step_statuses": steps,
            })
        except Exception:
            continue
    return projects


# ─── Streamlit UI helper ──────────────────────────────────────────────────────

def render_project_library_panel():
    """
    Render the Project Library panel inside the landing page.
    Shows a list of existing projects with 5-step status and Resume button.
    """
    import streamlit as st
    from app.project_manager import resume_project

    st.markdown("#### 📚 Open Existing Project")

    projects = list_projects_library()

    if not projects:
        st.info("No existing projects found in `outputs/`")
        return

    _STEP_ICONS = {
        "done": "✅",
        "in_progress": "🔵",
        "pending": "⬜",
    }
    _STEP_LABELS = ["Song Gen", "Thumbnail", "Video", "YouTube", "Distribution"]
    _STEP_KEYS = ["Song Generation", "Thumbnail", "Video", "YouTube", "Distribution"]

    # Sort selector
    col_sort, _ = st.columns([2, 3])
    with col_sort:
        sort_by = st.selectbox(
            "Sort by",
            ["Newest first", "Oldest first", "Name"],
            label_visibility="collapsed",
            key="library_sort",
        )

    if sort_by == "Oldest first":
        projects = list(reversed(projects))
    elif sort_by == "Name":
        projects = sorted(projects, key=lambda p: p["project_name"].lower())

    for proj in projects[:20]:
        steps = proj["step_statuses"]
        step_str = " ".join(
            f"{_STEP_ICONS.get(steps.get(k, 'pending'), '⬜')}{lbl}"
            for k, lbl in zip(_STEP_KEYS, _STEP_LABELS)
        )
        track_info = f"{proj['completed_tracks']}/{proj['track_count']} tracks"
        updated = proj["updated_at"][:10] if proj["updated_at"] else "?"

        with st.expander(
            f"**{proj['project_name']}**  ·  {track_info}  ·  {updated}",
            expanded=False,
        ):
            st.caption(f"📁 `{proj['folder_name']}`")
            st.caption(f"Status: `{proj['status']}`  ·  v{proj['app_version']}")
            st.markdown(f"<small>{step_str}</small>", unsafe_allow_html=True)

            col_open, col_info = st.columns([2, 3])
            with col_open:
                if st.button(
                    "▶ Resume",
                    key=f"lib_resume_{proj['project_id'] or proj['folder_name']}",
                    type="primary",
                    use_container_width=True,
                ):
                    output_folder = Path(proj["output_folder"])
                    manifest = resume_project(output_folder)
                    st.session_state.current_project = manifest
                    st.session_state.current_output_folder = str(output_folder)
                    st.rerun()
            with col_info:
                st.caption(f"Mode: {proj['production_mode']}  ·  {proj['language_pack']}")
