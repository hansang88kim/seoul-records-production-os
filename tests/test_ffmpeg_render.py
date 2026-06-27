"""
tests/test_ffmpeg_render.py
───────────────────────────
FFmpeg render tests — all pass regardless of whether FFmpeg is installed.
Subprocess calls are mocked to avoid environment dependency.
"""
from __future__ import annotations

import json
import wave
from pathlib import Path
from unittest import mock

import pytest


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_wav(path: Path, duration_s: float = 3.5) -> Path:
    n_frames = int(44100 * duration_s)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(b"\x00" * n_frames * 4)
    return path


def _create_test_project_with_wav(tmp_path, monkeypatch):
    """Create a project with one SAVED track that has a real WAV."""
    import app.config as cfg
    monkeypatch.setattr(cfg, "OUTPUTS_DIR", tmp_path)
    from app.project_manager import create_project, create_track_folder
    from app.state_machine import TrackStatus
    import shutil

    manifest, output_folder = create_project(
        project_name="FFmpeg Test",
        theme="Test",
        track_count=1,
        production_mode="Manual",
        output_type="YouTube + Distribution Package",
    )

    track = manifest.tracks[0]
    songs_root = output_folder / "01_suno_song_generation"
    tf = create_track_folder(songs_root, track.track_number, "test-track")
    track.track_folder_path = str(tf)
    track.prompt.title = "Test Track"

    wav_src = _make_wav(tmp_path / "source.wav", duration_s=215.0)
    dst = tf / "selected" / "suno_master.wav"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(wav_src, dst)

    track.selected_wav_path = str(dst)
    track.is_wav = True
    track.duration_seconds = 215.0
    track.distribution_eligible = True
    track.update_status(TrackStatus.SAVED)

    from app.project_manager import save_manifest
    save_manifest(manifest, output_folder)
    return manifest, output_folder


# ─── Tests ───────────────────────────────────────────────────────────────────

def test_ffmpeg_command_generation_works(tmp_path, monkeypatch):
    """build_ffmpeg_command returns a non-empty shell command string."""
    from workflows.render_video import build_ffmpeg_command

    audio_list = tmp_path / "audio_list.txt"
    audio_list.write_text("file '/some/track.wav'\n")
    bg = tmp_path / "bg.jpg"
    bg.write_bytes(b"JFIF")
    out = tmp_path / "final_video.mp4"

    cmd = build_ffmpeg_command(audio_list, bg, out)

    assert "ffmpeg" in cmd
    assert str(audio_list) in cmd
    assert str(out) in cmd
    assert len(cmd) > 20


def test_ffmpeg_missing_does_not_crash(tmp_path, monkeypatch):
    """When FFmpeg is absent, export_video_package returns without crashing."""
    manifest, output_folder = _create_test_project_with_wav(tmp_path, monkeypatch)

    with mock.patch("workflows.render_video._ffmpeg_available", return_value=False):
        from workflows.render_video import export_video_package
        result = export_video_package(manifest, output_folder)

    assert isinstance(result, dict)
    assert result.get("ffmpeg_available") is False
    assert result.get("rendered") is False

    # Command file must still be generated
    cmd_file = output_folder / "03_longform_video" / "render_scripts" / "ffmpeg_render_command.txt"
    assert cmd_file.exists(), "ffmpeg_render_command.txt must be generated even without FFmpeg"


def test_timestamps_and_chapters_generated(tmp_path, monkeypatch):
    """timestamps.txt and youtube_chapters.txt are always generated."""
    manifest, output_folder = _create_test_project_with_wav(tmp_path, monkeypatch)

    with mock.patch("workflows.render_video._ffmpeg_available", return_value=False):
        from workflows.render_video import export_video_package
        export_video_package(manifest, output_folder)

    ts = output_folder / "03_longform_video" / "timestamps" / "timestamps.txt"
    ch = output_folder / "03_longform_video" / "timestamps" / "youtube_chapters.txt"
    assert ts.exists(), "timestamps.txt must be created"
    assert ch.exists(), "youtube_chapters.txt must be created"


def test_final_video_path_appears_in_youtube_package_after_render(tmp_path, monkeypatch):
    """
    When FFmpeg renders successfully, the YouTube package workflow
    must reflect final_video_path in the manifest/video dict.
    """
    manifest, output_folder = _create_test_project_with_wav(tmp_path, monkeypatch)

    # Simulate successful FFmpeg render by writing the output file
    out_file = output_folder / "03_longform_video" / "output" / "final_video.mp4"

    def _fake_subprocess_run(cmd, **kwargs):
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_bytes(b"fake_mp4_data")
        return mock.Mock(returncode=0, stdout="", stderr="")

    with mock.patch("workflows.render_video._ffmpeg_available", return_value=True), \
         mock.patch("subprocess.run", side_effect=_fake_subprocess_run):
        from workflows.render_video import export_video_package
        result = export_video_package(manifest, output_folder)

    assert result.get("rendered") is True, f"Expected rendered=True. Result: {result}"
    assert result.get("output_video") is not None

    # Verify manifest was updated
    import json
    manifest_data = json.loads(
        (output_folder / "project_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest_data["video"]["final_video_path"] is not None, (
        "final_video_path must be set in project_manifest.json after render"
    )
