/**
 * lib/types.ts — frontend types aligned with the Python backend models.
 *
 * Mirrors the sanitized snapshot produced by api/snapshot.py and the existing
 * Python services (production_scanner, supervisor, job stores). These types
 * intentionally contain NO secret fields — the backend never sends tokens,
 * cookies, or keys to the frontend.
 */

export type JobStatus =
  | "idle"
  | "queued"
  | "running"
  | "rendering"
  | "uploading"
  | "completed"
  | "partial_success"
  | "failed"
  | "cancelled";

export type AssetStatus =
  | "Missing"
  | "Ready"
  | "Warning"
  | "Optional"
  | "Completed"
  | "Needs Review";

/** High-level pipeline stage status used on the dashboard. */
export type PipelineStage =
  | "song"
  | "thumbnail"
  | "video"
  | "youtube"
  | "distribution";

export interface PipelineStatus {
  stage: PipelineStage;
  label: string;
  score: number;
  status: AssetStatus;
}

export interface ChecklistItem {
  key: string;
  label: string;
  status: AssetStatus;
  optional: boolean;
  blocker: boolean;
  detail?: string;
}

export interface ProductionWarning {
  level: "blocker" | "warning" | "optional";
  message: string;
}

/** Production readiness scores + next action + warnings. */
export interface ProductionReadiness {
  overall_readiness: number;
  song_readiness: number;
  visual_readiness: number;
  video_readiness: number;
  youtube_package_readiness: number;
  upload_readiness: number;
  unitedmasters_readiness: number;
  next_action: string;
  warnings: ProductionWarning[];
  groups: Record<string, ChecklistItem[]>;
}

export interface AssetSummary {
  kind: "song" | "thumbnail" | "video" | "cover";
  name: string;
  status: AssetStatus;
  path?: string;
}

export interface SongTrack {
  title: string;
  duration_sec: number;
  created_at?: string;
}

export interface ThumbnailAsset {
  label: string;
  status: AssetStatus;
}

export interface VideoRenderJob {
  id: string;
  status: JobStatus;
  progress_percent: number;
  output?: string;
  eta?: string;
}

export interface YouTubePackage {
  package_id: string;
  title: string;
  privacy_status: "private" | "unlisted";
  upload_status: JobStatus;
  thumbnail_ready: boolean;
}

export interface UnitedMastersTrack {
  order: number;
  track_no: string;
  title: string;
  duration_sec: number;
  source_audio_mp3: boolean;
  distribution_ready: boolean;
  warnings: string[];
}

export interface UnitedMastersPackage {
  package_id: string;
  release_title: string;
  artist_name: string;
  status: string;
  distribution_ready: boolean;
  mp3_only: boolean;
  tracks: UnitedMastersTrack[];
}

export interface SupervisorStatus {
  status: "starting" | "healthy" | "restarting" | "degraded" | "stopped";
  streamlit_running: boolean;
  streamlit_http_status: number | null;
  last_health_check_at: string | null;
  restart_count_last_hour: number;
}

export interface RemoteControlStatus {
  supervisor: SupervisorStatus;
  telegram_enabled: boolean;
  telegram_package_installed: boolean;
  allowed_chat_id_count: number;
  tailscale_status: string | null;
}

export interface ActiveJob {
  id: string;
  kind: "song" | "video_render" | "youtube_upload";
  status: JobStatus;
  progress_percent: number;
  label: string;
  eta?: string;
}

export interface DashboardStatus {
  generated_at: string;
  pipeline: PipelineStatus[];
  active_jobs: ActiveJob[];
  latest_songs: SongTrack[];
  latest_renders: VideoRenderJob[];
  readiness: ProductionReadiness;
  remote_control: RemoteControlStatus;
}
