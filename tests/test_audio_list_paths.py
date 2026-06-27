"""
tests/test_audio_list_paths.py
───────────────────────────────
Regression tests for FFmpeg audio concat list path generation.
Verifies:
  - All paths in selected_audio_list.txt are absolute
  - Korean titles with spaces work correctly
  - Single quotes in paths are escaped
  - Works regardless of cwd
"""
from __future__ import annotations

import wave
import shutil
from pathlib import Path
from unittest import mock

import pytest


def _make_wav(path: Path, duration_s: float = 215.0) -> Path:
    n = int(44100 * duration_s)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(44100)
        wf.writeframes(b"\x00" * n * 4)
    return path


def _create_project_with_wavs(tmp_path, monkeypatch, titles):
    import app.config as cfg
    monkeypatch.setattr(cfg, "OUTPUTS_DIR", tmp_path)
    from app.project_manager import create_project, create_track_folder, save_manifest
    from app.state_machine import TrackStatus

    manifest, folder = create_project(
        "Audio List Test", "Test", len(titles), "Manual", "YouTube + Distribution Package"
    )
    songs_root = folder / "01_suno_song_generation"
    for i, title in enumerate(titles):
        t = manifest.tracks[i]
        t.prompt.title = title
        tf = create_track_folder(songs_root, t.track_number, title)
        t.track_folder_path = str(tf)
        wav = tf / "selected" / "suno_master.wav"
        wav.parent.mkdir(parents=True, exist_ok=True)
        _make_wav(wav)
        t.selected_wav_path = str(wav)
        t.is_wav = True
        t.duration_seconds = 215.0
        t.distribution_eligible = True
        t.update_status(TrackStatus.APPROVED)
    save_manifest(manifest, folder)
    return manifest, folder


# ─── Tests ───────────────────────────────────────────────────────────────────

def test_audio_list_contains_absolute_paths(tmp_path, monkeypatch):
    """All paths in selected_audio_list.txt must be absolute."""
    manifest, folder = _create_project_with_wavs(
        tmp_path, monkeypatch, ["잔고 없는 밤", "커플 종강"]
    )
    with mock.patch("workflows.render_video._ffmpeg_available", return_value=False):
        from workflows.render_video import export_video_package
        export_video_package(manifest, folder)

    audio_list = folder / "03_longform_video" / "input" / "selected_audio_list.txt"
    assert audio_list.exists(), "selected_audio_list.txt must be created"

    lines = [l for l in audio_list.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert lines, "audio list must not be empty"

    for line in lines:
        # Extract path from: file '/absolute/path'
        assert line.startswith("file '"), f"Line must start with \"file '\": {line}"
        # Remove file ' prefix and trailing '
        inner = line[6:]
        if inner.endswith("'"):
            inner = inner[:-1]
        # Unescape single quotes: '\'' → '
        inner = inner.replace("'\\''", "'")
        extracted = Path(inner)
        assert extracted.is_absolute(), (
            f"Path in audio list must be absolute, got: {extracted}"
        )


def test_audio_list_paths_with_korean_titles(tmp_path, monkeypatch):
    """Korean titles with spaces must produce valid escaped absolute paths."""
    manifest, folder = _create_project_with_wavs(
        tmp_path, monkeypatch, ["밤이 지나면", "늦은 대답", "여름이 가도"]
    )
    with mock.patch("workflows.render_video._ffmpeg_available", return_value=False):
        from workflows.render_video import export_video_package
        export_video_package(manifest, folder)

    audio_list = folder / "03_longform_video" / "input" / "selected_audio_list.txt"
    lines = [l for l in audio_list.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 3, f"Expected 3 entries, got {len(lines)}"

    for line in lines:
        assert line.startswith("file '"), f"Bad format: {line}"
        # Path must be absolute
        inner = line[6:].rstrip("'").replace("'\\''", "'")
        assert Path(inner).is_absolute()


def test_audio_list_absolute_path_exists(tmp_path, monkeypatch):
    """Each absolute path in the audio list must point to an existing WAV file."""
    manifest, folder = _create_project_with_wavs(
        tmp_path, monkeypatch, ["잔고 없는 밤"]
    )
    with mock.patch("workflows.render_video._ffmpeg_available", return_value=False):
        from workflows.render_video import export_video_package
        export_video_package(manifest, folder)

    audio_list = folder / "03_longform_video" / "input" / "selected_audio_list.txt"
    lines = [l for l in audio_list.read_text(encoding="utf-8").splitlines() if l.strip()]

    for line in lines:
        inner = line[6:].rstrip("'").replace("'\\''", "'")
        p = Path(inner)
        assert p.exists(), f"Audio path in list does not exist: {p}"


def test_audio_list_works_from_different_cwd(tmp_path, monkeypatch, tmp_path_factory):
    """
    Simulate running from a completely different cwd.
    The audio list paths must still resolve to existing files.
    """
    manifest, folder = _create_project_with_wavs(
        tmp_path, monkeypatch, ["밤이 지나면"]
    )
    # Change cwd to an unrelated directory
    other_dir = tmp_path_factory.mktemp("other_cwd")
    original_cwd = Path.cwd()
    import os
    os.chdir(other_dir)
    try:
        with mock.patch("workflows.render_video._ffmpeg_available", return_value=False):
            from workflows.render_video import export_video_package
            # Need fresh import to avoid caching
            import importlib
            import workflows.render_video as rv
            importlib.reload(rv)
            rv.export_video_package(manifest, folder)
    finally:
        os.chdir(original_cwd)

    audio_list = folder / "03_longform_video" / "input" / "selected_audio_list.txt"
    lines = [l for l in audio_list.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert lines, "audio list must not be empty"

    for line in lines:
        inner = line[6:].rstrip("'").replace("'\\''", "'")
        p = Path(inner)
        assert p.is_absolute(), f"Path must be absolute: {p}"
        assert p.exists(), f"Absolute path must exist: {p}"
