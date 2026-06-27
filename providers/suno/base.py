"""
Seoul Records Production OS — Composer Provider Base Interface
All Suno-compatible providers must implement this interface.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path


class ComposerProvider(ABC):
    """Abstract base for all song generation providers."""

    @abstractmethod
    def get_capabilities(self) -> dict:
        """Return what this provider supports."""
        ...

    @abstractmethod
    def create_song(
        self,
        title: str,
        style: str,
        lyrics: str,
        options: dict | None = None,
    ) -> str:
        """
        Submit a song generation request.
        Returns task_id.
        """
        ...

    @abstractmethod
    def get_status(self, task_id: str) -> dict:
        """
        Poll task status.
        Returns dict with at least: status, progress, error
        """
        ...

    @abstractmethod
    def download_wav(self, task_id: str, output_path: Path) -> Path:
        """
        Download WAV for a completed task.
        Returns path to saved file.
        """
        ...

    @abstractmethod
    def download_mp3_preview(self, task_id: str, output_path: Path) -> Path | None:
        """
        Download MP3 preview (fallback only).
        Returns path or None if unavailable.
        """
        ...

    @abstractmethod
    def get_metadata(self, task_id: str) -> dict:
        """Return all available metadata for a task."""
        ...
