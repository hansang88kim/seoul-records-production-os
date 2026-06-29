/**
 * lib/api.ts — backend boundary for the Studio Console.
 *
 * v1.0.0-alpha ships mock-first: each getter returns typed mock data so the UI
 * is fully navigable without a running backend. When the Python bridge
 * (api/snapshot.py exposed over HTTP) is available, set NEXT_PUBLIC_API_BASE and
 * the same typed calls fetch live, sanitized data.
 *
 * The backend NEVER returns secrets (tokens/cookies/keys/client_secret), so the
 * frontend has no code path that could render them.
 */
import type {
  DashboardStatus,
  ProductionReadiness,
  ActiveJob,
  AssetSummary,
  VideoRenderJob,
  YouTubePackage,
  UnitedMastersPackage,
  RemoteControlStatus,
} from "@/lib/types";
import {
  mockDashboard,
  mockReadiness,
  mockActiveJobs,
  mockSongs,
  mockRenders,
  mockYouTubePackages,
  mockUnitedMastersPackage,
  mockRemoteControl,
} from "@/lib/mock-data";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

async function fetchJson<T>(path: string, fallback: T): Promise<T> {
  if (!API_BASE) return fallback; // mock-first
  try {
    const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    if (!res.ok) return fallback;
    return (await res.json()) as T;
  } catch {
    return fallback;
  }
}

export async function getDashboardStatus(): Promise<DashboardStatus> {
  return fetchJson<DashboardStatus>("/api/dashboard", mockDashboard);
}

export async function getProductionReadiness(): Promise<ProductionReadiness> {
  return fetchJson<ProductionReadiness>("/api/production-readiness", mockReadiness);
}

export async function getActiveJobs(): Promise<ActiveJob[]> {
  return fetchJson<ActiveJob[]>("/api/jobs", mockActiveJobs);
}

export async function getRecentAssets(): Promise<AssetSummary[]> {
  const assets: AssetSummary[] = mockSongs.map((s) => ({
    kind: "song",
    name: s.title,
    status: "Ready",
  }));
  return fetchJson<AssetSummary[]>("/api/recent-assets", assets);
}

export async function getVideoRenderJobs(): Promise<VideoRenderJob[]> {
  return fetchJson<VideoRenderJob[]>("/api/video-renders", mockRenders);
}

export async function getYouTubePackages(): Promise<YouTubePackage[]> {
  return fetchJson<YouTubePackage[]>("/api/youtube-packages", mockYouTubePackages);
}

export async function getUnitedMastersPackages(): Promise<UnitedMastersPackage[]> {
  return fetchJson<UnitedMastersPackage[]>("/api/unitedmasters", [mockUnitedMastersPackage]);
}

export async function getRemoteControlStatus(): Promise<RemoteControlStatus> {
  return fetchJson<RemoteControlStatus>("/api/remote-control", mockRemoteControl);
}

export const IS_MOCK = API_BASE === "";
