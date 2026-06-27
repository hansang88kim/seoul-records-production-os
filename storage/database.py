"""
storage/database.py — lightweight project index for discovering and listing projects.

v0.1: Uses the filesystem as the database (outputs/ directory scan).
Future: Can be replaced with SQLite or PostgreSQL without changing the interface.
"""

from __future__ import annotations
import os
import json
from typing import Optional


def list_all_projects(outputs_root: str = "outputs") -> list[dict]:
    """
    Scan the outputs directory and return a list of project summary dicts.

    Each dict contains: project_dir, project_name, status, created_at, track_count.
    """
    projects = []
    if not os.path.isdir(outputs_root):
        return projects

    for entry in sorted(os.listdir(outputs_root)):
        proj_dir = os.path.join(outputs_root, entry)
        manifest_path = os.path.join(proj_dir, "project_manifest.json")
        if not os.path.isfile(manifest_path):
            continue
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
            projects.append(
                {
                    "project_dir": proj_dir,
                    "project_name": manifest.get("project_name", entry),
                    "status": manifest.get("status", "unknown"),
                    "created_at": manifest.get("created_at", ""),
                    "track_count": manifest.get("track_count", 0),
                    "language_pack": manifest.get("language_pack", ""),
                    "theme": manifest.get("theme", ""),
                }
            )
        except (json.JSONDecodeError, OSError):
            continue

    return projects


def get_project(project_dir: str) -> Optional[dict]:
    """
    Load a single project manifest by directory path.

    Returns the manifest dict, or None if not found.
    """
    manifest_path = os.path.join(project_dir, "project_manifest.json")
    if not os.path.isfile(manifest_path):
        return None
    try:
        with open(manifest_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def find_project_by_name(name: str, outputs_root: str = "outputs") -> Optional[dict]:
    """Find the first project matching a given name."""
    for p in list_all_projects(outputs_root):
        if p["project_name"] == name:
            return p
    return None


def get_recent_projects(n: int = 5, outputs_root: str = "outputs") -> list[dict]:
    """Return the n most recently modified projects."""
    projects = list_all_projects(outputs_root)
    projects.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    return projects[:n]
