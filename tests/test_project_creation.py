"""Tests for project creation and folder structure."""
import json
import pytest
from pathlib import Path
import tempfile
import shutil


def test_slugify():
    from app.project_manager import _slugify
    assert _slugify("Seoul Night Vol. 1!") == "seoul-night-vol-1"
    assert _slugify("  HELLO WORLD  ") == "hello-world"


def test_build_output_folder_name():
    from app.project_manager import build_output_folder_name
    name = build_output_folder_name("Seoul Night", "ko_kr_seoul")
    assert "ko_kr_seoul" in name
    assert "seoul-night" in name


def test_project_folders_created(tmp_path, monkeypatch):
    import app.config as cfg
    monkeypatch.setattr(cfg, "OUTPUTS_DIR", tmp_path)
    from app.project_manager import create_project
    manifest, output_folder = create_project(
        project_name="Test Project",
        theme="Late Night Drive",
        track_count=1,
        production_mode="Manual",
        output_type="YouTube + Distribution Package",
    )
    assert output_folder.exists()
    for step in ["01_suno_song_generation", "02_thumbnail_cover", "03_longform_video",
                  "04_youtube_upload", "05_music_distribution", "export_package"]:
        assert (output_folder / step).exists(), f"Missing: {step}"
    assert (output_folder / "project_manifest.json").exists()
    assert (output_folder / "project_log.jsonl").exists()


def test_manifest_serialization(tmp_path, monkeypatch):
    import app.config as cfg
    monkeypatch.setattr(cfg, "OUTPUTS_DIR", tmp_path)
    from app.project_manager import create_project, load_manifest
    manifest, output_folder = create_project(
        project_name="Serialization Test",
        theme="",
        track_count=2,
        production_mode="Auto",
        output_type="Full Album Mix Mode",
    )
    loaded = load_manifest(output_folder)
    assert loaded.project_name == "Serialization Test"
    assert loaded.track_count == 2
    assert len(loaded.tracks) == 2


def test_tracks_initialized(tmp_path, monkeypatch):
    import app.config as cfg
    monkeypatch.setattr(cfg, "OUTPUTS_DIR", tmp_path)
    from app.project_manager import create_project
    manifest, _ = create_project(
        project_name="Track Init Test",
        theme="",
        track_count=5,
        production_mode="Manual",
        output_type="1 Hour Playlist Mode",
    )
    assert len(manifest.tracks) == 5
    for i, t in enumerate(manifest.tracks, 1):
        assert t.track_number == i
