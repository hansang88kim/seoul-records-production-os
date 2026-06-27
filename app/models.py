"""
Seoul Records Production OS — Core Data Models (Pydantic v2)
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any
from pydantic import BaseModel, Field
from app.state_machine import ProjectStatus, TrackStatus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Candidate ────────────────────────────────────────────────────────────────

class CandidateMetadata(BaseModel):
    candidate_id: str                       # "A" or "B"
    task_id: str
    file_path: Optional[str] = None
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    bit_depth: Optional[int] = None
    file_format: Optional[str] = None      # "wav" | "mp3"
    is_wav: bool = False
    qc_warnings: list[str] = Field(default_factory=list)
    provider: str = "mock"
    created_at: str = Field(default_factory=_now)


# ─── Track ────────────────────────────────────────────────────────────────────

class TrackPrompt(BaseModel):
    title: str = ""
    lyrics: str = ""
    style: str = ""
    # FIX: list[str] not str — stored as list, UI joins/splits for display
    exclude_styles: list[str] = Field(default_factory=list)
    vocal_gender: str = "Female"           # Auto | Female | Male
    weirdness: int = 30
    style_influence: int = 70
    instrumental: bool = False
    model: str = "v5.5"
    persona_voice_id: Optional[str] = None

    title_locked: bool = False
    style_locked: bool = False
    lyrics_locked: bool = False


class TrackManifest(BaseModel):
    track_number: int
    track_id: str
    status: TrackStatus = TrackStatus.DRAFT_CREATED
    prompt: TrackPrompt = Field(default_factory=TrackPrompt)
    task_id: Optional[str] = None
    candidates: list[CandidateMetadata] = Field(default_factory=list)
    selected_candidate_id: Optional[str] = None
    track_folder_path: Optional[str] = None
    selected_wav_path: Optional[str] = None
    duration_seconds: Optional[float] = None
    is_wav: bool = False
    distribution_eligible: bool = False
    qc_warnings: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)

    def update_status(self, new_status: TrackStatus) -> None:
        self.status = new_status
        self.updated_at = _now()


# ─── Visual ───────────────────────────────────────────────────────────────────

class VisualManifest(BaseModel):
    status: str = "pending"
    youtube_thumbnail_path: Optional[str] = None
    dsp_cover_path: Optional[str] = None
    youtube_thumbnail_16x9: bool = False
    dsp_cover_1x1: bool = False
    cover_dimensions_ok: bool = False
    no_text_flag: bool = True
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


# ─── Video ────────────────────────────────────────────────────────────────────

class VideoManifest(BaseModel):
    status: str = "pending"
    final_video_path: Optional[str] = None
    final_audio_mix_path: Optional[str] = None
    render_command_path: Optional[str] = None
    timestamps_generated: bool = False
    chapters_generated: bool = False
    total_duration_seconds: Optional[float] = None
    track_count: int = 0
    manual_required: bool = False
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


# ─── YouTube ──────────────────────────────────────────────────────────────────

class YouTubeManifest(BaseModel):
    status: str = "pending"
    title: Optional[str] = None
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    package_path: Optional[str] = None
    private_url: Optional[str] = None
    uploaded: bool = False
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


# ─── Distribution ─────────────────────────────────────────────────────────────

class DistributionManifest(BaseModel):
    status: str = "pending"
    package_path: Optional[str] = None
    wav_masters_count: int = 0
    wav_masters_ready: bool = False
    cover_ready: bool = False
    metadata_ready: bool = False
    rights_statements_ready: bool = False
    blocked_reason: Optional[str] = None
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


# ─── Project Manifest ─────────────────────────────────────────────────────────

class ProjectManifest(BaseModel):
    project_id: str
    project_name: str
    core_style: str = "Seoul Records City Pop Core"
    language_pack: str = "ko_kr_seoul"
    theme: str = ""
    track_count: int = 5
    production_mode: str = "Manual"
    output_type: str = "YouTube + Distribution Package"
    output_folder: str = ""
    status: ProjectStatus = ProjectStatus.PROJECT_CREATED
    app_version: str = "0.1.3"

    tracks: list[TrackManifest] = Field(default_factory=list)
    visual: VisualManifest = Field(default_factory=VisualManifest)
    video: VideoManifest = Field(default_factory=VideoManifest)
    youtube: YouTubeManifest = Field(default_factory=YouTubeManifest)
    distribution: DistributionManifest = Field(default_factory=DistributionManifest)

    auto_mode_last_job_time: Optional[str] = None
    auto_mode_active: bool = False

    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)

    def update_status(self, new_status: ProjectStatus) -> None:
        self.status = new_status
        self.updated_at = _now()

    def completed_tracks(self) -> list[TrackManifest]:
        return [t for t in self.tracks if t.status == TrackStatus.SAVED]

    def approved_tracks(self) -> list[TrackManifest]:
        return [t for t in self.tracks
                if t.status in (TrackStatus.SAVED, TrackStatus.APPROVED)]


# ─── Log Entry ────────────────────────────────────────────────────────────────

class LogEntry(BaseModel):
    timestamp: str = Field(default_factory=_now)
    level: str = "INFO"
    step: str
    action: str
    details: dict[str, Any] = Field(default_factory=dict)
    track_id: Optional[str] = None
    project_id: Optional[str] = None
