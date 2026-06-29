# Remote Control via Telegram (v0.9.1)

A small control plane lets you check the studio and restart the Streamlit
frontend from your phone via a Telegram bot — without exposing any secrets and
without any ability to run arbitrary commands.

## What it is (and isn't)

- It is a **limited server-management bot**: status, restart frontend, job
  summaries, logs.
- It is **not** a replacement for the full UI, and it can **never** run shell
  commands. There is no `/shell`, `/cmd`, `/powershell`, or `/show_env`.

## Enabling it (disabled by default)

Set two environment variables before starting the supervisor:

```
TELEGRAM_BOT_TOKEN=123456:your-bot-token
TELEGRAM_ALLOWED_CHAT_IDS=11111111,22222222
```

- `TELEGRAM_BOT_TOKEN` comes from @BotFather.
- `TELEGRAM_ALLOWED_CHAT_IDS` is a comma-separated whitelist of chat IDs that
  are allowed to issue commands. Anyone else is rejected and logged.

If either variable is missing, the bot stays **disabled**.

## Commands

- `/status` — overall status summary
- `/app` — Streamlit health
- `/restart_app` — restart the Streamlit frontend
- `/jobs` — active Suno / video render / YouTube upload jobs
- `/render` — latest video render job status
- `/youtube` — latest YouTube upload job status
- `/qa` — Production QA readiness summary
- `/tail` — last 20 sanitized supervisor/app log lines
- `/help` — command list

Disabled-by-default, confirmation-required: `/reboot_pc`, `/stop_app`.

## Security

- Only whitelisted `chat_id`s can run commands.
- Unknown `chat_id`s are rejected and written to `command_audit_log.jsonl`.
- All responses are passed through redaction — **no tokens, cookies, OAuth
  tokens, client secrets, or API keys ever appear in Telegram messages**.
- The bot token itself is read from the environment and never echoed.

## python-telegram-bot dependency

`python-telegram-bot` is included in `requirements.txt`, so the real long-poll
bot works after a normal install:

```
pip install -r requirements.txt
```

Verify:

```
python -c "import telegram; print('ok')"
```

If you prefer to keep it optional, it is also available as an extra:

```
pip install ".[remote]"
```

If the package is missing, the bot stays disabled and the Production QA remote
control panel shows **python-telegram-bot: 미설치** with an install hint — the
supervisor and all other features keep working. In tests, the handler is
exercised directly with no network calls.
