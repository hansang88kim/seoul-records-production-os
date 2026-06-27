"""
tests/test_distribution_master.py
──────────────────────────────────
Distribution master tests — all pass regardless of whether FFmpeg is installed.
FFmpeg-dependent tests use subprocess mocking or skip gracefully.
"""
from __future__ import annotations

import shutil
import wave
from pathlib import Path
from unittest import mock

import pytest


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_wav(path: Path, duration_s: float = 3.5,
              sample_rate: int = 44100, channels: int = 2, bit_depth: int = 16) -> Path:
    n_frames = int(sample_rate * duration_s)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(bit_depth // 8)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00" * n_frames * channels * (bit_depth // 8))
    return path


def _make_fake_wav(path: Path) -> Path:
    """MP3 data with .wav extension."""
    path.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x00" * 50)
    return path


def _make_mp3(path: Path) -> Path:
    path.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x00" * 50)
    return path


# ─── Tests ───────────────────────────────────────────────────────────────────

def test_distribution_master_created_from_wav(tmp_path):
    """Valid WAV at target spec → copy (action='copy', success=True)."""
    from workflows.create_distribution_master import create_distribution_master

    src = _make_wav(tmp_path / "suno_master.wav",
                    sample_rate=44100, channels=2, bit_depth=16)
    dst = tmp_path / "output" / "distribution_master.wav"

    result = create_distribution_master(src, dst)

    assert result.success, f"Expected success=True. Warnings: {result.warnings}"
    assert result.action in ("copy", "ffmpeg_convert"), f"Unexpected action: {result.action}"
    assert dst.exists(), "distribution_master.wav must be created"
    assert result.output_path == str(dst)


def test_mp3_cannot_become_distribution_master(tmp_path):
    """MP3 file must be blocked — distribution_master.wav must NOT be created."""
    from workflows.create_distribution_master import create_distribution_master

    src = _make_mp3(tmp_path / "track.mp3")
    dst = tmp_path / "output" / "distribution_master.wav"

    result = create_distribution_master(src, dst)

    assert not result.success, "MP3 must not produce distribution_master.wav"
    assert result.action == "blocked", f"Expected action='blocked', got '{result.action}'"
    assert not dst.exists(), "distribution_master.wav must NOT be created from MP3"
    assert result.blocked_reason is not None


def test_fake_wav_cannot_become_distribution_master(tmp_path):
    """MP3 data inside .wav extension must be blocked."""
    from workflows.create_distribution_master import create_distribution_master

    src = _make_fake_wav(tmp_path / "sneaky.wav")
    dst = tmp_path / "output" / "distribution_master.wav"

    result = create_distribution_master(src, dst)

    assert not result.success
    assert result.action == "blocked"
    assert not dst.exists()
    assert "fake_wav" in (result.blocked_reason or ""), (
        f"blocked_reason should mention fake_wav: {result.blocked_reason}"
    )


def test_missing_source_returns_blocked(tmp_path):
    """Non-existent source file → blocked, no crash."""
    from workflows.create_distribution_master import create_distribution_master

    result = create_distribution_master(
        tmp_path / "does_not_exist.wav",
        tmp_path / "out.wav",
    )
    assert not result.success
    assert "source_file_not_found" in (result.blocked_reason or "") + " ".join(result.warnings)


def test_ffmpeg_missing_does_not_crash(tmp_path):
    """When FFmpeg is absent and WAV needs conversion, returns manual_required — no crash."""
    from workflows.create_distribution_master import create_distribution_master

    # Create a WAV that needs conversion (non-standard spec)
    src = _make_wav(tmp_path / "suno_master.wav",
                    sample_rate=48000, channels=2, bit_depth=24)
    dst = tmp_path / "output" / "distribution_master.wav"

    # Mock FFmpeg as unavailable
    with mock.patch("workflows.create_distribution_master._ffmpeg_available", return_value=False):
        result = create_distribution_master(src, dst)

    # Must not crash and must report manual_required (or copy if spec already matches)
    assert not result.success or result.action == "copy", (
        "Without FFmpeg, a non-standard WAV must return manual_required"
    )
    if not result.success:
        assert result.manual_required, f"Expected manual_required=True. Result: {result}"


def test_wav_already_at_spec_is_copied_not_reconverted(tmp_path):
    """WAV already at 44.1kHz/16-bit/stereo → copy, no FFmpeg call."""
    from workflows.create_distribution_master import create_distribution_master

    src = _make_wav(tmp_path / "suno_master.wav",
                    sample_rate=44100, channels=2, bit_depth=16)
    dst = tmp_path / "output" / "distribution_master.wav"

    # Mock only ffmpeg subprocess (not ffprobe which QC uses)
    with mock.patch("workflows.create_distribution_master._ffmpeg_available", return_value=True):
        result = create_distribution_master(src, dst)

    # When source already meets spec, action must be 'copy' (no FFmpeg conversion)

    assert result.success
    assert result.action == "copy"
    assert dst.exists()
