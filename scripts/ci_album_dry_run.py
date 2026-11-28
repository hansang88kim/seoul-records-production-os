"""Exercise album generation with local mock audio only."""
from __future__ import annotations

import os
from pathlib import Path

from agents.producer_agent import generate_song_prompt
from app.project_manager import create_project
from app.state_machine import TrackStatus
from workflows.generate_album import run_song_generation, update_song_list_csv


def main() -> int:
    track_count = int(os.environ.get("DRY_RUN_TRACK_COUNT", "3"))
    language_pack = os.environ.get("DRY_RUN_PRESET", "ko_kr_seoul")
    theme = os.environ.get("DRY_RUN_THEME", "Late Night Drive")
    if track_count not in {1, 3, 5, 10, 15, 20} or language_pack != "ko_kr_seoul":
        raise ValueError("Unsupported mock album configuration")

    manifest, output_folder = create_project(
        project_name=f"DryRun-{track_count}t",
        theme=theme,
        track_count=track_count,
        production_mode="Auto",
        output_type="YouTube + Distribution Package",
        language_pack=language_pack,
    )
    print(f"Mock album output: {output_folder}")

    saved_tracks = 0
    for track in manifest.tracks:
        result = generate_song_prompt(track.track_number, theme, language_pack)
        track.prompt.title = result["title"]
        track.prompt.style = result["style"]
        track.prompt.lyrics = result["lyrics"]
        track.prompt.exclude_styles = result["exclude_styles"]
        track.prompt.vocal_gender = "Female"
        updated = run_song_generation(manifest, output_folder, track, provider_name="mock")
        saved = (
            updated.status == TrackStatus.SAVED
            and updated.is_wav
            and bool(updated.selected_wav_path)
            and Path(updated.selected_wav_path).is_file()
        )
        saved_tracks += int(saved)
        print(f"Track {track.track_number}: {'saved WAV' if saved else updated.status}")

    update_song_list_csv(manifest, output_folder)
    print(f"Saved {saved_tracks}/{track_count} mock WAVs and wrote song_list.csv.")
    return 0 if saved_tracks == track_count else 1


if __name__ == "__main__":
    raise SystemExit(main())
