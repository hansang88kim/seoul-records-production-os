"""
providers/suno/manual_import.py
────────────────────────────────
ManualImportProvider — user places WAV files into the candidates/ folder manually.
The provider validates them and marks the task as completed.
"""
from __future__ import annotations

import shutil
import struct
from pathlib import Path

from providers.suno.base import ComposerProvider


def _read_wav_duration(path: Path) -> float | None:
    """Read duration from WAV header (stdlib only)."""
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


class ManualImportProvider(ComposerProvider):
    """
    Manual Import Provider.
    User copies WAV files into the project's candidates/ folder.
    This provider validates and registers them.
    """

    PROVIDER_NAME = "manual_import"

    def get_capabilities(self) -> dict:
        return {
            "provider": self.PROVIDER_NAME,
            "can_wav": True,
            "can_mp3": True,
            "requires_credentials": False,
            "note": (
                "User manually places WAV files into candidates/ folder. "
                "Call import_wav() to validate and register."
            ),
        }

    def create_song(
        self,
        title: str,
        style: str,
        lyrics: str,
        options: dict | None = None,
    ) -> str:
        raise NotImplementedError(
            "ManualImportProvider: use import_wav() to register a manually placed file."
        )

    def get_status(self, task_id: str) -> dict:
        return {"status": "manual_import", "task_id": task_id}

    def download_wav(self, task_id: str, output_path: Path) -> Path:
        raise NotImplementedError(
            "ManualImportProvider: WAV is already provided by the user."
        )

    def download_mp3_preview(self, task_id: str, output_path: Path) -> Path | None:
        return None

    def get_metadata(self, task_id: str) -> dict:
        return {"provider": self.PROVIDER_NAME, "task_id": task_id}

    def import_wav(self, source_path: Path, dest_path: Path) -> dict:
        """
        Validate and copy a user-provided WAV (or MP3) into the project.
        Returns metadata dict.
        """
        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        ext = source_path.suffix.lower()
        is_wav = ext == ".wav"
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)

        duration = _read_wav_duration(dest_path) if is_wav else None
        return {
            "file_path": str(dest_path),
            "is_wav": is_wav,
            "duration_seconds": duration,
            "file_format": ext.lstrip("."),
            "provider": self.PROVIDER_NAME,
        }
