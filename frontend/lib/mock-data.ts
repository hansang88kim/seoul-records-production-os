/**
 * lib/mock-data.ts — sanitized mock data for the v1.0.0-alpha prototype.
 *
 * Mirrors the shape of api/snapshot.py. NO secrets and no secret-like strings.
 * Used until the backend bridge is wired up; the types are identical so
 * swapping to live data is a one-line change in api.ts.
 */
import type {
  DashboardStatus,
  ProductionReadiness,
  UnitedMastersPackage,
  VideoRenderJob,
  YouTubePackage,
  RemoteControlStatus,
  ActiveJob,
  SongTrack,
} from "@/lib/types";

export const mockReadiness: ProductionReadiness = {
  overall_readiness: 72,
  song_readiness: 100,
  visual_readiness: 65,
  video_readiness: 58,
  youtube_package_readiness: 75,
  upload_readiness: 50,
  unitedmasters_readiness: 40,
  next_action:
    "30초 preview가 없습니다. Full render 전에 Video Renderer에서 preview를 먼저 생성하세요.",
  warnings: [
    {
      level: "warning",
      message:
        "Video Playback Background가 없습니다. 썸네일을 배경으로 쓰면 중앙 타이틀이 겹칠 수 있습니다.",
    },
    { level: "optional", message: "CTA 스티커가 없습니다 (브랜드 품질용 권장)." },
    {
      level: "warning",
      message:
        "UnitedMasters 패키지가 MP3-only입니다. 실제 배포에는 WAV/FLAC 마스터가 필요합니다.",
    },
  ],
  groups: {
    Songs: [
      { key: "mp3", label: "MP3 파일 (8개)", status: "Ready", optional: false, blocker: true },
      { key: "dur", label: "총 길이 30분", status: "Ready", optional: false, blocker: false },
    ],
    "Video render": [
      { key: "preview", label: "30초 preview", status: "Missing", optional: false, blocker: false },
      { key: "final", label: "final_video.mp4", status: "Missing", optional: false, blocker: true },
    ],
  },
};

export const mockSongs: SongTrack[] = [
  { title: "밤이 지나면", duration_sec: 212 },
  { title: "늦은 대답", duration_sec: 198 },
  { title: "네온 사인", duration_sec: 224 },
];

export const mockRenders: VideoRenderJob[] = [
  { id: "render_3600", status: "rendering", progress_percent: 42, output: "final_video.mp4", eta: "00:28:10" },
];

export const mockActiveJobs: ActiveJob[] = [
  { id: "r1", kind: "video_render", status: "rendering", progress_percent: 42, label: "Korea CityPop Vol.1", eta: "00:28:10" },
  { id: "s1", kind: "song", status: "idle", progress_percent: 0, label: "Suno" },
  { id: "y1", kind: "youtube_upload", status: "idle", progress_percent: 0, label: "YouTube" },
];

export const mockYouTubePackages: YouTubePackage[] = [
  {
    package_id: "pkg_0001",
    title: "Korea CityPop Playlist Vol.1",
    privacy_status: "private",
    upload_status: "idle",
    thumbnail_ready: true,
  },
];

export const mockUnitedMastersPackage: UnitedMastersPackage = {
  package_id: "um_0001",
  release_title: "Korea CityPop Playlist Vol.1",
  artist_name: "Seoul Records",
  status: "MP3-only Warning",
  distribution_ready: false,
  mp3_only: true,
  tracks: [
    { order: 1, track_no: "01", title: "밤이 지나면", duration_sec: 212, source_audio_mp3: true, distribution_ready: false, warnings: ["WAV/FLAC master required"] },
    { order: 2, track_no: "02", title: "늦은 대답", duration_sec: 198, source_audio_mp3: true, distribution_ready: false, warnings: ["WAV/FLAC master required"] },
    { order: 3, track_no: "03", title: "네온 사인", duration_sec: 224, source_audio_mp3: true, distribution_ready: false, warnings: ["WAV/FLAC master required"] },
  ],
};

export const mockRemoteControl: RemoteControlStatus = {
  supervisor: {
    status: "healthy",
    streamlit_running: true,
    streamlit_http_status: 200,
    last_health_check_at: new Date().toISOString(),
    restart_count_last_hour: 0,
  },
  telegram_enabled: false,
  telegram_package_installed: true,
  allowed_chat_id_count: 0,
  tailscale_status: null,
};

export const mockDashboard: DashboardStatus = {
  generated_at: new Date().toISOString(),
  pipeline: [
    { stage: "song", label: "Song Lab", score: 100, status: "Ready" },
    { stage: "thumbnail", label: "Thumbnail", score: 65, status: "Warning" },
    { stage: "video", label: "Video", score: 58, status: "Warning" },
    { stage: "youtube", label: "YouTube", score: 75, status: "Ready" },
    { stage: "distribution", label: "Distribution", score: 40, status: "Warning" },
  ],
  active_jobs: mockActiveJobs,
  latest_songs: mockSongs,
  latest_renders: mockRenders,
  readiness: mockReadiness,
  remote_control: mockRemoteControl,
};
