"""
workers/youtube_upload_worker.py — background YouTube private upload (v0.8.2).

Runs the upload as a separate process so Streamlit never blocks. Uploads the
video PRIVATE, then sets the thumbnail. If the thumbnail fails, the job is
marked partial_success (the video stays private). NEVER logs tokens.

Default + tests use the mock client (no network). The real client is used only
when explicitly requested AND credentials are present.

Usage: python -m workers.youtube_upload_worker <upload_job_id> [--real]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def run_upload_job(upload_job_id: str, use_mock: bool = True,
                   mock_kwargs: dict | None = None):
    from services.youtube.upload_job_store import (
        load_upload_state, update_upload_state, append_upload_log,
        append_upload_progress, save_upload_result, _job_path,
    )
    from services.youtube.youtube_api_client import get_youtube_client
    from services.youtube import token_store as ts

    state = load_upload_state(upload_job_id)
    if not state:
        print(f"No upload job {upload_job_id}")
        return

    import os as _os
    update_upload_state(upload_job_id, status="authorizing", worker_pid=_os.getpid(),
                        started_at=datetime.now(timezone.utc).isoformat(),
                        last_message="인증 확인 중")
    append_upload_log(upload_job_id, "업로드 작업 시작")

    # Load the payload snapshot
    jd = _job_path(upload_job_id)
    try:
        payload = json.loads((jd / "upload_payload_snapshot.json").read_text(encoding="utf-8"))
    except Exception:
        payload = {"snippet": {"title": state.get("title", "")},
                   "status": {"privacyStatus": "private"}}

    # Credentials (real mode only) — never logged
    credentials = ts.load_token() if not use_mock else None
    client = get_youtube_client(use_mock=use_mock, credentials=credentials,
                                **(mock_kwargs or {}))

    video_path = state.get("video_path", "")
    thumbnail_path = state.get("thumbnail_path", "")

    # ── Upload (PRIVATE) ─────────────────────────────────────────────────
    update_upload_state(upload_job_id, status="uploading", last_message="영상 업로드 중")

    def on_progress(p: dict):
        append_upload_progress(upload_job_id, p)
        update_upload_state(
            upload_job_id,
            progress_percent=float(p.get("percent", 0)),
            bytes_uploaded=int(p.get("bytes_uploaded", 0)),
            total_bytes=int(p.get("total_bytes", 0)),
            upload_speed=p.get("speed", ""),
            last_message=f"업로드 중 {p.get('percent', 0)}%",
        )

    try:
        result = client.upload_video_private(payload, video_path, progress_callback=on_progress)
    except Exception as e:
        update_upload_state(upload_job_id, status="failed",
                            completed_at=datetime.now(timezone.utc).isoformat(),
                            errors=state.get("errors", []) + ["upload exception"],
                            last_message="업로드 실패")
        append_upload_log(upload_job_id, "업로드 예외 발생", "error")
        save_upload_result(upload_job_id, {"status": "failed", "errors": ["upload exception"]})
        return

    if result.get("status") != "uploaded" or not result.get("video_id"):
        update_upload_state(upload_job_id, status="failed",
                            completed_at=datetime.now(timezone.utc).isoformat(),
                            errors=result.get("errors", ["upload failed"]),
                            last_message="업로드 실패")
        append_upload_log(upload_job_id, "업로드 실패 — video_id 없음", "error")
        save_upload_result(upload_job_id, {
            "upload_job_id": upload_job_id, "package_id": state.get("package_id"),
            "status": "failed", "video_id": None,
            "errors": result.get("errors", ["upload failed"]),
        })
        return

    video_id = result["video_id"]
    youtube_url = result.get("youtube_url", f"https://youtu.be/{video_id}")
    privacy = result.get("privacy_status", "private")
    update_upload_state(upload_job_id, video_id=video_id, youtube_url=youtube_url,
                        privacy_status=privacy, progress_percent=100.0,
                        status="thumbnail_setting", last_message="썸네일 설정 중")
    append_upload_log(upload_job_id, f"영상 업로드 완료 (private) — video_id 확보")

    # ── Thumbnail ────────────────────────────────────────────────────────
    thumb_status = "skipped"
    if thumbnail_path and Path(thumbnail_path).exists():
        thumb_result = client.set_thumbnail(video_id, thumbnail_path)
        if thumb_result.get("thumbnail_set"):
            thumb_status = "completed"
            append_upload_log(upload_job_id, "썸네일 설정 완료")
        else:
            thumb_status = "failed"
            append_upload_log(upload_job_id, "썸네일 설정 실패 — partial_success", "warning")
    else:
        append_upload_log(upload_job_id, "썸네일 파일 없음 — 설정 건너뜀", "warning")

    # ── Final status ─────────────────────────────────────────────────────
    final_status = "completed" if thumb_status in ("completed", "skipped") else "partial_success"
    update_upload_state(
        upload_job_id, status=final_status, thumbnail_set_status=thumb_status,
        completed_at=datetime.now(timezone.utc).isoformat(),
        last_message=("업로드 완료 (private)" if final_status == "completed"
                      else "업로드됨 — 썸네일 실패 (partial_success)"),
    )

    save_upload_result(upload_job_id, {
        "upload_job_id": upload_job_id,
        "package_id": state.get("package_id"),
        "status": final_status,
        "video_id": video_id,
        "youtube_url": youtube_url,
        "privacy_status": privacy,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "thumbnail_set_status": thumb_status,
        "api_response_summary": {"mock": result.get("mock", False)},
        "errors": [],
        "warnings": ([] if thumb_status != "failed" else ["thumbnail set failed"]),
    })
    append_upload_log(upload_job_id, f"작업 완료: {final_status}")


def run_thumbnail_retry(upload_job_id: str, use_mock: bool = True,
                        mock_kwargs: dict | None = None):
    """Retry ONLY the thumbnail set for a partial_success job (video stays)."""
    from services.youtube.upload_job_store import (
        load_upload_state, update_upload_state, append_upload_log, save_upload_result,
    )
    from services.youtube.youtube_api_client import get_youtube_client
    from services.youtube import token_store as ts

    state = load_upload_state(upload_job_id)
    if not state or not state.get("video_id"):
        return
    credentials = ts.load_token() if not use_mock else None
    client = get_youtube_client(use_mock=use_mock, credentials=credentials,
                                **(mock_kwargs or {}))
    video_id = state["video_id"]
    thumbnail_path = state.get("thumbnail_path", "")
    if not thumbnail_path or not Path(thumbnail_path).exists():
        append_upload_log(upload_job_id, "썸네일 재시도 실패 — 파일 없음", "error")
        return
    res = client.set_thumbnail(video_id, thumbnail_path)
    if res.get("thumbnail_set"):
        update_upload_state(upload_job_id, status="completed",
                            thumbnail_set_status="completed",
                            last_message="썸네일 재시도 성공 — 완료")
        append_upload_log(upload_job_id, "썸네일 재시도 성공")
    else:
        append_upload_log(upload_job_id, "썸네일 재시도 실패", "warning")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m workers.youtube_upload_worker <upload_job_id> [--real]")
        sys.exit(1)
    jid = sys.argv[1]
    real = "--real" in sys.argv
    run_upload_job(jid, use_mock=not real)
