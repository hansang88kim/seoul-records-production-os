"""
services/unitedmasters/track_builder.py — tracklist from playlist order (v0.9.0).

Builds the UnitedMasters track list from the Video Renderer's playlist_plan
(the source of truth for order). MP3 = source/YouTube audio only — it never
counts as a distribution master. WAV/FLAC, when actually present, flips a track
to distribution_ready. NO fake WAV is ever created.
"""
from __future__ import annotations

from pathlib import Path

from services.youtube.metadata_generator import _clean_track_title
from workflows.audio_qc import run_audio_qc


DISTRIBUTION_MASTER_EXTS = (".wav", ".flac")
SOURCE_AUDIO_EXTS = (".mp3",)
SAMPLE_RATES = {44100, 48000, 96000, 176400, 192000}
MAX_AUDIO_BYTES = 150_000_000


def _clean_title(name: str) -> str:
    """Fall back to a readable name when the playlist predates display titles."""
    return _clean_track_title(Path(name).name).replace("_", " ").strip() or name


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
    seen = set()
    order = []
    for entry in playlist_plan.get("entries", []):
        key = entry.get("path") or entry.get("name")
        if key and key not in seen:
            seen.add(key)
            order.append(entry)
    return order


def _find_master(source_path: str) -> str | None:
    """
    Look for a sibling WAV/FLAC with the same stem next to the MP3 (a real
    distribution master the user has provided). Returns the path or None.
    Never creates anything.
    """
    if not source_path:
        return None
    p = Path(source_path)
    if p.suffix.lower() in DISTRIBUTION_MASTER_EXTS:
        return source_path
    for ext in DISTRIBUTION_MASTER_EXTS:
        candidate = p.with_suffix(ext)
        if candidate.is_file():
            return str(candidate)
    return None


def _check_master(master: str | None) -> tuple[dict, str]:
    if not master:
        return {}, "배포용 트랙 원본 WAV/FLAC를 연결하세요."
    path = Path(master)
    ext = path.suffix.lower()
    try:
        if ext not in DISTRIBUTION_MASTER_EXTS or not path.is_file():
            return {}, "배포 원본으로 읽을 수 있는 WAV/FLAC 파일을 선택하세요."
        if path.stem.lower().startswith("final_audio_mix"):
            return {}, "영상용 믹스가 선택됐습니다. 이 곡의 원본 파일을 연결하세요."
        if path.stat().st_size >= MAX_AUDIO_BYTES:
            return {}, "곡별 원본 파일은 웹 화면 기준 150 MB 미만이어야 합니다."
        qc = run_audio_qc(path)
    except (OSError, EOFError):
        return {}, "배포용 음원 파일을 읽을 수 없습니다."
    valid = (qc.distribution_eligible and qc.container == "wav" if ext == ".wav"
             else qc.codec == "flac" and qc.container in ("flac", None))
    if not valid or not qc.duration_seconds or qc.duration_seconds <= 0:
        return {}, "실제 PCM WAV 또는 FLAC 형식의 유효한 음원 파일을 연결하세요."
    if qc.bit_depth not in (16, 24) or qc.sample_rate not in SAMPLE_RATES:
        return {}, "16/24-bit 및 UnitedMasters 지원 샘플레이트의 원본을 연결하세요."
    return {"sample_rate": qc.sample_rate, "bit_depth": qc.bit_depth,
            "channels": qc.channels, "duration_sec": qc.duration_seconds}, ""


def build_tracklist(playlist_plan: dict, master_overrides: dict | None = None,
                    title_overrides: dict | None = None) -> list[dict]:
    """Build tracks in playback order with edits keyed by the playlist source path."""
    master_overrides = master_overrides or {}
    title_overrides = title_overrides or {}
    tracks = []
    master_paths = set()
    for i, entry in enumerate(unique_tracks_from_plan(playlist_plan), 1):
        source_path = entry.get("path") or ""
        title = (title_overrides.get(source_path) or entry.get("title")
                 or _clean_title(entry.get("name") or f"track{i}"))
        mp3_path = source_path if Path(source_path).suffix.lower() in SOURCE_AUDIO_EXTS else ""
        master = master_overrides.get(source_path) or _find_master(source_path)
        audio, warning = _check_master(master)
        if audio:
            identity = Path(master).resolve()
            if identity in master_paths:
                audio = {}
                warning = "다른 트랙에 이미 연결한 원본입니다. 곡마다 해당 원본을 연결하세요."
            master_paths.add(identity)
        duration = audio.get("duration_sec") or entry.get("duration_sec") or _audio_duration(source_path)

        tracks.append({
            "order": i,
            "track_no": f"{i:02d}",
            "title": title,
            "source_path": source_path,
            "mp3_path": mp3_path,
            "duration_sec": round(float(duration), 1),
            "master_path": master if audio else None,
            "master_ext": Path(master).suffix.lower() if audio else None,
            "master_audio": audio,
            "source_audio_mp3": bool(mp3_path and Path(mp3_path).is_file()),
            "distribution_ready": bool(audio),
            "warnings": [warning] if warning else [],
        })
    return tracks


def validate_audio(track: dict) -> dict:
    """
    Validate one track's audio. Returns a status dict. MP3-only is a draft with
    a warning; a valid WAV/FLAC master makes it distribution-ready.
    """
    mp3_ok = bool(track.get("mp3_path") and Path(track["mp3_path"]).exists())
    master = track.get("master_path")
    master_ok = bool(master and Path(master).is_file() and track.get("distribution_ready"))

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
        "warning": next(iter(track.get("warnings", [])), "배포용 트랙 원본 WAV/FLAC를 연결하세요."),
        "duration_sec": track.get("duration_sec", 0),
    }


def tracklist_distribution_ready(tracks: list[dict]) -> bool:
    """A package is distribution-ready only if EVERY track has a valid master."""
    return bool(tracks) and all(t.get("distribution_ready") for t in tracks)


# ─── Track order sync with the Video Renderer ────────────────────────────────

def order_matches_playlist(tracks: list[dict], playlist_plan: dict) -> bool:
    """True if the package track order equals the playlist's unique order."""
    entries = unique_tracks_from_plan(playlist_plan)
    if tracks and all(t.get("source_path") for t in tracks):
        return [t["source_path"] for t in tracks] == [t.get("path") for t in entries]
    plan_order = [t.get("title") or _clean_title(t.get("name", "")) for t in entries]
    pkg_order = [t["title"] for t in tracks]
    return plan_order == pkg_order


def sync_order_from_playlist(playlist_plan: dict,
                             master_overrides: dict | None = None) -> list[dict]:
    """Rebuild the tracklist in the exact playlist order (source of truth)."""
    return build_tracklist(playlist_plan, master_overrides)
