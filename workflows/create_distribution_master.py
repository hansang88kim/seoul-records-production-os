"""
Seoul Records Production OS — Distribution Master Workflow (v0.2.0)

Rules:
  • Source MUST be suno_master.wav (PCM/WAV confirmed by Audio QC)
  • MP3 / AAC / M4A / fake-WAV → immediate error, no conversion
  • If source is already 16-bit / 44.1 kHz / stereo → copy (no re-encode)
  • Otherwise → FFmpeg conversion (lossless PCM target)
  • FFmpeg unavailable → report manual_required, do NOT crash
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from workflows.audio_qc import run_audio_qc, AudioQCResult

# ─── Target spec ─────────────────────────────────────────────────────────────
TARGET_SAMPLE_RATE = 44100
TARGET_CHANNELS = 2
TARGET_BIT_DEPTH = 16


@dataclass
class DistributionMasterResult:
    success: bool = False
    source_path: Optional[str] = None
    output_path: Optional[str] = None
    source_qc: Optional[AudioQCResult] = None
    action: str = "none"           # "copy" | "ffmpeg_convert" | "manual_required" | "blocked"
    manual_required: bool = False
    blocked_reason: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _meets_target_spec(qc: AudioQCResult) -> bool:
    """True when source already matches 16-bit / 44.1kHz / stereo."""
    return (
        qc.sample_rate == TARGET_SAMPLE_RATE
        and qc.channels == TARGET_CHANNELS
        and qc.bit_depth == TARGET_BIT_DEPTH
    )


def create_distribution_master(
    source_wav_path: str | Path,
    output_path: str | Path,
) -> DistributionMasterResult:
    """
    Create distribution_master.wav from suno_master.wav.

    Never raises — all errors captured in DistributionMasterResult.
    """
    source = Path(source_wav_path)
    dest = Path(output_path)
    result = DistributionMasterResult(source_path=str(source))

    # ── Step 1: Source must exist ─────────────────────────────────────────────
    if not source.exists():
        result.blocked_reason = "source_file_not_found"
        result.warnings.append("source_file_not_found")
        return result

    # ── Step 2: Audio QC on source ────────────────────────────────────────────
    qc = run_audio_qc(source)
    result.source_qc = qc

    # ── Step 3: Strict WAV/PCM gate ───────────────────────────────────────────
    if qc.is_fake_wav:
        result.blocked_reason = (
            f"fake_wav_blocked — source codec is {qc.codec}, not PCM. "
            "MP3-to-WAV conversion is not permitted as distribution master."
        )
        result.warnings.extend(qc.warnings)
        result.warnings.append("distribution_master_blocked_fake_wav")
        result.action = "blocked"
        return result

    if not qc.is_wav:
        codec_info = qc.codec or "unknown"
        result.blocked_reason = (
            f"non_wav_source_blocked — codec={codec_info}. "
            "Only PCM WAV files are accepted as distribution master source."
        )
        result.warnings.extend(qc.warnings)
        result.warnings.append(f"distribution_master_blocked_non_wav_{codec_info}")
        result.action = "blocked"
        return result

    # ── Step 4: Ensure output directory ──────────────────────────────────────
    dest.parent.mkdir(parents=True, exist_ok=True)

    # ── Step 5: Copy if already at target spec ────────────────────────────────
    if _meets_target_spec(qc):
        shutil.copy2(source, dest)
        result.success = True
        result.output_path = str(dest)
        result.action = "copy"
        return result

    # ── Step 6: FFmpeg conversion ─────────────────────────────────────────────
    if not _ffmpeg_available():
        result.manual_required = True
        result.action = "manual_required"
        result.warnings.append(
            f"ffmpeg_not_found — source is {qc.sample_rate}Hz/{qc.bit_depth}bit/"
            f"{qc.channels}ch, target is {TARGET_SAMPLE_RATE}Hz/"
            f"{TARGET_BIT_DEPTH}bit/{TARGET_CHANNELS}ch. "
            "Install FFmpeg to auto-convert."
        )
        return result

    cmd = [
        "ffmpeg", "-y",
        "-i", str(source),
        "-ar", str(TARGET_SAMPLE_RATE),
        "-ac", str(TARGET_CHANNELS),
        "-sample_fmt", "s16",   # 16-bit signed little-endian PCM
        "-acodec", "pcm_s16le",
        str(dest),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode == 0 and dest.exists():
            result.success = True
            result.output_path = str(dest)
            result.action = "ffmpeg_convert"
        else:
            result.manual_required = True
            result.action = "manual_required"
            result.warnings.append(
                f"ffmpeg_convert_failed — returncode={proc.returncode}"
            )
            if proc.stderr:
                result.warnings.append(f"ffmpeg_stderr: {proc.stderr[:200]}")
    except subprocess.TimeoutExpired:
        result.manual_required = True
        result.action = "manual_required"
        result.warnings.append("ffmpeg_timeout")
    except Exception as e:
        result.manual_required = True
        result.action = "manual_required"
        result.warnings.append(f"ffmpeg_exception_{type(e).__name__}")

    return result


def get_distribution_master_path(output_folder: Path, track_number: int) -> Path:
    """Canonical path for a track's distribution_master.wav."""
    return (
        output_folder
        / "05_music_distribution"
        / "unitedmasters"
        / "audio"
        / f"track_{track_number:02d}_distribution_master.wav"
    )
