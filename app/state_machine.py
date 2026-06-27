"""
Seoul Records Production OS — Global State Machine
Defines all project and track statuses.
"""
from enum import Enum


class ProjectStatus(str, Enum):
    PROJECT_CREATED = "project_created"
    SONG_GENERATION_READY = "song_generation_ready"
    SONG_GENERATION_IN_PROGRESS = "song_generation_in_progress"
    SONG_GENERATION_COMPLETED = "song_generation_completed"
    THUMBNAIL_READY = "thumbnail_ready"
    THUMBNAIL_COMPLETED = "thumbnail_completed"
    VIDEO_READY = "video_ready"
    VIDEO_RENDERED = "video_rendered"
    YOUTUBE_METADATA_READY = "youtube_metadata_ready"
    YOUTUBE_UPLOADED_PRIVATE = "youtube_uploaded_private"
    DISTRIBUTION_PACKAGE_READY = "distribution_package_ready"
    DISTRIBUTION_UPLOAD_ASSISTED = "distribution_upload_assisted"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class TrackStatus(str, Enum):
    DRAFT_CREATED = "draft_created"
    PROMPT_READY = "prompt_ready"
    MANUAL_REVIEW = "manual_review"
    CONFIRMED = "confirmed"
    SUBMITTED_TO_SUNO = "submitted_to_suno"
    SUNO_GENERATING = "suno_generating"
    CANDIDATES_READY = "candidates_ready"
    CANDIDATE_SELECTED = "candidate_selected"
    WAV_DOWNLOADED = "wav_downloaded"
    WAV_QC_PASSED = "wav_qc_passed"
    SAVED = "saved"
    APPROVED = "approved"
    FAILED = "failed"
    MANUAL_IMPORT_REQUIRED = "manual_import_required"
    REGENERATION_REQUIRED = "regeneration_required"


# Valid transitions for project status
PROJECT_TRANSITIONS: dict[ProjectStatus, list[ProjectStatus]] = {
    ProjectStatus.PROJECT_CREATED: [ProjectStatus.SONG_GENERATION_READY, ProjectStatus.FAILED],
    ProjectStatus.SONG_GENERATION_READY: [ProjectStatus.SONG_GENERATION_IN_PROGRESS, ProjectStatus.PAUSED],
    ProjectStatus.SONG_GENERATION_IN_PROGRESS: [
        ProjectStatus.SONG_GENERATION_COMPLETED,
        ProjectStatus.PAUSED,
        ProjectStatus.FAILED,
    ],
    ProjectStatus.SONG_GENERATION_COMPLETED: [ProjectStatus.THUMBNAIL_READY, ProjectStatus.FAILED],
    ProjectStatus.THUMBNAIL_READY: [ProjectStatus.THUMBNAIL_COMPLETED, ProjectStatus.PAUSED],
    ProjectStatus.THUMBNAIL_COMPLETED: [ProjectStatus.VIDEO_READY],
    ProjectStatus.VIDEO_READY: [ProjectStatus.VIDEO_RENDERED, ProjectStatus.PAUSED],
    ProjectStatus.VIDEO_RENDERED: [ProjectStatus.YOUTUBE_METADATA_READY],
    ProjectStatus.YOUTUBE_METADATA_READY: [ProjectStatus.YOUTUBE_UPLOADED_PRIVATE, ProjectStatus.PAUSED],
    ProjectStatus.YOUTUBE_UPLOADED_PRIVATE: [ProjectStatus.DISTRIBUTION_PACKAGE_READY],
    ProjectStatus.DISTRIBUTION_PACKAGE_READY: [ProjectStatus.DISTRIBUTION_UPLOAD_ASSISTED, ProjectStatus.COMPLETED],
    ProjectStatus.DISTRIBUTION_UPLOAD_ASSISTED: [ProjectStatus.COMPLETED],
    ProjectStatus.PAUSED: [
        ProjectStatus.SONG_GENERATION_READY,
        ProjectStatus.SONG_GENERATION_IN_PROGRESS,
        ProjectStatus.THUMBNAIL_READY,
        ProjectStatus.VIDEO_READY,
        ProjectStatus.YOUTUBE_METADATA_READY,
        ProjectStatus.DISTRIBUTION_PACKAGE_READY,
    ],
    ProjectStatus.FAILED: [ProjectStatus.SONG_GENERATION_READY],
    ProjectStatus.COMPLETED: [],
}
