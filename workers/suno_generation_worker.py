#!/usr/bin/env python3
"""
workers/suno_generation_worker.py — Background Suno generation worker.

Runs in a SEPARATE PROCESS so Streamlit tab switches / page refreshes
do NOT interrupt generation. The UI launches this via subprocess.Popen
and polls job_state.json for progress.

Usage:
    python -m workers.suno_generation_worker <job_id>
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass


def _log(job_id: str, msg: str, level: str = "info"):
    """Append a sanitized log line."""
    from services.job_store import add_log_line
    add_log_line(job_id, msg, level)


def _update(job_id: str, **kw):
    from services.job_store import update_job
    update_job(job_id, **kw)


def run_job(job_id: str):
    """Execute all pending tracks in a job."""
    from services.job_store import load_job, update_job, complete_job, add_log_line
    from providers.suno.suno_cli_provider import SunoCliProvider
    from app.project_manager import song_project_download_dir
    from app.ui.composer_panel import DEFAULT_EXCLUDE

    state = load_job(job_id)
    if not state:
        print(f"Job {job_id} not found", file=sys.stderr)
        sys.exit(1)

    # Load plan
    plan_path = Path(PROJECT_ROOT) / "outputs" / "jobs" / job_id / "plan.json"
    if not plan_path.exists():
        _log(job_id, "plan.json not found", "error")
        complete_job(job_id, "failed")
        sys.exit(1)

    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    # Load settings
    settings_path = Path(PROJECT_ROOT) / "outputs" / "jobs" / job_id / "settings.json"
    settings = {}
    if settings_path.exists():
        settings = json.loads(settings_path.read_text(encoding="utf-8"))

    project = state.get("project", "기본")
    # v1.0.0-alpha.65: Quick Single passes its Composer-panel-edited
    # "제외 스타일" through settings.exclude_styles so those edits survive
    # the move to this shared worker. Auto Batch never sets this key, so
    # it keeps falling back to DEFAULT_EXCLUDE exactly as before.
    custom_exclude = settings.get("exclude_styles") or []
    exclude_list = [s.strip() for s in custom_exclude if s and s.strip()] or [
        s.strip() for s in DEFAULT_EXCLUDE.split(",") if s.strip()
    ]

    # Mark running
    _update(job_id,
            status="running",
            started_at=datetime.now(timezone.utc).isoformat(),
            pid=os.getpid())
    _log(job_id, f"백그라운드 Worker 시작 (PID {os.getpid()}) — {len(plan)}곡 연속 생성")
    _log(job_id, "이 Worker는 전체 배치가 끝날 때까지 계속 실행됩니다 (Streamlit과 독립)")

    # Single provider instance reused for the whole batch.
    # Note: suno.exe itself spawns a fresh Chrome per command — that's
    # suno-cli's design and is expected; the Worker process stays alive.
    provider = SunoCliProvider()
    ok = 0
    fail = 0

    for idx, draft in enumerate(plan):
        if draft.get("status") == "generated":
            ok += 1
            continue  # skip already completed

        title = draft.get("title", "제목 없음")
        style = draft.get("style", "")
        lyrics = draft.get("lyrics", "")

        _update(job_id,
                current_track_no=idx + 1,
                current_track_title=title,
                progress_percent=round(idx / len(plan) * 100))
        _log(job_id, f"Track {idx+1}/{len(plan)}: {title} 시작")

        try:
            # v1.0.0-alpha.29: no local download. dl_dir is used only as the
            # folder for prompt-snapshot / submitted-payload metadata files.
            dl_dir = song_project_download_dir(project, title)

            # Per-track vocal gender (from batch variation) overrides the default
            track_vocal = draft.get("vocal_gender") or settings.get("vocal_gender", "Female")
            options = {
                "exclude_styles": exclude_list,
                "model": settings.get("model", "v5"),
                "vocal_gender": track_vocal,
                "instrumental": settings.get("instrumental", False),
                "weirdness": settings.get("weirdness", 35),
                "style_influence": settings.get("style_influence", 70),
            }

            # Save prompt snapshot (canonical)
            track_dir = dl_dir / f"track_{idx}"
            try:
                from services.metadata_consistency_service import create_prompt_snapshot
                create_prompt_snapshot(
                    track_dir, title=title, style=style, lyrics=lyrics,
                    settings=options, ai_provider=draft.get("ai_provider", ""),
                )
            except Exception:
                pass

            # Save submitted payload (what actually gets sent to Suno)
            try:
                from services.metadata_consistency_service import (
                    compute_prompt_hash, sanitize_command, redact_sensitive,
                )
                from providers.suno.suno_cli_provider import _split_style_and_excludes
                clean_style, _ = _split_style_and_excludes(style)
                payload = {
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                    "provider": "suno_cli",
                    "title_sent": title,
                    "tags_sent": clean_style,
                    "lyrics_text_hash": compute_prompt_hash(title, style, lyrics),
                    "exclude_sent": options.get("exclude_styles", []),
                    "model_sent": options.get("model", "v5"),
                    "vocal_sent": options.get("vocal_gender", "Female"),
                    "weirdness_sent": options.get("weirdness", 35),
                    "style_influence_sent": options.get("style_influence", 70),
                    "download_note": "다운로드 안 함 — suno.com에서 직접 다운로드",
                    "prompt_snapshot_id": None,
                }
                (track_dir).mkdir(parents=True, exist_ok=True)
                (track_dir / "submitted_payload.json").write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except Exception:
                pass

            # Progress callback — records CAPTCHA retries to job_state
            def _on_progress(msg, attempt=1, max_attempts=10, failed=False):
                _update(job_id,
                        current_track_no=idx + 1,
                        current_track_title=title,
                        captcha_attempt=attempt,
                        captcha_max=max_attempts)
                _log(job_id, f"Track {idx+1}: {msg}", "error" if failed else "info")

            task_id = provider.create_song(title, style, lyrics, options,
                                           progress_callback=_on_progress)

            # v1.0.0-alpha.29: no local download. create_song() returning
            # without raising IS the success signal — save task_id/metadata
            # only; the user downloads the finished song from suno.com.
            try:
                response_meta = {
                    "provider": "suno_cli",
                    "provider_track_id": task_id,
                    "provider_title": title,
                    "provider_model": options.get("model", "v5"),
                    "provider_status": "submitted",
                    "download_note": "다운로드 안 함 — suno.com에서 직접 다운로드",
                    "parsed_at": datetime.now(timezone.utc).isoformat(),
                }
                (track_dir).mkdir(parents=True, exist_ok=True)
                (track_dir / "provider_response.json").write_text(
                    json.dumps(response_meta, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except Exception:
                pass

            draft["status"] = "generated"
            draft["task_id"] = task_id
            ok += 1
            _log(job_id, f"Track {idx+1}: {title} ✅ Suno 생성 완료 · task_id={task_id} "
                          f"(suno.com에서 직접 다운로드)")

            # Record in project manifest
            try:
                from app.project_manager import add_song_to_project
                add_song_to_project(project, {
                    "title": title, "status": "submitted",
                    "provider": "suno_cli", "model": options["model"],
                    "file_type": None, "file_path": "",
                    "distribution_eligible": False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "task_id": task_id,
                    "style": style, "project": project,
                    "job_id": job_id,
                })
            except Exception:
                pass

            # 자동 다운로드 훅은 제거됨 (v1.0.0-alpha.119) — 음원은 suno.com에서
            # 직접 받거나, 💿 프로젝트 관리의 ⬇️ 최종본 다운로드 버튼으로 받는다.

        except Exception as e:
            draft["status"] = "failed"
            draft["error"] = f"{type(e).__name__}: {e}"
            fail += 1
            _log(job_id, f"Track {idx+1}: {title} ❌ {e}", "error")

        # Save updated plan back
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        _update(job_id, completed_tracks=ok, failed_tracks=fail)

    # Final status
    final = "completed" if fail == 0 else ("partially_failed" if ok > 0 else "failed")
    complete_job(job_id, final)
    _update(job_id, progress_percent=100.0)
    _log(job_id, f"완료: {ok}/{len(plan)}곡 성공, {fail}곡 실패")
    print(f"Job {job_id} finished: {final} ({ok} ok, {fail} fail)")

    # ── Chain to the next QUEUED job (cue system) ────────────────────────
    # If the user queued more songs while this batch ran, start the next one.
    try:
        from services.generation_job_manager import start_next_queued_job
        next_job = start_next_queued_job()
        if next_job:
            _log(job_id, f"다음 대기 작업 시작: {next_job['job_id']}")
            print(f"Chained to next queued job: {next_job['job_id']}")
    except Exception as e:
        print(f"Failed to chain next job: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m workers.suno_generation_worker <job_id>")
        sys.exit(1)
    run_job(sys.argv[1])
