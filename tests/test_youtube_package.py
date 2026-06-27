"""
Tests for YouTube export package (v0.1.1).
Fix 6: thumbnail included, final_video_path.txt instead of MP4.
Fix 7: chapters start at 00:00 with first track, no "Intro".
"""
import zipfile
import pytest
from pathlib import Path


def _make_project_with_tracks(tmp_path, monkeypatch, n=2):
    """Helper: create project with n saved WAV tracks."""
    import app.config as cfg
    monkeypatch.setattr(cfg, "OUTPUTS_DIR", tmp_path)

    from app.project_manager import create_project
    from app.state_machine import TrackStatus
    from providers.suno.mock_suno import _generate_sine_wav

    manifest, output_folder = create_project(
        project_name="YT Test", theme="", track_count=n,
        production_mode="Manual", output_type="YouTube + Distribution Package",
    )
    for i, track in enumerate(manifest.tracks):
        track.prompt.title = f"서울의 밤 No.{i + 1}"
        track.status = TrackStatus.SAVED
        track.is_wav = True
        wav_path = tmp_path / f"track{i}.wav"
        _generate_sine_wav(wav_path, duration_seconds=3.0)  # tiny WAV
        track.selected_wav_path = str(wav_path)
        track.duration_seconds = 215.0 + i * 5
        track.distribution_eligible = True

    from app.project_manager import save_manifest
    save_manifest(manifest, output_folder)
    return manifest, output_folder


def test_youtube_chapters_start_with_first_track_no_intro(tmp_path, monkeypatch):
    """Fix 7: First chapter must be '00:00 01. Track Title', NOT '00:00 Intro'."""
    manifest, output_folder = _make_project_with_tracks(tmp_path, monkeypatch)
    from workflows.export_youtube_package import export_youtube_package

    zip_path = export_youtube_package(manifest, output_folder)
    chapters_path = output_folder / "04_youtube_upload" / "metadata" / "youtube_chapters.txt"
    assert chapters_path.exists()

    chapters = chapters_path.read_text(encoding="utf-8")
    lines = [l.strip() for l in chapters.strip().split("\n") if l.strip()]

    assert lines, "Chapters file must not be empty"
    assert lines[0].startswith("00:00"), f"First chapter must start at 00:00, got: {lines[0]}"
    assert "Intro" not in lines[0], (
        f"First chapter must NOT contain 'Intro', got: {lines[0]}"
    )
    assert "01." in lines[0], f"First chapter must contain track 01, got: {lines[0]}"


def test_youtube_package_includes_thumbnail(tmp_path, monkeypatch):
    """Fix 6: YouTube package ZIP must include the thumbnail image."""
    manifest, output_folder = _make_project_with_tracks(tmp_path, monkeypatch)

    # Simulate Tab 2 generating a thumbnail
    thumb_dir = output_folder / "02_thumbnail_cover" / "final"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_file = thumb_dir / "youtube_thumbnail_16x9.png"
    thumb_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    manifest.visual.youtube_thumbnail_path = str(thumb_file)
    manifest.visual.youtube_thumbnail_16x9 = True

    from app.project_manager import save_manifest
    save_manifest(manifest, output_folder)

    from workflows.export_youtube_package import export_youtube_package
    zip_path = export_youtube_package(manifest, output_folder)

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()

    thumbnail_in_zip = [n for n in names if "thumbnail" in n.lower() and n.endswith(".png")]
    assert thumbnail_in_zip, f"Thumbnail not in ZIP. Contents: {names}"


def test_youtube_package_no_mp4_in_zip(tmp_path, monkeypatch):
    """Fix 6: MP4 must NOT be bundled in the ZIP by default."""
    manifest, output_folder = _make_project_with_tracks(tmp_path, monkeypatch)

    # Simulate a rendered video
    video_dir = output_folder / "03_longform_video" / "output"
    video_dir.mkdir(parents=True, exist_ok=True)
    fake_video = video_dir / "final_video.mp4"
    fake_video.write_bytes(b"FAKEMP4" * 1000)

    from app.project_manager import save_manifest
    save_manifest(manifest, output_folder)

    from workflows.export_youtube_package import export_youtube_package
    zip_path = export_youtube_package(manifest, output_folder)

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()

    mp4_in_zip = [n for n in names if n.endswith(".mp4")]
    assert not mp4_in_zip, f"MP4 must NOT be in ZIP by default. Found: {mp4_in_zip}"


def test_youtube_package_includes_video_path_txt(tmp_path, monkeypatch):
    """Fix 6: final_video_path.txt must be in ZIP when video exists."""
    manifest, output_folder = _make_project_with_tracks(tmp_path, monkeypatch)

    video_dir = output_folder / "03_longform_video" / "output"
    video_dir.mkdir(parents=True, exist_ok=True)
    fake_video = video_dir / "final_video.mp4"
    fake_video.write_bytes(b"FAKEMP4")

    from app.project_manager import save_manifest
    save_manifest(manifest, output_folder)

    from workflows.export_youtube_package import export_youtube_package
    zip_path = export_youtube_package(manifest, output_folder)

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()

    path_txt_in_zip = [n for n in names if "final_video_path" in n]
    assert path_txt_in_zip, f"final_video_path.txt not in ZIP. Contents: {names}"
