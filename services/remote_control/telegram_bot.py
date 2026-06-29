"""
services/remote_control/telegram_bot.py — Telegram control bot (v0.9.1).

Thin wrapper that:
  - is DISABLED unless TELEGRAM_BOT_TOKEN + TELEGRAM_ALLOWED_CHAT_IDS are set,
  - rejects any chat_id not on the whitelist (and audits it),
  - dispatches allowed commands through the command_router,
  - never echoes secrets (responses are redacted by the router).

The actual long-poll loop uses python-telegram-bot if available; in tests the
pure handler `handle_update()` is exercised directly with no network.
"""
from __future__ import annotations

from services.remote_control import security as SEC
from services.remote_control import command_router as ROUTER


def is_enabled() -> bool:
    return SEC.is_control_enabled()


def handle_update(chat_id, text: str) -> dict:
    """
    Process one incoming message. Returns {ok, response, ...}. Pure function —
    no network. Enforces the chat_id whitelist and audits every attempt.
    """
    if not SEC.is_control_enabled():
        return {"ok": False, "response": "원격 제어가 비활성화되어 있습니다.",
                "disabled": True}

    if not SEC.is_chat_allowed(chat_id):
        SEC.audit(chat_id, text, allowed=False, note="unknown chat_id rejected")
        return {"ok": False, "response": "권한이 없습니다.", "rejected": True}

    result = ROUTER.route(text)
    SEC.audit(chat_id, text, allowed=result.get("ok", False),
              note="rejected" if result.get("rejected") else "")
    return result


def run_polling():
    """
    Start the real Telegram long-poll loop. Only used outside tests. Requires
    python-telegram-bot; degrades clearly if missing.
    """
    if not SEC.is_control_enabled():
        print("Telegram control disabled (set TELEGRAM_BOT_TOKEN + "
              "TELEGRAM_ALLOWED_CHAT_IDS).")
        return
    try:
        from telegram.ext import Application, MessageHandler, filters
    except Exception:
        from services.remote_control.security import telegram_install_hint
        print(telegram_install_hint() or
              "python-telegram-bot 미설치 — pip install -r requirements.txt")
        return

    token = SEC.get_bot_token()
    app = Application.builder().token(token).build()

    async def _on_message(update, context):
        chat_id = update.effective_chat.id if update.effective_chat else None
        text = update.message.text if update.message else ""
        result = handle_update(chat_id, text)
        await update.message.reply_text(result["response"])

    app.add_handler(MessageHandler(filters.TEXT, _on_message))
    app.run_polling()
