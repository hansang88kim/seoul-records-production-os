"""
services/suno_cleanup.py — 미선택 Suno 버전 정리 (v1.0.0-alpha.49).

Suno generates 2 clips per task. The user downloads ONE into the project's
songs/ folder; the sibling stays in the Suno workspace and later causes
"어떤 버전이 최종본이지?" confusion. This service finds those siblings and
(after explicit confirmation in the UI) trashes them via `suno delete`.

How the kept clip is identified (v1.0.0-alpha.68):
  * Our provider stores task_id as the comma-joined FIRST-8 chars of the
    two clip ids (e.g. "8df69261,b099c8aa").
  * PRIMARY: song["selected_clip_id"] — the full clip id
    auto_download_final_version() already records when it picks the final
    version. This is the deterministic source of truth and works
    regardless of filename.
  * FALLBACK: for songs with no selected_clip_id (downloaded before this
    field existed, or via older/manual flows), fall back to matching the
    local filename's trailing clip-id suffix — this only works for the
    OLD "{title}-{clipid8}.mp3" naming; the current "{title}_{project}.mp3"
    naming (v1.0.0-alpha.68) has no clip id in it at all, so newly
    downloaded songs always carry selected_clip_id instead.

Safety rules (plan_suno_cleanup):
  * task_id must contain ≥2 valid 8-hex clip ids — "generated"/empty skip.
  * EXACTLY ONE clip id must be identified as kept (via either method
    above). 0 matches → we can't know which version was chosen → skip.
    2 matches → both versions are in use → skip. Only the unambiguous
    sibling is ever proposed for deletion.
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
    """
    FALLBACK matcher for songs with no selected_clip_id recorded — the OLD
    suno-cli / auto-download naming was '{title-slug}-{clipid8}.ext'.
    Current downloads (v1.0.0-alpha.68: '{title}_{project}.mp3') carry no
    clip id in the filename, so this never matches them; those songs rely
    on selected_clip_id instead (see plan_suno_cleanup).
    """
    if not file_path:
        return False
    stem = Path(file_path).stem
    return stem.lower().endswith(clip_id8.lower())


def _matched_clip_ids(song: dict, clip_ids: list[str], local_file: str) -> tuple[list[str], str]:
    """
    Figure out which of `clip_ids` was kept locally for `song`.

    Returns (matched_ids, method) where method is "selected_clip_id" or
    "filename" — used only to phrase the plan entry's reason text.
    """
    selected = (song.get("selected_clip_id") or "").strip().lower()
    if selected:
        return (
            [cid for cid in clip_ids if selected.startswith(cid.lower())],
            "selected_clip_id",
        )
    return (
        [cid for cid in clip_ids if _file_matches_clip(local_file, cid)],
        "filename",
    )


def plan_suno_cleanup(project_name: str, provider=None) -> list[dict]:
    """
    Dry-run: for each song in the project, decide whether a Suno-side
    sibling can be safely deleted.

    Matching order (v1.0.0-alpha.68):
      1. selected_clip_id 매칭 — auto_download_final_version()이 기록한
         전체 클립 ID로 확정적으로 식별 (파일명 형식과 무관).
      2. 파일명 클립 ID 매칭 — selected_clip_id가 없는 예전 곡만 폴백으로
         사용('{title}-{clipid8}.mp3' 구형 다운로드명 한정).
      3. 길이 규칙 폴백 (provider 지정 시) — 위 두 방식 다 실패하면(주로
         클립 ID를 전혀 식별할 수 없는 웹 다운로드) "긴 버전 = 최종본"
         규칙으로 두 클립의 duration을 조회해 짧은 쪽을 삭제 대상으로 표시.
         길이가 같거나 조회 실패면 건너뜀.

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

        matched, method = _matched_clip_ids(song, clip_ids, local)
        if len(matched) == 1:
            entry["action"] = "delete"
            entry["keep_id"] = matched[0]
            entry["delete_ids"] = [c for c in clip_ids if c != matched[0]]
            reason_src = "selected_clip_id" if method == "selected_clip_id" else "파일명 ID"
            entry["reason"] = f"다운로드한 버전 확인됨({reason_src}) — 나머지 버전 삭제 가능"
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
            entry["reason"] = "다운로드한 버전을 식별할 수 없어 건너뜀"
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
