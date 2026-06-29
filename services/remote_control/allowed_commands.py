"""
services/remote_control/allowed_commands.py — Telegram command allowlist (v0.9.1).

ONLY these commands exist. There is no shell/exec command and no way to run an
arbitrary string. Anything not in ALLOWED_COMMANDS is rejected.
"""
from __future__ import annotations


# Safe, always-available commands
ALLOWED_COMMANDS = {
    "/status": "전체 상태 요약",
    "/app": "Streamlit 상태",
    "/restart_app": "Streamlit 재시작",
    "/jobs": "활성 작업 요약 (Suno / 영상 / YouTube)",
    "/render": "최근 영상 렌더 작업 상태",
    "/youtube": "최근 YouTube 업로드 작업 상태",
    "/qa": "Production QA 준비도 요약",
    "/tail": "최근 supervisor/app 로그 20줄 (토큰 제거됨)",
    "/help": "명령어 목록",
}

# Dangerous commands — disabled by default, require 2-step confirmation.
CONFIRMATION_COMMANDS = {
    "/reboot_pc": "PC 재부팅 (기본 비활성화, 2단계 확인 필요)",
    "/stop_app": "Streamlit 중지 (확인 필요)",
}

# Explicitly forbidden — never implemented, always rejected.
FORBIDDEN_COMMANDS = {
    "/shell", "/cmd", "/powershell", "/exec", "/run",
    "/show_env", "/show_cookie", "/show_token", "/show_secret", "/env",
}


def is_allowed(command: str) -> bool:
    return command in ALLOWED_COMMANDS


def is_confirmation_required(command: str) -> bool:
    return command in CONFIRMATION_COMMANDS


def is_forbidden(command: str) -> bool:
    return command in FORBIDDEN_COMMANDS


def help_text() -> str:
    lines = ["Seoul Records Studio — 사용 가능한 명령:"]
    for cmd, desc in ALLOWED_COMMANDS.items():
        lines.append(f"{cmd} — {desc}")
    return "\n".join(lines)
