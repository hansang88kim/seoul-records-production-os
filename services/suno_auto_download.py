"""
services/suno_auto_download.py — 최종본 자동 다운로드 (v1.0.0-alpha.52).

Rule (사용자 확정 기준, v1.0.0-alpha.52로 변경):
  1. 180s~240s 범위 안에 들어오는 버전을 우선한다.
  2. 둘 다 범위 안이면 더 긴 쪽.
  3. 둘 다 범위 밖이면 180s~240s 범위에 더 가까운 쪽
     (범위 경계까지의 거리가 짧은 쪽 — 예: 178s vs 170s → 178s,
     245s vs 250s → 245s가 240s 경계에 더 가까우므로 245s).
  4. 위 기준으로도 완전히 동일하면(길이 정확히 같음) 어느 쪽이 최종본인지
     알 수 없으므로 삭제는 하지 않는다(둘 다 유지, 다운로드는 함).

선택되지 않은 나머지 버전은 Suno에서 자동으로 삭제한다(사용자 선택 불필요).

저장 위치는 프로젝트 폴더 FLAT:
    outputs/song_projects/<프로젝트명>/songs/<제목>_<프로젝트슬러그>.mp3
    (동명 곡이 이미 있으면 <제목>_<프로젝트슬러그>_2.mp3 ... 로 번호가 붙는다 —
    v1.0.0-alpha.68, 파일명에서 클립ID를 빼는 대신 절대 덮어쓰지 않도록)
곡별 하위 폴더를 만들지 않는다 — suno-cli의 곡별 폴더 다운로드를 우회하기
위해 CLI download 대신 audio_url을 직접 스트리밍 다운로드한다.

Manifest는 file_path / duration / file_type / status 로 갱신되어
프로젝트 관리 재생 버튼·Video Renderer 라벨이 즉시 따라온다.
"""
from __future__ import annotations

import re
from pathlib import Path

from services.suno_cleanup import _task_clip_ids

_FORBIDDEN = re.compile(r'[/\\:*?"<>|]')

# 최종본 우선순위 범위 (초 단위)
_RANGE_LO = 180.0
_RANGE_HI = 240.0


def _safe_title(title: str) -> str:
    s = _FORBIDDEN.sub("_", (title or "무제").strip())
    return s[:80] or "무제"


def _unique_path(dest: Path) -> Path:
    """
    If `dest` already exists, append _2, _3, ... before the extension
    until a free name is found. A project can end up with two songs of
    the same title, and the new "{title}_{project}.mp3" naming (v1.0.0-
    alpha.68) no longer has a clip id in it to keep them apart, so we
    must never silently overwrite an existing download.
    """
    if not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    n = 2
    while True:
        candidate = dest.with_name(f"{stem}_{n}{suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def _clip_duration(info: dict) -> float:
    if not info:
        return 0.0
    d = info.get("duration")
    if d is None:
        d = (info.get("metadata") or {}).get("duration")
    try:
        return float(d or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _clip_audio_url(info: dict) -> str:
    if not info:
        return ""
    return (info.get("audio_url") or info.get("audio_url_wav")
            or info.get("wav_url") or info.get("stream_audio_url")
            or info.get("mp3_url") or info.get("download_url") or "")


def _in_range(duration: float) -> bool:
    return _RANGE_LO <= duration <= _RANGE_HI


def _distance_to_range(duration: float) -> float:
    """0 if inside [180, 240]; else the gap to the nearest boundary."""
    if duration < _RANGE_LO:
        return _RANGE_LO - duration
    if duration > _RANGE_HI:
        return duration - _RANGE_HI
    return 0.0


def _select_final_clip(cand_a: tuple, cand_b: tuple) -> tuple:
    """
    Decide which of two (clip_id, info) candidates is the "final version".

    Returns (winner, loser, is_tie):
      * winner/loser are (clip_id, info) tuples.
      * is_tie is True only when the two durations are EXACTLY equal —
        the only case where we truly cannot tell them apart. In that case
        `winner` is chosen arbitrarily (cand_a) for download purposes, but
        callers must NOT delete `loser` on Suno when is_tie is True.
    """
    id_a, info_a = cand_a
    id_b, info_b = cand_b
    d_a, d_b = _clip_duration(info_a), _clip_duration(info_b)

    if d_a == d_b:
        return cand_a, cand_b, True

    in_a, in_b = _in_range(d_a), _in_range(d_b)

    # Rule 1: exactly one is inside the 180-240s range — it wins outright.
    if in_a != in_b:
        return (cand_a, cand_b, False) if in_a else (cand_b, cand_a, False)

    # Rule 2: both inside the range — the longer one wins.
    if in_a and in_b:
        return (cand_a, cand_b, False) if d_a > d_b else (cand_b, cand_a, False)

    # Rule 3: neither inside the range — whichever is closer to it wins.
    dist_a, dist_b = _distance_to_range(d_a), _distance_to_range(d_b)
    if dist_a == dist_b:
        # Equally close but different durations (symmetric around a
        # boundary) — decisive tie-break: prefer the longer one. This is
        # NOT the "can't tell apart" tie (durations differ), so deletion
        # of the loser still proceeds normally.
        return (cand_a, cand_b, False) if d_a > d_b else (cand_b, cand_a, False)
    return (cand_a, cand_b, False) if dist_a < dist_b else (cand_b, cand_a, False)


def _http_download(url: str, dest: Path) -> bool:
    """Stream an audio URL to disk. Returns True on success."""
    import requests
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with requests.get(url, stream=True, timeout=180) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        f.write(chunk)
        tmp.replace(dest)
        return True
    except Exception:
        tmp.unlink(missing_ok=True)
        return False


def auto_download_final_version(project_name: str, provider=None,
                                delete_other: bool = True,
                                downloader=None) -> dict:
    """
    For every song in the project that has 2 recorded clip ids and no
    local audio yet: pick the "final version" per the 180-240s priority
    rule (see module docstring), download it flat into the project's
    songs/ folder, and (optionally) trash the other clip on Suno.

    provider / downloader are injectable for tests.
    Returns {"downloaded": [...], "deleted": [...], "skipped": [...],
             "failed": [...]} — every entry carries the song title AND a
             "reason"/"error" string so callers can surface WHY nothing
             happened instead of failing silently.
    """
    from app.project_manager import (
        get_song_project_songs, find_song_file, song_project_dir,
        update_song_in_project, _song_slug,
    )

    if provider is None:
        from providers.suno.suno_cli_provider import SunoCliProvider
        provider = SunoCliProvider()
    dl = downloader or _http_download

    report = {"downloaded": [], "deleted": [], "skipped": [], "failed": []}

    for song in get_song_project_songs(project_name):
        title = song.get("title", "제목 없음")
        clip_ids = _task_clip_ids(song.get("task_id", "") or "")

        if len(clip_ids) < 2:
            report["skipped"].append(
                {"title": title, "reason": "클립 ID 2개 미기록 — 자동 처리 불가"})
            continue
        if find_song_file(project_name, song):
            report["skipped"].append(
                {"title": title, "reason": "이미 로컬 파일 있음 — 🧹 Suno 정리에서 처리"})
            continue

        # 설계상 곡당 클립은 2개 — 그 이상 기록된 경우는 앞의 2개만 사용.
        pair = clip_ids[:2]
        infos = [(cid, provider.get_clip_info(cid) or {}) for cid in pair]
        # 안전규칙: 모든 클립 정보가 조회돼야 비교가 유효하다 — 하나라도
        # 실패하면 남은 클립을 '정답'으로 오판할 수 있으므로 진행하지 않는다.
        if any(not info for _, info in infos):
            report["failed"].append(
                {"title": title, "reason": "일부 클립 정보 조회 실패 — 비교 불가"})
            continue

        winner, loser, is_tie = _select_final_clip(infos[0], infos[1])
        winner_id, winner_info = winner
        loser_id, loser_info = loser

        if not _clip_audio_url(winner_info):
            report["failed"].append(
                {"title": title, "reason": "오디오 URL 조회 실패", "clip_id": winner_id})
            continue
        proj_slug = song.get("project_slug") or _song_slug(project_name)
        dest = _unique_path(
            song_project_dir(project_name) / "songs"
            / f"{_safe_title(title)}_{proj_slug}.mp3"
        )

        if not dl(_clip_audio_url(winner_info), dest):
            report["failed"].append(
                {"title": title, "reason": "다운로드 실패", "clip_id": winner_id})
            continue

        update_song_in_project(project_name, song, {
            "file_path": str(dest),
            "file_type": "mp3",
            "duration": _clip_duration(winner_info) or None,
            "status": "saved",
            "selected_clip_id": winner_info.get("id") or winner_id,
        })
        report["downloaded"].append({
            "title": title, "clip_id": winner_id,
            "duration": _clip_duration(winner_info), "path": str(dest),
        })

        if not delete_other:
            continue
        # v1.0.0-alpha.95: the winner is already downloaded, so the loser is
        # DEFINITIVELY the clip we're not keeping — delete it from Suno even when
        # the two versions tie on length. (Previously a length tie skipped the
        # delete and left both clips on Suno; the user wants exactly ONE kept and
        # the other removed, always.)
        full = loser_info.get("id") or loser_id
        res = provider.delete_clips([full])
        if res.get("ok"):
            report["deleted"].append({"title": title, "clip_id": full, "tie": is_tie})
        else:
            report["failed"].append(
                {"title": title, "clip_id": full,
                 "reason": f"Suno 삭제 실패: {res.get('error')}"})
    return report


# 이전 이름 호환 — 기존 호출부/외부 스크립트가 있다면 그대로 동작한다.
auto_download_longest = auto_download_final_version
