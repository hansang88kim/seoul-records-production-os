"""
app/ui/live_console.py — Live Generation Console.

Polls job_state.json and displays real-time progress, log lines,
and per-track status. Shows sanitized logs (no credentials).
"""
from __future__ import annotations

import streamlit as st
from services.job_store import load_job, list_jobs, get_active_jobs
from services.generation_job_manager import check_worker_alive


_STATUS_ICONS = {
    "queued": "⏳", "running": "🔄", "completed": "✅",
    "failed": "❌", "partially_failed": "⚠️",
    "interrupted": "🔌", "cancelled": "🚫",
}


def render_queue_panel():
    """Show queued jobs waiting to start."""
    from services.generation_job_manager import get_queued_jobs
    queued = get_queued_jobs()
    if not queued:
        return
    st.markdown("### 📋 대기열")
    st.caption("현재 작업이 끝나면 아래 순서대로 자동 생성됩니다.")
    for qi, j in enumerate(queued):
        cols = st.columns([4, 1])
        with cols[0]:
            st.write(f"**{qi+1}.** {j.get('project','?')} · {j.get('total_tracks',0)}곡 ⏳ 대기 중")
        with cols[1]:
            if st.button("취소", key=f"cancel_queue_{j['job_id']}", use_container_width=True):
                from services.job_store import update_job
                update_job(j["job_id"], status="cancelled",
                           last_message="사용자가 대기열에서 취소함")
                st.rerun()


def render_active_job_console():
    """
    Show the live console for the currently active job.
    Auto-detects the active job or uses the one from session_state.
    """
    # Show the queue first
    render_queue_panel()

    # Find active job (prefer a RUNNING one)
    active = get_active_jobs()
    running = [j for j in active if j.get("status") == "running"]
    job_id = st.session_state.get("active_job_id")

    if running:
        job_id = running[0]["job_id"]
    elif not job_id and active:
        job_id = active[0]["job_id"]

    if not job_id:
        return  # no active job

    job = load_job(job_id)
    if not job:
        return

    status = job.get("status", "unknown")
    icon = _STATUS_ICONS.get(status, "•")

    # Only show console for running/queued/interrupted jobs, or recently completed
    if status in ("running", "queued"):
        _render_live_progress(job)
    elif status == "interrupted":
        _render_interrupted(job)
    elif status == "cancelled":
        _render_cancelled(job)
    elif status in ("completed", "partially_failed", "failed"):
        _render_completed(job)


def _render_live_progress(job: dict):
    """Show live progress for a running job."""
    job_id = job["job_id"]
    total = job.get("total_tracks", 0)
    done = job.get("completed_tracks", 0)
    failed = job.get("failed_tracks", 0)
    pct = job.get("progress_percent", 0) or 0
    current = job.get("current_track_title", "")
    pid = job.get("pid")
    alive = check_worker_alive(pid)

    st.markdown("### 🔄 생성 진행 중")

    if not alive and pid:
        st.warning("⚠️ Worker 프로세스가 감지되지 않습니다. 작업이 중단되었을 수 있습니다.")

    # Progress
    st.progress(pct / 100)
    st.markdown(
        f"**✅ {done}/{total}곡 완료** · ❌ {failed}곡 실패 · "
        f"🎵 현재: **{current or '—'}**"
    )

    # CAPTCHA retry indicator
    captcha_attempt = job.get("captcha_attempt", 0)
    captcha_max = job.get("captcha_max", 10)
    if captcha_attempt and captcha_attempt > 1:
        st.warning(
            f"🔄 hCaptcha 재시도 중: **{captcha_attempt}/{captcha_max}회** "
            f"— suno.com의 hCaptcha 로딩이 불안정해 자동 재시도하고 있습니다 "
            f"(최대 {captcha_max}회). 잠시만 기다려 주세요."
        )
    elif captcha_attempt == 1:
        st.info("🎵 Suno 생성 시도 중 — hCaptcha 자동 해결을 진행하고 있습니다.")

    st.caption(f"Job ID: {job_id} · PID: {pid or '—'} · {'🟢 실행 중' if alive else '⚪ 확인 필요'}")

    # Stop / Restart controls
    ctrl1, ctrl2, ctrl3 = st.columns(3)
    with ctrl1:
        if st.button("⏹️ 중단", key=f"stop_{job_id}", use_container_width=True,
                     help="현재 생성을 중단합니다 (완료된 곡은 보관)"):
            from services.generation_job_manager import stop_job
            stop_job(job_id)
            st.rerun()
    with ctrl2:
        if st.button("🔄 새로고침", key="refresh_console", use_container_width=True):
            st.rerun()
    with ctrl3:
        st.write("")  # spacer

    # Log lines
    logs = job.get("log_lines", [])
    if logs:
        with st.expander(f"📋 생성 로그 (최근 {len(logs)}줄)", expanded=True):
            for entry in logs[-20:]:  # show last 20
                level = entry.get("level", "info")
                msg = entry.get("msg", "")
                ts = entry.get("ts", "")[:19].replace("T", " ")
                prefix = "❌ " if level == "error" else ""
                st.text(f"{ts}  {prefix}{msg}")

    st.caption("💡 탭을 전환하거나 새로고침해도 생성이 계속됩니다.")


def _render_interrupted(job: dict):
    """Show recovery options for an interrupted job."""
    st.markdown("### 🔌 작업 중단됨")
    st.warning(job.get("last_message", "작업이 중단되었습니다."))

    done = job.get("completed_tracks", 0)
    total = job.get("total_tracks", 0)
    failed = job.get("failed_tracks", 0)

    st.write(f"✅ {done}곡 완료 · ❌ {failed}곡 실패 · 📝 {total - done - failed}곡 미완료")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 실패/미완료 곡만 재시도", use_container_width=True, key="retry_interrupted"):
            from services.generation_job_manager import retry_failed_tracks
            result = retry_failed_tracks(job["job_id"])
            if result and not result.get("error"):
                st.session_state["active_job_id"] = result["job_id"]
                st.success("🚀 재시도 시작!")
                st.rerun()
    with col2:
        if st.button("✓ 완료로 표시", use_container_width=True, key="mark_done"):
            from services.job_store import update_job
            update_job(job["job_id"], status="partially_failed")
            st.session_state.pop("active_job_id", None)
            st.rerun()


def _render_cancelled(job: dict):
    """Show restart option for a cancelled job."""
    st.markdown("### 🚫 생성 중단됨")
    done = job.get("completed_tracks", 0)
    total = job.get("total_tracks", 0)
    failed = job.get("failed_tracks", 0)
    st.warning(f"사용자가 중단했습니다. ✅ {done}곡 완료 · 📝 {total - done - failed}곡 미완료")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ 재시작 (미완료 곡만)", use_container_width=True, key=f"restart_{job['job_id']}"):
            from services.generation_job_manager import restart_job
            result = restart_job(job["job_id"])
            if result and not result.get("error"):
                st.session_state["active_job_id"] = result["job_id"]
                st.success("▶️ 재시작!")
                st.rerun()
            elif result and result.get("queued"):
                st.info("📋 대기열에 추가됨 (다른 작업 진행 중)")
                st.rerun()
            else:
                st.warning("재시작할 미완료 곡이 없습니다.")
    with col2:
        if st.button("✓ 닫기", use_container_width=True, key=f"close_cancelled_{job['job_id']}"):
            st.session_state.pop("active_job_id", None)
            st.rerun()


def _render_completed(job: dict):
    """Show summary for a completed job."""
    status = job.get("status", "")
    icon = _STATUS_ICONS.get(status, "•")
    done = job.get("completed_tracks", 0)
    total = job.get("total_tracks", 0)
    failed = job.get("failed_tracks", 0)

    if status == "completed":
        st.success(f"{icon} 생성 완료: {done}/{total}곡 성공")
    elif status == "partially_failed":
        st.warning(f"{icon} 부분 완료: {done}/{total}곡 성공, {failed}곡 실패")
        if st.button("🔄 실패 곡만 재시도", key="retry_partial"):
            from services.generation_job_manager import retry_failed_tracks
            result = retry_failed_tracks(job["job_id"])
            if result and not result.get("error"):
                st.session_state["active_job_id"] = result["job_id"]
                st.rerun()
    else:
        st.error(f"{icon} 생성 실패")

    # Show log
    logs = job.get("log_lines", [])
    if logs:
        with st.expander(f"📋 생성 로그 ({len(logs)}줄)", expanded=False):
            for entry in logs[-20:]:
                level = entry.get("level", "info")
                msg = entry.get("msg", "")
                prefix = "❌ " if level == "error" else ""
                st.text(f"{prefix}{msg}")

    # Clear active job from display
    if st.button("✓ 확인", key="clear_job"):
        st.session_state.pop("active_job_id", None)
        st.rerun()


def render_job_history():
    """Show recent job history."""
    jobs = list_jobs(limit=10)
    if not jobs:
        st.caption("작업 이력이 없습니다.")
        return

    st.markdown("**📋 작업 이력**")
    for j in jobs:
        icon = _STATUS_ICONS.get(j.get("status", ""), "•")
        project = j.get("project", "?")
        done = j.get("completed_tracks", 0)
        total = j.get("total_tracks", 0)
        created = (j.get("created_at", ""))[:16].replace("T", " ")
        st.caption(f"{icon} {project} · {done}/{total}곡 · {created}")
