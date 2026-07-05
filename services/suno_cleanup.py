"""
services/suno_cleanup.py — 미선택 Suno 버전 정리 (v1.0.0-alpha.49).

Suno generates 2 clips per task. The user downloads ONE into the project's
songs/ folder; the sibling stays in the Suno workspace and later causes
"어떤 버전이 최종본이지?" confusion. This service finds those siblings and
(after explicit confirmation in the UI) trashes them via `suno delete`.

Why this is deterministic:
  * Our provider stores task_id as the comma-joined FIRST-8 chars of the
    two clip ids (e.g. "8df69261,b099c8aa").
  * suno-cli downloads name files "{title-slug}-{clipid8}.mp3", so the
    kept clip is identified by matching the local filename suffix.

Safety rules (plan_suno_cleanup):
  * task_id must contain ≥2 valid 8-hex clip ids — "generated"/empty skip.
  * EXACTLY ONE clip id must match a local file. 0 matches → we can't know
    which version was chosen → skip. 2 matches → both versions are in use
    → skip. Only the unambiguous sibling is ever proposed for deletion.
  * plan (dry-run) and execute are separate steps; execute verifies each
    clip via `suno info` and uses the FULL clip id when available.
"""
from __future__ import annotations

import re
from pathlib import Path

_ID8 = re.compile(r"^[0-9a-f]{8}$", re.IGNORECASE)


def _task_clip_ids(task_id: str) -> list[str]:
    """Parse a task_id into valid 8-hex clip-id prefixes."""
    if not task_id:
        return []
    return [t.strip() for t in task_id.split(",") if _ID8.match(t.strip())]


def _file_matches_clip(file_path: str, clip_id8: str) -> bool:
    """suno-cli download names are '{title-slug}-{clipid8}.ext'."""
    if not file_path:
        return False
    stem = Path(file_path).stem
    return stem.lower().endswith(clip_id8.lower())


def plan_suno_cleanup(project_name: str, provider=None) -> list[dict]:
    """
    Dry-run: for each song in the project, decide whether a Suno-side
    sibling can be safely deleted.

    Matching order (v1.0.0-alpha.50):
      1. 파일명 클립 ID 매칭 — suno-cli 다운로드('{title}-{clipid8}.mp3')는
         확정적으로 식별.
      2. 길이 규칙 폴백 (provider 지정 시) — 파일명에 ID가 없는 웹 다운로드는
         "긴 버전 = 최종본" 규칙으로 두 클립의 duration을 조회해 짧은 쪽을
         삭제 대상으로 표시. 길이가 같거나 조회 실패면 건너뜀.

    Returns one entry per song:
      {title, task_id, action: "delete"|"skip", keep_id, delete_ids,
       local_file, reason}
    Only action == "delete" entries are ever executed.
    """
    from app.project_manager import get_song_project_songs, find_song_file

    plan = []
    for song in get_song_project_songs(project_name):
        title = song.get("title", "제목 없음")
        task_id = song.get("task_id", "") or ""
        entry = {"title": title, "task_id": task_id, "action": "skip",
                 "keep_id": None, "delete_ids": [], "local_file": "",
                 "reason": ""}

        clip_ids = _task_clip_ids(task_id)
        if len(clip_ids) < 2:
            entry["reason"] = "클립 ID 2개가 기록되지 않은 곡 (정리 불필요/불가)"
            plan.append(entry)
            continue

        local = find_song_file(project_name, song)
        entry["local_file"] = local
        if not local:
            entry["reason"] = "로컬 파일 없음 — ⬇️ 최종본 자동 다운로드를 먼저 실행하세요"
            plan.append(entry)
            continue

        matched = [cid for cid in clip_ids if _file_matches_clip(local, cid)]
        if len(matched) == 1:
            entry["action"] = "delete"
            entry["keep_id"] = matched[0]
            entry["delete_ids"] = [c for c in clip_ids if c != matched[0]]
            entry["reason"] = "다운로드한 버전 확인됨(파일명 ID) — 나머지 버전 삭제 가능"
            plan.append(entry)
            continue
        if matched:
            entry["reason"] = "두 버전 모두 로컬에 있어 건너뜀"
            plan.append(entry)
            continue

        # ── 길이 규칙 폴백: 긴 버전 = 최종본 ─────────────────────────
        if provider is not None:
            durs = []
            for cid in clip_ids:
                info = provider.get_clip_info(cid) or {}
                d = info.get("duration")
                if d is None:
                    d = (info.get("metadata") or {}).get("duration")
                try:
                    durs.append((cid, float(d or 0.0)))
                except (TypeError, ValueError):
                    durs.append((cid, 0.0))
            durs.sort(key=lambda t: t[1], reverse=True)
            if durs[0][1] > 0 and durs[0][1] > durs[1][1]:
                entry["action"] = "delete"
                entry["keep_id"] = durs[0][0]
                entry["delete_ids"] = [c for c, _ in durs[1:]]
                entry["reason"] = (f"길이 규칙 적용 — 긴 버전({durs[0][1]:.0f}s) 유지, "
                                   f"짧은 버전({durs[1][1]:.0f}s) 삭제")
            else:
                entry["reason"] = "두 버전 길이 동일/조회 실패 — 건너뜀"
        else:
            entry["reason"] = "파일명에서 클립 ID를 식별할 수 없어 건너뜀"
        plan.append(entry)
    return plan


def execute_suno_cleanup(plan: list[dict], provider=None) -> dict:
    """
    Delete the sibling clips proposed by plan_suno_cleanup (action=="delete"
    entries only). Each clip is verified via `suno info` first and deleted
    by its FULL id when resolvable (8-char prefix as fallback).

    Returns {"deleted": [...], "failed": [...], "skipped": [...]}.
    """
    if provider is None:
        from providers.suno.suno_cli_provider import SunoCliProvider
        provider = SunoCliProvider()

    result = {"deleted": [], "failed": [], "skipped": []}
    for entry in plan:
        if entry.get("action") != "delete":
            result["skipped"].append(entry.get("title", "?"))
            continue
        for cid in entry.get("delete_ids", []):
            info = provider.get_clip_info(cid) or {}
            full_id = info.get("id") or cid
            res = provider.delete_clips([full_id])
            if res.get("ok"):
                result["deleted"].append(
                    {"title": entry["title"], "clip_id": full_id})
            else:
                result["failed"].append(
                    {"title": entry["title"], "clip_id": full_id,
                     "error": res.get("error", "unknown")})
    return result
