"""
workers/thumbnail_generation_worker.py — background worker process for
Thumbnail Studio batch image generation (v1.0.0-alpha.38).

Launched as a detached subprocess by services/thumbnail_job_manager.py
(python -m workers.thumbnail_generation_worker <job_id>). Reads the job's
plan.json (list of prompts, from prompt_generator.generate_prompt_batch) and
settings.json (session_id, use_real, model, engine), then calls
session_store.generate_images() ONCE for the whole batch with a
progress_callback that updates job_store after each image — so the UI can
poll live progress without blocking on the (potentially minutes-long, real-
API) generation itself.

Mirrors workers/suno_generation_worker.py's shape (job lifecycle, logging,
crash-safety) but is much simpler: there's no per-track retry/queue-chaining
logic here (see thumbnail_job_manager's docstring on why concurrent jobs are
simply queued rather than auto-chained).
"""
from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services import job_store  # noqa: E402
from services.thumbnail import session_store as ss  # noqa: E402


def _log(job_id: str, message: str, level: str = "info"):
    try:
        job_store.add_log_line(job_id, message, level)
    except Exception:
        pass


def main(job_id: str):
    job = job_store.load_job(job_id)
    if not job:
        return

    jobs_dir = job_store._jobs_dir() / job_id
    plan_path = jobs_dir / "plan.json"
    settings_path = jobs_dir / "settings.json"

    try:
        prompts = json.loads(plan_path.read_text(encoding="utf-8"))
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception as e:
        job_store.update_job(job_id, status="failed",
                             last_message=f"작업 설정을 읽을 수 없음: {e}")
        _log(job_id, f"plan/settings load failed: {e}", "error")
        return

    session_id = settings.get("session_id")
    use_real = settings.get("use_real", False)
    model = settings.get("model")
    engine = settings.get("engine", "gemini")
    append = bool(settings.get("append", False))  # v1.0.0-alpha.89: 이미지 추가 생성
    total = len(prompts)

    _log(job_id, f"썸네일 생성 시작: {total}장 · engine={engine} · use_real={use_real}")
    job_store.update_job(job_id, status="running", current_track_no=0,
                         last_message=f"이미지 생성 중 (0/{total})")

    counters = {"completed": 0, "failed": 0}

    def _on_progress(index: int, total_n: int, candidate: dict):
        pct = round(((index + 1) / max(1, total_n)) * 100, 1)
        ok = candidate.get("status") == "image_generated"
        if ok:
            counters["completed"] += 1
        else:
            counters["failed"] += 1
        icon = "✅" if ok else "⚠️"
        job_store.update_job(
            job_id,
            current_track_no=index + 1,
            completed_tracks=counters["completed"],
            failed_tracks=counters["failed"],
            progress_percent=pct,
            current_track_title=candidate.get("candidate_id", ""),
            last_message=f"이미지 생성 중 ({index + 1}/{total_n})",
        )
        _log(job_id, f"{icon} {candidate.get('candidate_id', '?')} "
                     f"({index + 1}/{total_n})" +
                     ("" if ok else f" — {candidate.get('gen_error', '')}"))

    try:
        if append:
            # Append N MORE to the session (existing candidates untouched).
            new_cands = ss.append_and_generate_images(
                session_id, prompts, use_real=use_real, model=model, engine=engine,
                progress_callback=_on_progress)
            # count only the newly-added ones for this job's success tally
            cands = new_cands[-len(prompts):] if len(new_cands) >= len(prompts) else new_cands
        else:
            cands = ss.generate_images(session_id, prompts, use_real=use_real,
                                       model=model, engine=engine,
                                       progress_callback=_on_progress)
    except Exception as e:
        job_store.update_job(job_id, status="failed",
                             last_message=f"생성 중 오류: {e}")
        _log(job_id, f"generate_images crashed: {e}\n{traceback.format_exc()}", "error")
        _chain_next()
        return

    ok_count = sum(1 for c in cands if c.get("status") == "image_generated")
    fail_count = len(cands) - ok_count
    final_status = "completed" if fail_count == 0 else (
        "partially_failed" if ok_count > 0 else "failed"
    )
    job_store.complete_job(job_id, final_status)
    job_store.update_job(
        job_id,
        last_message=f"완료: {ok_count}/{len(cands)}장 생성 성공",
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
    _log(job_id, f"썸네일 생성 종료: {ok_count}/{len(cands)}장 성공 ({final_status})")
    _chain_next()


def _chain_next():
    """v1.0.0-alpha.89: when this job finishes, auto-start the next QUEUED
    thumbnail job so each generation runs as its own independent job (no
    interruption, no manual retry). Guarded to never run two at once."""
    try:
        from services.thumbnail_job_manager import start_next_queued_thumbnail_job
        started = start_next_queued_thumbnail_job()
        if started:
            _log(started["job_id"], "이전 작업 완료 → 대기열의 다음 썸네일 작업 자동 시작")
    except Exception:
        pass


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    main(sys.argv[1])
