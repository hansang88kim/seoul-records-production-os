"""
tests/test_project_library.py
──────────────────────────────
Project Library tests — verify that existing projects are listed correctly
and step statuses are computed from ProjectStatus enum.
No Streamlit dependency.
"""
from __future__ import annotations

import json
import wave
import shutil
from pathlib import Path

import pytest


def _write_minimal_manifest(folder: Path, project_name: str = "Test", status: str = "project_created", track_count: int = 2, completed: int = 0) -> None:
    """Write a minimal project_manifest.json directly — no create_project dependency."""
    import uuid
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    tracks = []
    for i in range(track_count):
        s = "saved" if i < completed else "draft_created"
        tracks.append({
            "track_number": i + 1,
            "track_id": str(uuid.uuid4()),
            "status": s,
            "prompt": {"title": f"Track {i+1}", "style": "", "lyrics": "", "exclude_styles": [], "vocal_gender": "Female", "weirdness": 30, "style_influence": 70, "instrumental": False, "model": "v5.5", "title_locked": False, "style_locked": False, "lyrics_locked": False},
        })
    data = {
        "project_id": str(uuid.uuid4()),
        "project_name": project_name,
        "core_style": "Seoul Records City Pop Core",
        "language_pack": "ko_kr_seoul",
        "theme": "",
        "track_count": track_count,
        "production_mode": "Manual",
        "output_type": "YouTube + Distribution Package",
        "output_folder": str(folder),
        "status": status,
        "app_version": "0.2.0",
        "tracks": tracks,
        "created_at": now,
        "updated_at": now,
    }
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "project_manifest.json").write_text(json.dumps(data, indent=2))


# ─── Tests ───────────────────────────────────────────────────────────────────

def test_project_library_lists_existing_projects(tmp_path):
    """list_projects_library returns an entry for each project manifest found."""
    _write_minimal_manifest(tmp_path / "proj_a", "Seoul Night Vol 1", track_count=5)
    _write_minimal_manifest(tmp_path / "proj_b", "Seoul Night Vol 2", track_count=3)

    from app.tabs.project_library import list_projects_library
    projects = list_projects_library(outputs_dir=tmp_path)

    assert len(projects) == 2, f"Expected 2 projects, got {len(projects)}"
    names = {p["project_name"] for p in projects}
    assert "Seoul Night Vol 1" in names
    assert "Seoul Night Vol 2" in names


def test_project_library_step_statuses_for_new_project(tmp_path):
    """A brand new project has all steps as 'pending'."""
    _write_minimal_manifest(tmp_path / "proj_new", "New Project", status="project_created")

    from app.tabs.project_library import list_projects_library
    projects = list_projects_library(outputs_dir=tmp_path)
    assert len(projects) == 1, f"Expected 1 project, got {len(projects)}"

    steps = projects[0]["step_statuses"]
    assert isinstance(steps, dict)
    assert steps.get("Distribution") == "pending", (
        f"New project Distribution step should be pending, got: {steps}"
    )


def test_project_library_shows_completed_tracks(tmp_path):
    """completed_tracks count reflects SAVED/APPROVED tracks in manifest."""
    _write_minimal_manifest(tmp_path / "proj_tracks", "Track Count Test", track_count=3, completed=2)

    from app.tabs.project_library import list_projects_library
    projects = list_projects_library(outputs_dir=tmp_path)
    assert len(projects) == 1
    assert projects[0]["completed_tracks"] == 2
    assert projects[0]["track_count"] == 3


def test_project_library_returns_empty_for_empty_outputs(tmp_path):
    """Empty outputs directory returns an empty list."""
    from app.tabs.project_library import list_projects_library
    projects = list_projects_library(outputs_dir=tmp_path)
    assert projects == []


def test_project_library_path_is_correct(tmp_path):
    """output_folder in library entry points to the actual project directory."""
    proj_dir = tmp_path / "my_project"
    _write_minimal_manifest(proj_dir, "Path Test")

    from app.tabs.project_library import list_projects_library
    projects = list_projects_library(outputs_dir=tmp_path)
    assert len(projects) == 1, f"Expected 1 project, got {len(projects)}"

    folder = Path(projects[0]["output_folder"])
    assert folder.exists(), f"output_folder {folder} does not exist"
    assert (folder / "project_manifest.json").exists()


def test_project_library_distribution_done_status(tmp_path):
    """A completed project shows Distribution step as 'done'."""
    _write_minimal_manifest(tmp_path / "proj_done", "Done Project", status="completed", track_count=5, completed=5)

    from app.tabs.project_library import list_projects_library
    projects = list_projects_library(outputs_dir=tmp_path)
    assert len(projects) == 1

    steps = projects[0]["step_statuses"]
    assert steps.get("Distribution") == "done", (
        f"Completed project Distribution step should be 'done', got: {steps}"
    )
    assert steps.get("Song Generation") == "done"
