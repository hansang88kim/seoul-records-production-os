"""
create_project.py — workflow entry point for new project creation.

Called from the dashboard when the user submits the project creation form.
Creates the full folder tree, initializes project_manifest.json and project_log.jsonl.
"""

from __future__ import annotations
import sys
import os

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.orchestrator import (
    create_project,
    append_log,
    load_manifest,
)


def run(
    project_name: str,
    language_pack: str = "ko_kr_seoul",
    theme: str = "late_night_drive",
    track_count: int = 5,
    production_mode: str = "manual",
    output_type: str = "youtube_distribution_package",
    outputs_root: str = "outputs",
) -> dict:
    """
    Create a new project and return the resulting manifest.

    Args:
        project_name: User-supplied project name.
        language_pack: Language/market pack ID.
        theme: Theme preset name.
        track_count: Number of tracks to produce.
        production_mode: 'manual' or 'auto'.
        output_type: '1h_playlist', 'full_album_mix', or 'youtube_distribution_package'.
        outputs_root: Root directory for all projects.

    Returns:
        project_manifest dict.
    """
    manifest = create_project(
        project_name=project_name,
        language_pack=language_pack,
        theme=theme,
        track_count=track_count,
        production_mode=production_mode,
        output_type=output_type,
        outputs_root=outputs_root,
    )

    append_log(
        manifest["project_dir"],
        event="workflow.create_project",
        status="completed",
        message=f"Project '{project_name}' created with {track_count} tracks.",
    )

    return manifest


if __name__ == "__main__":
    import json

    result = run(
        project_name="테스트 앨범",
        language_pack="ko_kr_seoul",
        theme="late_night_drive",
        track_count=5,
        production_mode="manual",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
