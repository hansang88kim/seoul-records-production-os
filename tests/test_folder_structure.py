"""Tests for project folder structure correctness."""
import pytest
from pathlib import Path


def test_all_step_folders_exist(tmp_path, monkeypatch):
    import app.config as cfg
    monkeypatch.setattr(cfg, "OUTPUTS_DIR", tmp_path)
    from app.project_manager import create_project

    manifest, output_folder = create_project(
        project_name="Folder Test", theme="", track_count=1,
        production_mode="Manual", output_type="YouTube + Distribution Package",
    )

    expected_folders = [
        "01_suno_song_generation",
        "01_suno_song_generation/songs",
        "02_thumbnail_cover/flow_prompts",
        "02_thumbnail_cover/source_images",
        "02_thumbnail_cover/canva",
        "02_thumbnail_cover/final",
        "03_longform_video/input",
        "03_longform_video/timestamps",
        "03_longform_video/render_scripts",
        "03_longform_video/output",
        "04_youtube_upload/metadata",
        "04_youtube_upload/assets",
        "04_youtube_upload/upload_result",
        "05_music_distribution/unitedmasters/audio",
        "05_music_distribution/unitedmasters/cover",
        "05_music_distribution/unitedmasters/metadata",
        "05_music_distribution/unitedmasters/rights",
        "export_package",
    ]
    for folder in expected_folders:
        assert (output_folder / folder).exists(), f"Missing: {folder}"


def test_manifest_and_log_exist(tmp_path, monkeypatch):
    import app.config as cfg
    monkeypatch.setattr(cfg, "OUTPUTS_DIR", tmp_path)
    from app.project_manager import create_project

    manifest, output_folder = create_project(
        project_name="Log Test", theme="", track_count=1,
        production_mode="Manual", output_type="YouTube + Distribution Package",
    )
    assert (output_folder / "project_manifest.json").exists()
    assert (output_folder / "project_log.jsonl").exists()
