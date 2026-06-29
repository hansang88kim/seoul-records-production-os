"""
workers/studio_supervisor_worker.py — supervisor + telegram entrypoint (v0.9.1).

Runs the supervisor health loop and (if enabled) the Telegram control bot in a
background thread. This process is SEPARATE from Streamlit so it keeps running
even if the frontend crashes.

Usage:
    python -m workers.studio_supervisor_worker
"""
from __future__ import annotations

import os
import time
import threading


def _interval() -> int:
    try:
        return int(os.environ.get("HEALTH_CHECK_INTERVAL_SECONDS", "30"))
    except ValueError:
        return 30


def _auto_restart() -> bool:
    return os.environ.get("AUTO_RESTART_STREAMLIT", "true").lower() != "false"


def _max_restarts() -> int:
    try:
        return int(os.environ.get("MAX_RESTARTS_PER_HOUR", "5"))
    except ValueError:
        return 5


def _run_telegram():
    from services.remote_control import telegram_bot
    if telegram_bot.is_enabled():
        telegram_bot.run_polling()


def main():
    from services.remote_control import supervisor as SUP

    SUP.log("Supervisor 시작")
    # Telegram bot in a daemon thread (only runs if enabled)
    try:
        t = threading.Thread(target=_run_telegram, daemon=True)
        t.start()
    except Exception:
        SUP.log("Telegram 스레드 시작 실패", "warning")

    interval = _interval()
    while True:
        try:
            SUP.health_and_maybe_restart(auto_restart=_auto_restart(),
                                         max_per_hour=_max_restarts())
        except Exception:
            SUP.log("supervisor tick 오류", "error")
        time.sleep(interval)


if __name__ == "__main__":
    main()
