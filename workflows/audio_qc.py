"""
Seoul Records Production OS — Audio QC Workflow (v0.2.0)

Priority chain:
  1. ffprobe   (most accurate — full codec info)
  2. wave      (stdlib — WAV/PCM only, no codec detail)
  3. mutagen   (already in requirements — broad format support)

Fake-WAV detection:
  A file with .wav extension is accepted as WAV only when the
  actual container/codec is PCM (wav, pcm_s16le, pcm_s24le, pcm_s32le,
  pcm_f32le, pcm_u8, …).  MP3 / AAC / M4A data inside a .wav wrapper
  is rejected for distribution.
"""
from __future__ import annotations

import shutil
import struct
import subprocess
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ─── Seoul Records duration targets ──────────────────────────────────────────
TARGET_DURATION_MIN_SECONDS = 210  # 3:30
TARGET_DURATION_MAX_SECONDS = 240  # 4:00

# ─── PCM codec whitelist ─────────────────────────────────────────────────────
_PCM_CODECS = {
    "pcm_s16le", "pcm_s16be",
    "pcm_s24le", "pcm_s24be",
    "pcm_s32le", "pcm_s32be",
    "pcm_f32le", "pcm_f32be",
    "pcm_u8",
    "wav",       # ffprobe sometimes reports container as codec for plain WAV
}

# WAV RIFF magic bytes
_WAV_RIFF = b"RIFF"
_WAV_WAVE = b"WAVE"


@dataclass
class AudioQCResult:
    file_path: str
    exists: bool = False
    is_wav: bool = False            # True only when confirmed PCM/WAV
    is_fake_wav: bool = False       # .wav extension but non-PCM codec inside
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    bit_depth: Optional[int] = None
    codec: Optional[str] = None
    container: Optional[str] = None
    distribution_eligible: bool = False
    warnings: list[str] = field(default_factory=list)
    method: str = "none"            # "ffprobe" | "wave" | "mutagen" | "header"


# ─── Helper: check magic bytes ───────────────────────────────────────────────

def _has_wav_header(path: Path) -> bool:
    """Check RIFF....WAVE magic without any library."""
    try:
        with open(path, "rb") as f:
            riff = f.read(4)
            f.seek(8)
            wave = f.read(4)
        return riff == _WAV_RIFF and wave == _WAV_WAVE
    except Exception:
        return False


def _has_mp3_header(path: Path) -> bool:
    """Quick check for ID3 tag or MP3 sync word."""
    try:
        with open(path, "rb") as f:
            header = f.read(10)
        # ID3 tag
        if header[:3] == b"ID3":
            return True
        # MPEG sync word
        if len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
            return True
        return False
    except Exception:
        return False


# ─── Method 1: ffprobe ───────────────────────────────────────────────────────

def _ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def _qc_via_ffprobe(path: Path) -> AudioQCResult:
    result = AudioQCResult(file_path=str(path), exists=True, method="ffprobe")
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", "-show_format",
                str(path),
            ],
            capture_output=True, text=True, timeout=15,
        )
        if proc.returncode != 0:
            result.warnings.append("ffprobe_error")
            # Even on ffprobe failure, check magic bytes for fake-WAV detection
            if path.suffix.lower() == ".wav":
                if not _has_wav_header(path):
                    result.is_fake_wav = True
                    if _has_mp3_header(path):
                        result.warnings.append("fake_wav_codec_mp3")
                    else:
                        result.warnings.append("fake_wav_invalid_header")
                    result.warnings.append("not_pcm_wav_distribution_blocked")
            return result

        data = json.loads(proc.stdout)
        fmt = data.get("format", {})
        streams = data.get("streams", [])

        # Pick first audio stream
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        if not audio:
            result.warnings.append("no_audio_stream")
            return result

        codec = audio.get("codec_name", "").lower()
        container = fmt.get("format_name", "").lower()

        result.codec = codec
        result.container = container
        result.duration_seconds = float(
            audio.get("duration") or fmt.get("duration") or 0
        ) or None
        result.sample_rate = int(audio.get("sample_rate", 0)) or None
        result.channels = int(audio.get("channels", 0)) or None

        # bit_depth: bits_per_raw_sample or bits_per_sample
        bps = audio.get("bits_per_raw_sample") or audio.get("bits_per_sample")
        result.bit_depth = int(bps) if bps else None

        # PCM / WAV check
        is_pcm = codec in _PCM_CODECS or codec.startswith("pcm_")
        result.is_wav = is_pcm

        # Fake-WAV detection: .wav extension but non-PCM codec
        if path.suffix.lower() == ".wav" and not is_pcm:
            result.is_fake_wav = True
            result.warnings.append(f"fake_wav_codec_{codec}")

        # Distribution eligibility
        if result.is_wav and not result.is_fake_wav:
            if result.duration_seconds and result.duration_seconds > 0:
                result.distribution_eligible = True
            else:
                result.warnings.append("duration_unknown")
        else:
            result.warnings.append("not_pcm_wav_distribution_blocked")

    except subprocess.TimeoutExpired:
        result.warnings.append("ffprobe_timeout")
    except Exception as e:
        result.warnings.append(f"ffprobe_exception_{type(e).__name__}")

    return result


# ─── Method 2: wave stdlib ───────────────────────────────────────────────────

def _qc_via_wave(path: Path) -> AudioQCResult:
    import wave as wave_mod
    result = AudioQCResult(file_path=str(path), exists=True, method="wave")

    # Bail out immediately on magic-byte mismatch
    if not _has_wav_header(path):
        result.is_fake_wav = path.suffix.lower() == ".wav"
        if result.is_fake_wav:
            if _has_mp3_header(path):
                result.warnings.append("fake_wav_codec_mp3")
            else:
                result.warnings.append("fake_wav_invalid_header")
        else:
            result.warnings.append("not_wav_format")
        result.warnings.append("not_pcm_wav_distribution_blocked")
        return result

    try:
        with wave_mod.open(str(path), "rb") as wf:
            result.sample_rate = wf.getframerate()
            result.channels = wf.getnchannels()
            result.bit_depth = wf.getsampwidth() * 8
            nframes = wf.getnframes()
            result.duration_seconds = (
                nframes / result.sample_rate if result.sample_rate else None
            )
        result.is_wav = True
        result.codec = "pcm_s%dle" % result.bit_depth if result.bit_depth else "pcm"
        result.container = "wav"
        if result.duration_seconds and result.duration_seconds > 0:
            result.distribution_eligible = True
        else:
            result.warnings.append("duration_unknown")
    except wave_mod.Error as e:
        # wave module can't open it → probably not PCM
        result.is_fake_wav = path.suffix.lower() == ".wav"
        result.warnings.append(f"wave_error_{str(e)[:40]}")
        result.warnings.append("not_pcm_wav_distribution_blocked")

    return result


# ─── Method 3: mutagen fallback ──────────────────────────────────────────────

def _qc_via_mutagen(path: Path) -> AudioQCResult:
    result = AudioQCResult(file_path=str(path), exists=True, method="mutagen")
    try:
        from mutagen import File as MutagenFile  # type: ignore
        audio = MutagenFile(str(path))
        if audio is None:
            result.warnings.append("mutagen_unrecognised_format")
            return result

        result.duration_seconds = getattr(audio.info, "length", None)
        result.sample_rate = getattr(audio.info, "sample_rate", None)
        result.channels = getattr(audio.info, "channels", None)
        result.bit_depth = getattr(audio.info, "bits_per_sample", None)

        # Try to identify codec from class name
        cls = type(audio).__name__.lower()
        if "wave" in cls or "aiff" in cls:
            result.is_wav = True
            result.codec = "pcm"
            result.container = "wav"
            result.distribution_eligible = bool(result.duration_seconds)
        else:
            result.codec = cls
            result.warnings.append(f"not_pcm_wav_distribution_blocked")
            if path.suffix.lower() == ".wav":
                result.is_fake_wav = True
                result.warnings.append(f"fake_wav_codec_{cls}")

    except ImportError:
        result.warnings.append("mutagen_not_available")
    except Exception as e:
        result.warnings.append(f"mutagen_exception_{type(e).__name__}")

    return result


# ─── Public API ──────────────────────────────────────────────────────────────

def run_audio_qc(file_path: str | Path) -> AudioQCResult:
    """
    Run Audio QC on a file using the best available method.

    Priority: ffprobe → wave → mutagen → header-only fallback.
    Never raises; all errors are captured in AudioQCResult.warnings.
    """
    path = Path(file_path)
    result = AudioQCResult(file_path=str(path))

    if not path.exists():
        result.warnings.append("file_not_found")
        return result

    result.exists = True

    if _ffprobe_available():
        return _qc_via_ffprobe(path)

    # wave module handles standard PCM WAV only
    if path.suffix.lower() == ".wav":
        r = _qc_via_wave(path)
        if r.warnings and any("wave_error" in w for w in r.warnings):
            # wave failed; try mutagen
            return _qc_via_mutagen(path)
        return r

    # Non-WAV extension → mutagen for duration/sample_rate
    return _qc_via_mutagen(path)


def qc_result_to_track_fields(result: AudioQCResult) -> dict:
    """
    Convert an AudioQCResult into a dict of TrackManifest field updates.
    """
    return {
        "is_wav": result.is_wav and not result.is_fake_wav,
        "duration_seconds": result.duration_seconds,
        "distribution_eligible": result.distribution_eligible,
        "qc_warnings": result.warnings,
        "duration_warning": get_duration_warning(result.duration_seconds),
    }


def get_duration_warning(duration_seconds: Optional[float]) -> Optional[str]:
    """
    Return a human-readable duration warning string, or None if in target range.
    Target: 3:30 (210s) – 4:00 (240s).
    Below target → warning only, distribution not blocked.
    Above target → strict_duration policy applies (handled by select_best_candidate).
    """
    if duration_seconds is None:
        return None
    if duration_seconds < TARGET_DURATION_MIN_SECONDS:
        m, s = divmod(int(duration_seconds), 60)
        return f"Duration {m}:{s:02d} is below target 3:30 — regeneration recommended"
    if duration_seconds > TARGET_DURATION_MAX_SECONDS:
        m, s = divmod(int(duration_seconds), 60)
        return f"Duration {m}:{s:02d} exceeds 4:00 — strict policy: both candidates must be in range"
    return None
