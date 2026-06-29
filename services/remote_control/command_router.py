"""
services/remote_control/command_router.py — safe command dispatch (v0.9.1).

Maps an incoming Telegram command to a fixed, safe handler. There is NO handler
that runs an arbitrary string. Unknown/forbidden commands are rejected. Every
response is passed through redaction before returning.
"""
from __future__ import annotations

from services.remote_control import allowed_commands as AC
from services.remote_control import supervisor as SUP
from services.remote_control import process_manager as PM
from services.remote_control import health_check as HC
from services.security.redaction import redact_text


def _fmt_status() -> str:
    st = SUP.load_status()
    health = HC.check_streamlit()
    jobs = st.get("active_jobs_summary", {})
    return (
        "Seoul Records Studio Status\n"
        f"- Streamlit: {'running' if health['running'] else 'down'}\n"
        f"- URL: http://{health['host']}:{health['port']}\n"
        f"- Video render: {jobs.get('video_render', 'idle')}\n"
        f"- YouTube upload: {jobs.get('youtube_upload', 'idle')}\n"
        f"- Supervisor: {st.get('status', 'unknown')}\n"
        f"- Last check: {st.get('last_health_check_at', 'n/a')}"
    )


def _fmt_app() -> str:
    health = HC.check_streamlit()
    return (f"Streamlit: {'running' if health['running'] else 'down'}\n"
            f"HTTP: {health['http_status']}\n"
            f"URL: http://{health['host']}:{health['port']}")


def _do_restart_app() -> str:
    before = PM.find_streamlit_pids()
    result = PM.restart_streamlit()
    import time
    time.sleep(3)
    health = HC.check_streamlit()
    return (
        "Restarting Streamlit...\n"
        f"- old pid: {before[0] if before else 'none'}\n"
        f"- new pid: {result.get('new_pid', 'none')}\n"
        f"- health check: {'OK' if health['running'] else 'pending'}\n"
        f"- local URL: http://{health['host']}:{health['port']}"
    )


def _fmt_jobs() -> str:
    jobs = SUP.active_jobs_summary()
    return ("Active Jobs\n"
            f"- Video Render: {jobs.get('video_render', 'idle')}\n"
            f"- Suno: {jobs.get('suno', 'idle')}\n"
            f"- YouTube Upload: {jobs.get('youtube_upload', 'idle')}")


def _fmt_render() -> str:
    try:
        from services.video.render_job_store import _jobs_dir
        import json
        root = _jobs_dir()
        if root.exists():
            latest = sorted(root.iterdir(), key=lambda p: p.stat().st_mtime,
                            reverse=True)
            for d in latest:
                sp = d / "render_state.json"
                if sp.exists():
                    st = json.loads(sp.read_text(encoding="utf-8"))
                    return (f"최근 렌더: {st.get('status')} · "
                            f"{st.get('progress_percent', 0):.0f}%")
    except Exception:
        pass
    return "최근 영상 렌더 작업이 없습니다."


def _fmt_youtube() -> str:
    try:
        from services.youtube.upload_job_store import list_upload_jobs
        jobs = list_upload_jobs(1)
        if jobs:
            j = jobs[0]
            return (f"최근 YouTube 업로드: {j.get('status')} · "
                    f"{j.get('progress_percent', 0):.0f}%")
    except Exception:
        pass
    return "최근 YouTube 업로드 작업이 없습니다."


def _fmt_qa() -> str:
    try:
        from services.production.production_checklist import build_checklist
        cl = build_checklist()
        return f"Production 준비도: {cl['overall_readiness']}%\n{cl['next_action']}"
    except Exception:
        return "Production QA 요약을 가져올 수 없습니다."


def _fmt_tail() -> str:
    lines = SUP.tail_logs(20)
    if not lines:
        return "로그가 없습니다."
    return "최근 로그 (토큰 제거됨):\n" + "\n".join(lines)


# command → handler (each is a fixed function; NO arbitrary execution)
_HANDLERS = {
    "/status": _fmt_status,
    "/app": _fmt_app,
    "/restart_app": _do_restart_app,
    "/jobs": _fmt_jobs,
    "/render": _fmt_render,
    "/youtube": _fmt_youtube,
    "/qa": _fmt_qa,
    "/tail": _fmt_tail,
    "/help": AC.help_text,
}


def route(command: str) -> dict:
    """
    Dispatch a command. Returns {ok, response}. The response is ALWAYS redacted.
    Forbidden/unknown commands are rejected without execution.
    """
    cmd = (command or "").strip().split()[0] if command else ""

    if AC.is_forbidden(cmd):
        return {"ok": False, "response": "허용되지 않은 명령입니다.", "rejected": True}
    if AC.is_confirmation_required(cmd):
        return {"ok": False,
                "response": "이 명령은 기본 비활성화되어 있으며 별도 확인이 필요합니다.",
                "needs_confirmation": True}
    if not AC.is_allowed(cmd):
        return {"ok": False, "response": "알 수 없는 명령입니다. /help 를 입력하세요.",
                "rejected": True}

    handler = _HANDLERS.get(cmd)
    try:
        text = handler()
    except Exception:
        text = "명령 처리 중 오류가 발생했습니다."
    return {"ok": True, "response": redact_text(text)}
