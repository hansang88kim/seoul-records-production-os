"""
tests/test_audio_qc.py
─────────────────────
Audio QC tests — all pass regardless of whether ffprobe is installed.
Fake-WAV detection (MP3 data inside .wav extension) is validated via
magic-byte checks, so no external tool dependency.
"""
from __future__ import annotations

import struct
import wave
from pathlib import Path

import pytest


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_wav(path: Path, duration_s: float = 3.5, sample_rate: int = 44100,
              channels: int = 2, bit_depth: int = 16) -> Path:
    """Write a minimal valid PCM WAV file."""
    n_frames = int(sample_rate * duration_s)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(bit_depth // 8)
        wf.setframerate(sample_rate)
        # silent frames
        wf.writeframes(b"\x00" * n_frames * channels * (bit_depth // 8))
    return path


def _make_fake_wav(path: Path) -> Path:
    """Write an ID3-tagged MP3 stub with a .wav extension."""
    # Minimal ID3v2 header + FF FB sync word (simulates MP3 data)
    fake_data = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x00" * 50
    path.write_bytes(fake_data)
    return path


def _make_mp3(path: Path) -> Path:
    """Write a stub MP3 file."""
    fake_data = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x00" * 50
    path.write_bytes(fake_data)
    return path


# ─── Tests ───────────────────────────────────────────────────────────────────

def test_wav_qc_reads_duration_sample_rate_channels(tmp_path):
    """Valid PCM WAV: duration, sample_rate, channels are parsed correctly."""
    from workflows.audio_qc import run_audio_qc

    wav = _make_wav(tmp_path / "test.wav", duration_s=3.6, sample_rate=44100, channels=2)
    result = run_audio_qc(wav)

    assert result.exists
    assert result.is_wav, f"Expected is_wav=True, got warnings={result.warnings}"
    assert not result.is_fake_wav
    assert result.duration_seconds is not None
    assert abs(result.duration_seconds - 3.6) < 0.1, (
        f"Duration {result.duration_seconds:.2f}s not close to 3.6s"
    )
    assert result.sample_rate == 44100
    assert result.channels == 2
    assert result.distribution_eligible


def test_fake_wav_blocked(tmp_path):
    """MP3 data with .wav extension must be flagged as fake WAV and distribution-blocked."""
    from workflows.audio_qc import run_audio_qc

    fake = _make_fake_wav(tmp_path / "sneaky.wav")
    result = run_audio_qc(fake)

    assert result.exists
    assert result.is_fake_wav, (
        f"Expected is_fake_wav=True for MP3-in-WAV. "
        f"is_wav={result.is_wav}, warnings={result.warnings}"
    )
    assert not result.distribution_eligible, "Fake WAV must not be distribution eligible"
    # At least one warning about the fake codec or invalid header
    assert any(
        "fake_wav" in w or "not_pcm" in w for w in result.warnings
    ), f"Expected fake_wav warning, got: {result.warnings}"


def test_mp3_not_distribution_eligible(tmp_path):
    """MP3 file must not be distribution eligible."""
    from workflows.audio_qc import run_audio_qc

    mp3 = _make_mp3(tmp_path / "track.mp3")
    result = run_audio_qc(mp3)

    assert result.exists
    assert not result.distribution_eligible, (
        f"MP3 must not be distribution eligible. Warnings: {result.warnings}"
    )


def test_missing_file_returns_warning(tmp_path):
    """Non-existent file must return exists=False with file_not_found warning."""
    from workflows.audio_qc import run_audio_qc

    result = run_audio_qc(tmp_path / "does_not_exist.wav")

    assert not result.exists
    assert "file_not_found" in result.warnings
    assert not result.distribution_eligible


def test_qc_result_to_track_fields(tmp_path):
    """qc_result_to_track_fields maps correctly to TrackManifest fields."""
    from workflows.audio_qc import run_audio_qc, qc_result_to_track_fields

    wav = _make_wav(tmp_path / "track.wav", duration_s=4.0)
    result = run_audio_qc(wav)
    fields = qc_result_to_track_fields(result)

    assert "is_wav" in fields
    assert "duration_seconds" in fields
    assert "distribution_eligible" in fields
    assert "qc_warnings" in fields
    assert isinstance(fields["qc_warnings"], list)


def test_wav_44100_stereo_16bit(tmp_path):
    """Standard 44.1kHz/16-bit/stereo WAV passes all checks."""
    from workflows.audio_qc import run_audio_qc

    wav = _make_wav(tmp_path / "standard.wav",
                    duration_s=3.5, sample_rate=44100, channels=2, bit_depth=16)
    result = run_audio_qc(wav)

    assert result.is_wav
    assert result.sample_rate == 44100
    assert result.channels == 2
    assert result.bit_depth == 16
    assert result.distribution_eligible
