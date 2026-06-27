"""
Tests for distribution package: MP3 blocking, WAV pass-through,
cover art copy (Fix 5), and package contents (v0.1.1).
"""
import shutil
import pytest
from pathlib import Path


def test_distribution_blocked_for_mp3_only(tmp_path, monkeypatch):
    import app.config as cfg
    monkeypatch.setattr(cfg, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(cfg, "ALLOW_MP3_FOR_DISTRIBUTION", False)

    from app.project_manager import create_project
    from app.state_machine import TrackStatus
    from workflows.export_distribution_package import export_distribution_package

    manifest, output_folder = create_project(
        project_name="MP3 Block Test", theme="", track_count=1,
        production_mode="Manual", output_type="YouTube + Distribution Package",
    )
    track = manifest.tracks[0]
    track.status = TrackStatus.SAVED
    track.is_wav = False
    fake_mp3 = tmp_path / "fake.mp3"
    fake_mp3.write_bytes(b"ID3FAKE")
    track.selected_wav_path = str(fake_mp3)

    from app.project_manager import save_manifest
    save_manifest(manifest, output_folder)

    zip_path, warnings = export_distribution_package(manifest, output_folder)
    assert zip_path is None
    assert manifest.distribution.blocked_reason is not None


def test_distribution_succeeds_for_wav(tmp_path, monkeypatch):
    import app.config as cfg
    monkeypatch.setattr(cfg, "OUTPUTS_DIR", tmp_path)

    from app.project_manager import create_project
    from app.state_machine import TrackStatus
    from workflows.export_distribution_package import export_distribution_package
    from providers.suno.mock_suno import _generate_sine_wav

    manifest, output_folder = create_project(
        project_name="WAV OK Test", theme="", track_count=1,
        production_mode="Manual", output_type="YouTube + Distribution Package",
    )
    track = manifest.tracks[0]
    track.prompt.title = "Test Track"
    track.status = TrackStatus.SAVED
    track.is_wav = True
    wav_path = tmp_path / "test_master.wav"
    _generate_sine_wav(wav_path, duration_seconds=3.0)  # tiny WAV
    track.selected_wav_path = str(wav_path)
    track.distribution_eligible = True

    from app.project_manager import save_manifest
    save_manifest(manifest, output_folder)

    zip_path, warnings = export_distribution_package(manifest, output_folder)
    assert zip_path is not None
    assert zip_path.exists()


def test_distribution_package_includes_cover_art(tmp_path, monkeypatch):
    """Fix 5: DSP cover from tab 2 must be copied into unitedmasters/cover/ and included in ZIP."""
    import app.config as cfg
    monkeypatch.setattr(cfg, "OUTPUTS_DIR", tmp_path)

    from app.project_manager import create_project
    from app.state_machine import TrackStatus
    from workflows.export_distribution_package import export_distribution_package
    from providers.suno.mock_suno import _generate_sine_wav
    import zipfile

    manifest, output_folder = create_project(
        project_name="Cover Art Test", theme="", track_count=1,
        production_mode="Manual", output_type="YouTube + Distribution Package",
    )
    track = manifest.tracks[0]
    track.prompt.title = "Cover Track"
    track.status = TrackStatus.SAVED
    track.is_wav = True
    wav_path = tmp_path / "cover_master.wav"
    _generate_sine_wav(wav_path, duration_seconds=3.0)  # tiny WAV
    track.selected_wav_path = str(wav_path)
    track.distribution_eligible = True

    # Simulate Tab 2 generating a cover
    cover_dir = output_folder / "02_thumbnail_cover" / "final"
    cover_dir.mkdir(parents=True, exist_ok=True)
    cover_file = cover_dir / "dsp_cover_3000x3000.png"
    cover_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)  # minimal PNG-like

    from app.project_manager import save_manifest
    save_manifest(manifest, output_folder)

    zip_path, warnings = export_distribution_package(manifest, output_folder)
    assert zip_path is not None

    # cover_ready must be True
    assert manifest.distribution.cover_ready is True

    # Cover file must exist in unitedmasters/cover/
    cover_dest_dir = output_folder / "05_music_distribution" / "unitedmasters" / "cover"
    assert any(cover_dest_dir.iterdir()), "cover/ dir must not be empty"

    # Cover must be included in ZIP
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    cover_in_zip = [n for n in names if "cover" in n and n.endswith((".png", ".jpg"))]
    assert cover_in_zip, f"Cover art not found in ZIP. Contents: {names[:20]}"


def test_cover_ready_flag_set(tmp_path, monkeypatch):
    """Fix 5: manifest.distribution.cover_ready=True when cover is present."""
    import app.config as cfg
    monkeypatch.setattr(cfg, "OUTPUTS_DIR", tmp_path)

    from app.project_manager import create_project
    from app.state_machine import TrackStatus
    from workflows.export_distribution_package import export_distribution_package
    from providers.suno.mock_suno import _generate_sine_wav

    manifest, output_folder = create_project(
        project_name="Flag Test", theme="", track_count=1,
        production_mode="Manual", output_type="YouTube + Distribution Package",
    )
    track = manifest.tracks[0]
    track.prompt.title = "Flag Track"
    track.status = TrackStatus.SAVED
    track.is_wav = True
    wav_path = tmp_path / "flag_master.wav"
    _generate_sine_wav(wav_path, duration_seconds=3.0)  # tiny WAV
    track.selected_wav_path = str(wav_path)
    track.distribution_eligible = True

    cover_dir = output_folder / "02_thumbnail_cover" / "final"
    cover_dir.mkdir(parents=True, exist_ok=True)
    (cover_dir / "dsp_cover_3000x3000.png").write_bytes(b"\x89PNG" + b"\x00" * 32)

    from app.project_manager import save_manifest
    save_manifest(manifest, output_folder)

    zip_path, _ = export_distribution_package(manifest, output_folder)
    assert zip_path is not None
    assert manifest.distribution.cover_ready is True
