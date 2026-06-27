"""
Seoul Records Production OS — Orchestrator
High-level pipeline runner (used by Auto Mode and GitHub Actions dry-run).
"""
from __future__ import annotations
from pathlib import Path
from app.models import ProjectManifest
from app.project_manager import save_manifest, log_action
from app.state_machine import ProjectStatus, TrackStatus
from agents.producer_agent import generate_song_prompt
from workflows.generate_album import run_song_generation, update_song_list_csv


def run_full_pipeline(
    manifest: ProjectManifest,
    output_folder: Path,
    provider_name: str = "mock",
    auto_interval_seconds: int = 0,
) -> ProjectManifest:
    """
    Run the complete song generation pipeline for all tracks.
    In Auto Mode, respects the auto_interval_seconds delay between jobs.
    """
    import time

    manifest.update_status(ProjectStatus.SONG_GENERATION_IN_PROGRESS)
    save_manifest(manifest, output_folder)

    for i, track in enumerate(manifest.tracks):
        if track.status in (TrackStatus.SAVED, TrackStatus.APPROVED):
            continue

        if i > 0 and auto_interval_seconds > 0:
            time.sleep(auto_interval_seconds)

        # Auto-generate prompt if empty
        if not track.prompt.title:
            result = generate_song_prompt(
                track_number=track.track_number,
                theme=manifest.theme,
                language_pack=manifest.language_pack,
            )
            track.prompt.title = result["title"]
            track.prompt.style = result["style"]
            track.prompt.lyrics = result["lyrics"]
            track.prompt.exclude_styles = result["exclude_styles"]
            track.prompt.vocal_gender = "Female"

        updated = run_song_generation(manifest, output_folder, track, provider_name=provider_name)
        manifest.tracks[i] = updated
        update_song_list_csv(manifest, output_folder)
        save_manifest(manifest, output_folder)

        log_action(
            output_folder,
            step="orchestrator",
            action="track_complete",
            details={"track": updated.track_number, "status": updated.status},
            project_id=manifest.project_id,
        )

    # Check if all done
    if all(t.status in (TrackStatus.SAVED, TrackStatus.APPROVED, TrackStatus.FAILED)
           for t in manifest.tracks):
        manifest.update_status(ProjectStatus.SONG_GENERATION_COMPLETED)
        save_manifest(manifest, output_folder)

    return manifest
