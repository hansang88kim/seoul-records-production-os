"""
services/unitedmasters/track_builder.py — tracklist from playlist order (v0.9.0).

Builds the UnitedMasters track list from the Video Renderer's playlist_plan
(the source of truth for order). MP3 = source/YouTube audio only — it never
counts as a distribution master. WAV/FLAC, when actually present, flips a track
to distribution_ready. NO fake WAV is ever created.
"""
from __future__ import annotations

import re
from pathlib import Path


DISTRIBUTION_MASTER_EXTS = (".wav", ".flac")
SOURCE_AUDIO_EXTS = (".mp3",)


def _clean_title(name: str) -> str:
    """Turn a filename into a readable track title (no extension, no underscores)."""
    stem = Path(name).stem
    stem = stem.replace("_", " ").strip()
    # Drop a leading track-number prefix like "01 " if present
    stem = re.sub(r"^\d{1,2}\s+", "", stem)
    return stem or name


def _audio_duration(path: str) -> float:
    try:
        import mutagen
        m = mutagen.File(path)
        if m and m.info:
            return float(m.info.length or 0.0)
    except Exception:
        pass
    return 0.0


def unique_tracks_from_plan(playlist_plan: dict) -> list[dict]:
    """
    Extract the UNIQUE tracks in playlist order (ignoring repeat loops).
    Order follows first appearance in playlist_plan['entries'].
    """
    seen = {}
    order = []
    for entry in playlist_plan.get("entries", []):
        name = entry.get("name")
        if name and name not in seen:
            seen[name] = entry
            order.append(entry)
    return order


def _find_master(mp3_path: str) -> str | None:
    """
    Look for a sibling WAV/FLAC with the same stem next to the MP3 (a real
    distribution master the user has provided). Returns the path or None.
    Never creates anything.
    """
    p = Path(mp3_path)
    for ext in DISTRIBUTION_MASTER_EXTS:
        candidate = p.with_suffix(ext)
        if candidate.exists():
            return str(candidate)
    return None


def build_tracklist(playlist_plan: dict,
                    master_overrides: dict | None = None) -> list[dict]:
    """
    Build the ordered tracklist.

    master_overrides: {mp3_path: master_wav_or_flac_path} for masters the user
    attached explicitly (validated elsewhere).

    Each track:
      {
        order, track_no (01..), title, mp3_path, duration_sec,
        master_path (wav/flac or None), master_ext,
        source_audio_mp3 (True), distribution_ready (bool), warnings[]
      }
    """
    master_overrides = master_overrides or {}
    tracks = []
    for i, entry in enumerate(unique_tracks_from_plan(playlist_plan), 1):
        mp3_path = entry.get("path", "")
        title = _clean_title(entry.get("name", f"track{i}"))
        duration = entry.get("duration_sec") or _audio_duration(mp3_path)

        # A real master: explicit override first, else a sibling wav/flac
        master = master_overrides.get(mp3_path) or _find_master(mp3_path)
        master_valid = bool(master and Path(master).exists()
                            and Path(master).suffix.lower() in DISTRIBUTION_MASTER_EXTS)

        warnings = []
        if not master_valid:
            warnings.append("WAV/FLAC master required for actual distribution")

        tracks.append({
            "order": i,
            "track_no": f"{i:02d}",
            "title": title,
            "mp3_path": mp3_path,
            "duration_sec": round(float(duration), 1),
            "master_path": master if master_valid else None,
            "master_ext": (Path(master).suffix.lower() if master_valid else None),
            "source_audio_mp3": True,
            "distribution_ready": master_valid,
            "warnings": warnings,
        })
    return tracks


def validate_audio(track: dict) -> dict:
    """
    Validate one track's audio. Returns a status dict. MP3-only is a draft with
    a warning; a valid WAV/FLAC master makes it distribution-ready.
    """
    mp3_ok = bool(track.get("mp3_path") and Path(track["mp3_path"]).exists())
    master = track.get("master_path")
    master_ok = bool(master and Path(master).exists()
                     and Path(master).suffix.lower() in DISTRIBUTION_MASTER_EXTS)

    if master_ok:
        return {
            "status": "Distribution Ready",
            "distribution_ready": True,
            "source_audio_mp3": mp3_ok,
            "master_ext": Path(master).suffix.lower(),
            "duration_sec": track.get("duration_sec", 0),
        }
    return {
        "status": "MP3-only Warning" if mp3_ok else "Missing WAV/FLAC",
        "distribution_ready": False,
        "source_audio_mp3": mp3_ok,
        "warning": "WAV/FLAC master required for actual distribution",
        "duration_sec": track.get("duration_sec", 0),
    }


def tracklist_distribution_ready(tracks: list[dict]) -> bool:
    """A package is distribution-ready only if EVERY track has a valid master."""
    return bool(tracks) and all(t.get("distribution_ready") for t in tracks)


# ─── Track order sync with the Video Renderer ────────────────────────────────

def order_matches_playlist(tracks: list[dict], playlist_plan: dict) -> bool:
    """True if the package track order equals the playlist's unique order."""
    plan_order = [t.get("name") and _clean_title(t["name"])
                  for t in unique_tracks_from_plan(playlist_plan)]
    pkg_order = [t["title"] for t in tracks]
    return plan_order == pkg_order


def sync_order_from_playlist(playlist_plan: dict,
                             master_overrides: dict | None = None) -> list[dict]:
    """Rebuild the tracklist in the exact playlist order (source of truth)."""
    return build_tracklist(playlist_plan, master_overrides)
