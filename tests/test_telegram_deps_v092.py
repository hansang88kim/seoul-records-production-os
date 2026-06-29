"""
tests/test_telegram_deps_v092.py — Telegram runtime dependency tests.

Verifies python-telegram-bot is declared and that the bot degrades clearly
when the package is missing. No real Telegram calls.
"""
from __future__ import annotations
import json
import pytest
from pathlib import Path
from unittest import mock


# ─── Declared dependency ─────────────────────────────────────────────────────

def test_requirements_include_python_telegram_bot():
    req = Path("requirements.txt").read_text(encoding="utf-8")
    assert "python-telegram-bot" in req


def test_pyproject_includes_python_telegram_bot():
    pp = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "python-telegram-bot" in pp


# ─── Runtime dependency check ────────────────────────────────────────────────

def test_telegram_runtime_dependency_check():
    import services.remote_control.security as SEC
    # Available
    with mock.patch.object(SEC, "is_telegram_package_installed", return_value=True):
        report = SEC.check_telegram_dependency()
        assert report["installed"] is True
        assert "설치" in report["message"]
    # Missing
    with mock.patch("importlib.util.find_spec", return_value=None):
        # is_telegram_package_installed uses find_spec
        assert SEC.is_telegram_package_installed() is False
        hint = SEC.telegram_install_hint()
        assert "pip install" in hint


def test_telegram_dependency_in_config_summary():
    import services.remote_control.security as SEC
    summary = SEC.public_config_summary()
    assert "telegram_package_installed" in summary


def test_telegram_bot_disabled_or_warns_when_package_missing(monkeypatch, capsys):
    """run_polling must NOT crash when the package is missing — it warns."""
    import services.remote_control.telegram_bot as TB
    import services.remote_control.security as SEC
    # Enable control (token + chat ids) so we get past the disabled check
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:FAKE")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "111")

    # Force the telegram import inside run_polling to fail
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name.startswith("telegram"):
            raise ImportError("no telegram")
        return real_import(name, *a, **k)

    with mock.patch("builtins.__import__", side_effect=fake_import):
        TB.run_polling()  # should print a hint, not raise

    out = capsys.readouterr().out
    assert "telegram" in out.lower() or "pip install" in out.lower()


def test_ui_panel_shows_telegram_package_status():
    src = Path("app/tabs/production_qa_tab.py").read_text(encoding="utf-8")
    assert "telegram_package_installed" in src
    assert "pip install -r requirements.txt" in src


# ─── Existing remote-control behavior unchanged ──────────────────────────────

def test_telegram_disabled_without_token_v092(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_ALLOWED_CHAT_IDS", raising=False)
    from services.remote_control import telegram_bot as TB
    assert TB.is_enabled() is False


def test_config_summary_still_hides_token_v092(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:SECRETFAKE")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "111,222")
    from services.remote_control import security as SEC
    summary = SEC.public_config_summary()
    assert "SECRETFAKE" not in json.dumps(summary)
    assert summary["allowed_chat_id_count"] == 2


def test_forbidden_commands_still_rejected_v092():
    from services.remote_control import command_router as ROUTER
    for cmd in ["/shell ls", "/show_env", "/cmd dir"]:
        r = ROUTER.route(cmd)
        assert r["ok"] is False


# ─── Existing features unaffected ────────────────────────────────────────────

def test_existing_supervisor_unaffected():
    from services.remote_control.supervisor import health_and_maybe_restart
    assert callable(health_and_maybe_restart)


def test_existing_music_generation_unaffected():
    from providers.ai.base import MOCK_SONGS
    assert len(MOCK_SONGS) >= 2


def test_existing_youtube_package_unaffected():
    from services.youtube.youtube_package_service import create_package
    assert callable(create_package)


def test_existing_unitedmasters_unaffected():
    from services.unitedmasters.package_service import create_package
    assert callable(create_package)
