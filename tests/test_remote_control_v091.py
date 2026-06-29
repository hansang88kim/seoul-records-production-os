"""
tests/test_remote_control_v091.py — Remote Control Plane + Supervisor tests.

NO real Telegram API. NO real Tailscale. NO arbitrary shell execution. The
Streamlit process control is exercised with mocked health/process calls.
"""
from __future__ import annotations
import json
import pytest
from pathlib import Path
from unittest import mock


@pytest.fixture
def rc_dir(monkeypatch, tmp_path):
    """Point supervisor + security output dirs at a temp folder."""
    import services.remote_control.supervisor as SUP
    import services.remote_control.security as SEC
    monkeypatch.setattr(SUP, "_rc_dir", lambda: tmp_path / "rc")
    monkeypatch.setattr(SEC, "_audit_path", lambda: tmp_path / "rc" / "audit.jsonl")
    (tmp_path / "rc").mkdir(parents=True, exist_ok=True)
    return tmp_path / "rc"


@pytest.fixture
def enable_telegram(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:FAKE")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "111,222")
    yield


# ─── Supervisor status + health ──────────────────────────────────────────────

def test_supervisor_status_file_created(rc_dir):
    import services.remote_control.supervisor as SUP
    with mock.patch.object(SUP.HC, "check_streamlit",
                           return_value={"running": True, "http_status": 200,
                                         "port": 8501, "host": "127.0.0.1",
                                         "port_open": True}), \
         mock.patch.object(SUP.PM, "find_streamlit_pids", return_value=[4321]):
        SUP.health_and_maybe_restart(auto_restart=False)
    assert (rc_dir / "supervisor_status.json").exists()
    status = json.loads((rc_dir / "supervisor_status.json").read_text(encoding="utf-8"))
    assert status["streamlit_running"] is True
    assert status["streamlit_pid"] == 4321


def test_health_check_detects_streamlit_down():
    import services.remote_control.health_check as HC
    with mock.patch.object(HC, "is_port_open", return_value=False):
        h = HC.check_streamlit()
        assert h["running"] is False


def test_health_check_detects_streamlit_up():
    import services.remote_control.health_check as HC
    with mock.patch.object(HC, "is_port_open", return_value=True), \
         mock.patch.object(HC, "http_status", return_value=200):
        h = HC.check_streamlit()
        assert h["running"] is True
        assert h["http_status"] == 200


# ─── Restart command + safety ────────────────────────────────────────────────

def test_restart_streamlit_command_created():
    import services.remote_control.process_manager as PM
    cmd = PM.build_start_command("python")
    assert "streamlit" in cmd
    assert "run" in cmd
    assert "app/main.py" in cmd
    assert "8501" in cmd
    assert "127.0.0.1" in cmd


def test_restart_does_not_kill_unrelated_python_process():
    """The matcher must reject worker processes and unrelated python."""
    import services.remote_control.process_manager as PM
    # Streamlit frontend → match
    assert PM._cmdline_is_target_streamlit(
        ["python", "-m", "streamlit", "run", "app/main.py"]) is True
    # Workers → NEVER match
    assert PM._cmdline_is_target_streamlit(
        ["python", "-m", "workers.video_render_worker", "abc"]) is False
    assert PM._cmdline_is_target_streamlit(
        ["python", "-m", "workers.youtube_upload_worker", "abc"]) is False
    # Unrelated python → no match
    assert PM._cmdline_is_target_streamlit(["python", "some_other.py"]) is False


def test_supervisor_restart_loop_guard(rc_dir):
    import services.remote_control.supervisor as SUP
    # Record 5 restarts → guard should block the 6th
    for _ in range(5):
        SUP._record_restart()
    assert SUP.can_restart(max_per_hour=5) is False
    assert SUP.can_restart(max_per_hour=10) is True


# ─── Telegram gating ─────────────────────────────────────────────────────────

def test_telegram_bot_disabled_without_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_ALLOWED_CHAT_IDS", raising=False)
    from services.remote_control import telegram_bot as TB
    assert TB.is_enabled() is False
    result = TB.handle_update(111, "/status")
    assert result.get("disabled") is True


def test_telegram_rejects_unknown_chat_id(rc_dir, enable_telegram):
    from services.remote_control import telegram_bot as TB
    result = TB.handle_update(999, "/status")  # not in 111,222
    assert result["ok"] is False
    assert result.get("rejected") is True
    # Rejection is audited
    audit = (rc_dir / "audit.jsonl").read_text(encoding="utf-8")
    assert "999" in audit


def test_telegram_accepts_allowed_chat_id(rc_dir, enable_telegram):
    from services.remote_control import telegram_bot as TB
    result = TB.handle_update(111, "/help")
    assert result["ok"] is True
    assert "/status" in result["response"]


# ─── Command router allow/deny ───────────────────────────────────────────────

def test_command_router_allows_status(rc_dir):
    import services.remote_control.command_router as ROUTER
    with mock.patch.object(ROUTER.HC, "check_streamlit",
                           return_value={"running": True, "http_status": 200,
                                         "port": 8501, "host": "127.0.0.1",
                                         "port_open": True}):
        r = ROUTER.route("/status")
    assert r["ok"] is True
    assert "Streamlit" in r["response"]


def test_command_router_allows_restart_app(rc_dir):
    import services.remote_control.command_router as ROUTER
    with mock.patch.object(ROUTER.PM, "find_streamlit_pids", return_value=[111]), \
         mock.patch.object(ROUTER.PM, "restart_streamlit",
                           return_value={"old_pids": [111], "new_pid": 222}), \
         mock.patch.object(ROUTER.HC, "check_streamlit",
                           return_value={"running": True, "http_status": 200,
                                         "port": 8501, "host": "127.0.0.1",
                                         "port_open": True}):
        r = ROUTER.route("/restart_app")
    assert r["ok"] is True
    assert "222" in r["response"]


def test_command_router_rejects_shell_command():
    import services.remote_control.command_router as ROUTER
    r = ROUTER.route("/shell rm -rf /")
    assert r["ok"] is False
    assert r.get("rejected") is True


def test_command_router_rejects_show_env():
    import services.remote_control.command_router as ROUTER
    r = ROUTER.route("/show_env")
    assert r["ok"] is False
    assert r.get("rejected") is True


def test_command_router_rejects_arbitrary_command():
    import services.remote_control.command_router as ROUTER
    for cmd in ["/cmd dir", "/powershell", "/exec something", "/run x"]:
        r = ROUTER.route(cmd)
        assert r["ok"] is False


# ─── Redaction ───────────────────────────────────────────────────────────────

def test_telegram_status_redacts_secrets(rc_dir):
    """Even if a secret somehow appears in a status string, it's redacted."""
    import services.remote_control.command_router as ROUTER
    with mock.patch.object(ROUTER.SUP, "load_status",
                           return_value={"status": "healthy",
                                         "active_jobs_summary": {},
                                         "last_health_check_at": "Bearer ya29.SECRETTOKEN"}), \
         mock.patch.object(ROUTER.HC, "check_streamlit",
                           return_value={"running": True, "http_status": 200,
                                         "port": 8501, "host": "127.0.0.1",
                                         "port_open": True}):
        r = ROUTER.route("/status")
    assert "ya29.SECRETTOKEN" not in r["response"]


def test_tail_logs_redacts_tokens(rc_dir):
    import services.remote_control.supervisor as SUP
    # Write a log line that contains a token — tail must redact it
    SUP.log("debug Authorization: Bearer ya29.LEAKED here")
    lines = SUP.tail_logs(20)
    blob = "\n".join(lines)
    assert "ya29.LEAKED" not in blob


def test_no_secrets_in_supervisor_status(rc_dir, enable_telegram):
    """The supervisor status file never contains the bot token or secrets."""
    import services.remote_control.supervisor as SUP
    with mock.patch.object(SUP.HC, "check_streamlit",
                           return_value={"running": True, "http_status": 200,
                                         "port": 8501, "host": "127.0.0.1",
                                         "port_open": True}), \
         mock.patch.object(SUP.PM, "find_streamlit_pids", return_value=[1]):
        SUP.health_and_maybe_restart(auto_restart=False)
    blob = (rc_dir / "supervisor_status.json").read_text(encoding="utf-8")
    assert "FAKE" not in blob       # the fake token value
    assert "TELEGRAM_BOT_TOKEN" not in blob
    assert "ya29." not in blob


def test_config_summary_hides_token(enable_telegram):
    from services.remote_control import security as SEC
    summary = SEC.public_config_summary()
    assert summary["telegram_enabled"] is True
    assert summary["allowed_chat_id_count"] == 2
    # Token never present
    assert "FAKE" not in json.dumps(summary)
    assert "123:" not in json.dumps(summary)


# ─── Windows scripts + docs exist ────────────────────────────────────────────

def test_windows_task_script_exists():
    assert Path("scripts/windows/start_studio_supervisor.ps1").exists()
    assert Path("scripts/windows/restart_streamlit.ps1").exists()


def test_install_supervisor_task_script_exists():
    p = Path("scripts/windows/install_supervisor_task.ps1")
    assert p.exists()
    assert "SeoulRecordsSupervisor" in p.read_text(encoding="utf-8")


def test_remote_control_docs_exist():
    assert Path("docs/remote_control_telegram.md").exists()
    assert Path("docs/tailscale_remote_access.md").exists()
    assert Path("docs/windows_supervisor_setup.md").exists()


def test_supervisor_worker_exists():
    assert Path("workers/studio_supervisor_worker.py").exists()


# ─── Existing features unaffected ────────────────────────────────────────────

def test_existing_music_generation_unaffected():
    from providers.ai.base import MOCK_SONGS
    assert len(MOCK_SONGS) >= 2


def test_existing_thumbnail_studio_unaffected():
    from services.thumbnail.prompt_generator import generate_flow_prompt
    assert generate_flow_prompt("korea", "n", 0)["main_prompt"]


def test_existing_video_renderer_unaffected():
    from services.video.render_plan import build_full_render_command
    assert callable(build_full_render_command)


def test_existing_youtube_package_unaffected():
    from services.youtube.youtube_package_service import create_package
    assert callable(create_package)


def test_existing_unitedmasters_unaffected():
    from services.unitedmasters.package_service import create_package
    assert callable(create_package)
