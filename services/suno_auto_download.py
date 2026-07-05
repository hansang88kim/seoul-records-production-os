"""
services/suno_auto_download.py — 최종본 자동 다운로드 (v1.0.0-alpha.50).

Rule (사용자 확정 기준): Suno가 만든 2개 버전 중 **길이가 더 긴 쪽이 최종본**.
선택 과정 없이:
  1. 두 클립의 duration을 `suno info`로 조회 → 더 긴 클립의 audio_url을
     HTTP로 직접 스트리밍 다운로드.
  2. 저장 위치는 프로젝트 폴더 FLAT:
         outputs/song_projects/<프로젝트명>/songs/<제목>-<clipid8>.mp3
     — 곡별 하위 폴더를 절대 만들지 않는다 (suno-cli의 곡별 폴더 다운로드를
     우회하기 위해 CLI download 대신 audio_url 직접 다운로드를 쓴다).
  3. delete_shorter=True(기본)면 짧은 버전을 Suno 휴지통으로 이동 —
     동일한 길이 규칙이므로 사용자 선택이 필요 없다.

Manifest는 file_path / duration / file_type / status 로 갱신되어
프로젝트 관리 재생 버튼·Video Renderer 라벨이 즉시 따라온다.
"""
from __future__ import annotations

import re
from pathlib import Path

from services.suno_cleanup import _task_clip_ids

_FORBIDDEN = re.compile(r'[/\\:*?"<>|]')


def _safe_title(title: str) -> str:
    s = _FORBIDDEN.sub("_", (title or "무제").strip())
    return s[:80] or "무제"


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
            or info.get("wav_url") or "")


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


def auto_download_longest(project_name: str, provider=None,
                          delete_shorter: bool = True,
                          downloader=None) -> dict:
    """
    For every song in the project that has 2 recorded clip ids and no
    local audio yet: download the LONGER clip flat into the project's
    songs/ folder and (optionally) trash the shorter sibling on Suno.

    provider / downloader are injectable for tests.
    Returns {"downloaded": [...], "deleted": [...], "skipped": [...],
             "failed": [...]} — every entry carries the song title.
    """
    from app.project_manager import (
        get_song_project_songs, find_song_file, song_project_dir,
        update_song_in_project,
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

        infos = [(cid, provider.get_clip_info(cid) or {}) for cid in clip_ids]
        # 안전규칙: 모든 클립 정보가 조회돼야 길이 비교가 유효하다 — 하나라도
        # 실패하면 남은 클립을 '긴 쪽'으로 오판할 수 있으므로 진행하지 않는다.
        if any(not info for _, info in infos):
            report["failed"].append(
                {"title": title, "reason": "일부 클립 정보 조회 실패 — 길이 비교 불가"})
            continue

        # 길이 규칙: 더 긴 클립이 최종본
        ranked = sorted(infos, key=lambda t: _clip_duration(t[1]), reverse=True)
        winner_id, winner = ranked[0]
        is_tie = (len(ranked) > 1 and
                  _clip_duration(ranked[0][1]) == _clip_duration(ranked[1][1]))
        if not _clip_audio_url(winner):
            report["failed"].append(
                {"title": title, "reason": "오디오 URL 조회 실패", "clip_id": winner_id})
            continue
        dest = (song_project_dir(project_name) / "songs"
                / f"{_safe_title(title)}-{winner_id}.mp3")

        if not dl(_clip_audio_url(winner), dest):
            report["failed"].append(
                {"title": title, "reason": "다운로드 실패", "clip_id": winner_id})
            continue

        update_song_in_project(project_name, song, {
            "file_path": str(dest),
            "file_type": "mp3",
            "duration": _clip_duration(winner) or None,
            "status": "saved",
            "selected_clip_id": winner.get("id") or winner_id,
        })
        report["downloaded"].append({
            "title": title, "clip_id": winner_id,
            "duration": _clip_duration(winner), "path": str(dest),
        })

        if delete_shorter and is_tie:
            report["skipped"].append(
                {"title": title,
                 "reason": "두 버전 길이 동일 — 다운로드만 하고 Suno 삭제는 건너뜀"})
        elif delete_shorter:
            for cid, info in infos:
                if cid == winner_id:
                    continue
                full = (info or {}).get("id") or cid
                res = provider.delete_clips([full])
                if res.get("ok"):
                    report["deleted"].append({"title": title, "clip_id": full})
                else:
                    report["failed"].append(
                        {"title": title, "clip_id": full,
                         "reason": f"Suno 삭제 실패: {res.get('error')}"})
    return report
