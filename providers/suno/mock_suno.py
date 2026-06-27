"""
providers/suno/mock_suno.py
────────────────────────────
MockSunoProvider — generates synthetic WAV candidates locally.
No network calls. Used for all v0.1 testing.

v0.1.2: fast_mode=True by default — generates tiny (3-5s) valid WAV files
while keeping metadata durations in the 210-240s range for candidate selection.
"""
from __future__ import annotations

import json
import math
import random
import struct
import uuid
from datetime import datetime, timezone
from pathlib import Path

from providers.suno.base import ComposerProvider


# ─── WAV Helpers ──────────────────────────────────────────────────────────────

def _generate_sine_wav(
    path: Path,
    frequency: float = 440.0,
    duration_seconds: float = 3.0,
    sample_rate: int = 44100,
    amplitude: float = 0.3,
) -> Path:
    """
    Generate a minimal valid PCM 16-bit stereo WAV file with a sine wave.

    In fast_mode (default), duration_seconds is small (3-5s) to keep files
    under 1 MB. The *metadata* still reports the simulated target duration.
    """
    num_samples = int(sample_rate * duration_seconds)
    num_channels = 2
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size = num_samples * block_align
    chunk_size = 36 + data_size

    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "wb") as f:
        # RIFF header
        f.write(b"RIFF")
        f.write(struct.pack("<I", chunk_size))
        f.write(b"WAVE")
        # fmt subchunk
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))
        f.write(struct.pack("<H", 1))            # PCM
        f.write(struct.pack("<H", num_channels))
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", byte_rate))
        f.write(struct.pack("<H", block_align))
        f.write(struct.pack("<H", bits_per_sample))
        # data subchunk
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        max_val = int(32767 * amplitude)
        for i in range(num_samples):
            sample = int(max_val * math.sin(2 * math.pi * frequency * i / sample_rate))
            packed = struct.pack("<h", sample)
            f.write(packed)  # L
            f.write(packed)  # R

    return path


def _read_wav_duration(path: Path) -> float | None:
    """Read actual duration from WAV header (stdlib only, no mutagen)."""
    try:
        with open(path, "rb") as f:
            f.seek(24)
            sample_rate = struct.unpack("<I", f.read(4))[0]
            f.seek(32)
            block_align = struct.unpack("<H", f.read(2))[0]
            f.seek(40)
            data_size = struct.unpack("<I", f.read(4))[0]
            if block_align == 0 or sample_rate == 0:
                return None
            return (data_size // block_align) / sample_rate
    except Exception:
        return None


# ─── MockSunoProvider ─────────────────────────────────────────────────────────

# Fast mode WAV duration: tiny file, just enough to be a valid WAV
_FAST_WAV_SECONDS = 3.0
# Full-length mode: write real-duration WAVs (slow, huge files)
_FULL_WAV_SECONDS_RANGE = (195.0, 245.0)


class MockSunoProvider(ComposerProvider):
    """
    Mock Suno provider for v0.1.
    Returns two synthetic WAV candidates per request.
    No network calls, no credentials required.

    fast_mode (default True):
        WAV files are 3 seconds long (~500 KB each).
        Metadata duration_seconds is simulated at 195-245 s for selection testing.

    fast_mode=False:
        WAV files are real 3-4 minute sine waves (~35 MB each).
        Use only when you need actual audio duration validation.
    """

    PROVIDER_NAME = "mock_suno"
    _tasks: dict[str, dict] = {}

    def __init__(self, fast_mode: bool = True) -> None:
        self.fast_mode = fast_mode

    def get_capabilities(self) -> dict:
        return {
            "provider": self.PROVIDER_NAME,
            "can_wav": True,
            "can_mp3": False,
            "requires_credentials": False,
            "max_concurrent_jobs": 1,
            "fast_mode": self.fast_mode,
            "note": "Mock provider — generates local sine-wave WAV files.",
        }

    def create_song(
        self,
        title: str,
        style: str,
        lyrics: str,
        options: dict | None = None,
    ) -> str:
        task_id = str(uuid.uuid4())
        # Simulated durations in the realistic range for candidate selection
        dur_a = random.uniform(195.0, 245.0)   # 3:15 – 4:05
        dur_b = random.uniform(185.0, 230.0)
        freq_a = random.choice([261.63, 293.66, 329.63, 349.23, 392.0])
        freq_b = random.choice([220.0, 246.94, 277.18, 311.13, 369.99])

        self._tasks[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "title": title,
            "style": style,
            "lyrics": lyrics,
            "options": options or {},
            "candidates": [
                {"candidate_id": "A", "duration_seconds": dur_a,
                 "frequency": freq_a, "file_format": "wav"},
                {"candidate_id": "B", "duration_seconds": dur_b,
                 "frequency": freq_b, "file_format": "wav"},
            ],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return task_id

    def get_status(self, task_id: str) -> dict:
        task = self._tasks.get(task_id)
        if not task:
            return {"status": "not_found", "error": f"Unknown task: {task_id}"}
        task["status"] = "completed"
        return {
            "status": task["status"],
            "task_id": task_id,
            "candidates": task["candidates"],
        }

    def download_wav(self, task_id: str, output_path: Path) -> Path:
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Unknown task: {task_id}")
        cand = task["candidates"][0]
        wav_dur = _FAST_WAV_SECONDS if self.fast_mode else cand["duration_seconds"]
        return _generate_sine_wav(output_path, cand["frequency"], wav_dur)

    def download_mp3_preview(self, task_id: str, output_path: Path) -> Path | None:
        return None

    def get_metadata(self, task_id: str) -> dict:
        task = self._tasks.get(task_id)
        if not task:
            return {}
        return {
            "task_id": task_id,
            "title": task.get("title"),
            "style": task.get("style"),
            "provider": self.PROVIDER_NAME,
            "candidates": task.get("candidates", []),
            "created_at": task.get("created_at"),
        }

    def download_candidates(
        self,
        task_id: str,
        candidates_folder: Path,
    ) -> list[dict]:
        """
        Download both WAV candidates.

        In fast_mode: WAV files are ~3 s (tiny), but metadata duration_seconds
        reflects the simulated 210-245 s value for candidate selection testing.
        """
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Unknown task: {task_id}")

        results = []
        for cand in task["candidates"]:
            cid = cand["candidate_id"]
            simulated_duration = cand["duration_seconds"]
            frequency = cand["frequency"]
            wav_path = candidates_folder / f"candidate_{cid}.wav"

            # Write a small or full-length WAV depending on mode
            wav_dur = _FAST_WAV_SECONDS if self.fast_mode else simulated_duration
            _generate_sine_wav(wav_path, frequency, wav_dur)

            # Report the *simulated* duration for selection logic,
            # NOT the actual file duration (which is 3 s in fast_mode)
            meta = {
                "candidate_id": cid,
                "task_id": task_id,
                "file_path": str(wav_path),
                "duration_seconds": simulated_duration,
                "actual_file_duration_seconds": wav_dur,
                "sample_rate": 44100,
                "channels": 2,
                "bit_depth": 16,
                "file_format": "wav",
                "is_wav": True,
                "fast_mode": self.fast_mode,
                "provider": self.PROVIDER_NAME,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            meta_path = candidates_folder / f"candidate_{cid}_metadata.json"
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            results.append(meta)

        return results
