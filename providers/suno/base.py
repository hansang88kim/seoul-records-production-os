"""
Seoul Records Production OS — Composer Provider Base Interface (v0.3)
All Suno-compatible providers must implement this interface.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ─── Normalized error statuses ───────────────────────────────────────────────

class ProviderError(Exception):
    """Base exception for all provider errors."""
    def __init__(self, status: str, message: str, details: dict | None = None):
        self.status = status
        self.message = message
        self.details = details or {}
        super().__init__(f"[{status}] {message}")


PROVIDER_ERROR_STATUSES = [
    "provider_unavailable",
    "auth_required",
    "captcha_required",
    "two_factor_required",
    "generation_failed",
    "polling_timeout",
    "wav_download_unavailable",
    "mp3_only_preview",
    "manual_import_required",
    "rate_limited",
    "unknown_provider_error",
]


# ─── Standardized Capabilities ───────────────────────────────────────────────

@dataclass
class ProviderCapabilities:
    """Standardized capability reporting for all Suno providers."""
    provider: str
    status: str = "ready"       # "ready" | "not_implemented" | "unavailable"

    # Input support
    title: bool = False
    lyrics: bool = False
    style: bool = False
    exclude_styles: bool = False
    vocal_gender: bool = False
    weirdness: bool = False
    style_influence: bool = False
    instrumental: bool = False
    model_selector: bool = False
    persona: bool = False

    # Output support
    two_candidates: bool = False
    wav_download: bool = False
    mp3_preview: bool = False
    supports_polling: bool = False

    # Auth
    requires_user_session: bool = False
    requires_api_key: bool = False
    requires_credentials: bool = False

    # Limitations
    note: Optional[str] = None
    fallback_instructions: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


# ─── Normalized response schemas ─────────────────────────────────────────────

@dataclass
class SongGenerationResult:
    """Normalized result from create_song."""
    task_id: str
    status: str = "submitted"   # "submitted" | "generating" | "completed" | "failed"
    candidates: list[dict] = field(default_factory=list)
    error: Optional[str] = None
    provider: str = ""


@dataclass
class CandidateInfo:
    """Normalized candidate info."""
    candidate_id: str           # "A" or "B"
    suno_clip_id: Optional[str] = None
    audio_url: Optional[str] = None
    wav_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    status: str = "pending"     # "pending" | "streaming" | "completed" | "failed"
    metadata: dict = field(default_factory=dict)


# ─── Base class ──────────────────────────────────────────────────────────────

class ComposerProvider(ABC):
    """Abstract base for all song generation providers."""

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
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

    def get_candidates(self, task_id: str) -> list[CandidateInfo]:
        """Get candidate info for a completed task. Optional override."""
        return []

    def safe_error(self, status: str, message: str, **details) -> ProviderError:
        """Create a ProviderError that never exposes credentials."""
        # Scrub any credential-like values from details
        safe = {}
        for k, v in details.items():
            s = str(v)
            if any(w in k.lower() for w in ("cookie", "token", "key", "secret", "password")):
                safe[k] = "***REDACTED***"
            elif len(s) > 200:
                safe[k] = s[:200] + "..."
            else:
                safe[k] = s
        return ProviderError(status, message, safe)
