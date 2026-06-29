"""
services/youtube/dependency_check.py — Google API library availability (v0.8.3).

The real YouTube upload path needs google-api-python-client + google-auth +
google-auth-oauthlib. These are optional at runtime (mock upload works without
them), so the app checks at runtime and gives a clear install message instead
of failing silently.
"""
from __future__ import annotations

import importlib.util


# (import name, pip package) pairs required for real upload
REQUIRED_LIBS = [
    ("googleapiclient", "google-api-python-client"),
    ("google.auth", "google-auth"),
    ("google_auth_oauthlib", "google-auth-oauthlib"),
    ("google.auth.transport.requests", "google-auth-httplib2"),
]


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def missing_google_libs() -> list[str]:
    """Return the list of pip package names that are NOT importable."""
    missing = []
    for module_name, pip_name in REQUIRED_LIBS:
        if not _module_available(module_name):
            missing.append(pip_name)
    return missing


def google_libs_available() -> bool:
    """True only if every required Google library is importable."""
    return len(missing_google_libs()) == 0


def install_hint() -> str:
    """A user-facing install instruction listing what is missing."""
    missing = missing_google_libs()
    if not missing:
        return ""
    pkgs = " ".join(missing)
    return (
        "실제 YouTube 업로드를 위해 다음 라이브러리 설치가 필요합니다: "
        f"{', '.join(missing)}.\n설치: pip install {pkgs}"
    )


def oauth_install_hint() -> str:
    """A focused hint for the OAuth flow (needs google-auth-oauthlib)."""
    if _module_available("google_auth_oauthlib"):
        return ""
    return (
        "OAuth 인증에는 google-auth-oauthlib 설치가 필요합니다.\n"
        "설치: pip install google-auth-oauthlib google-auth"
    )

# ─── v0.8.3 spec API (explicit function names + module-level checks) ─────────

# Exact import targets the spec asks us to verify
_SPEC_MODULES = [
    ("googleapiclient.discovery", "google-api-python-client"),
    ("googleapiclient.http", "google-api-python-client"),
    ("google_auth_oauthlib.flow", "google-auth-oauthlib"),
    ("google.oauth2.credentials", "google-auth"),
    ("google.auth.transport.requests", "google-auth-httplib2"),
]


def get_missing_youtube_api_dependencies() -> list[str]:
    """Return the unique pip package names whose modules are not importable."""
    missing = []
    for module_name, pip_name in _SPEC_MODULES:
        if not _module_available(module_name) and pip_name not in missing:
            missing.append(pip_name)
    return missing


def is_real_youtube_upload_available() -> bool:
    """True only if every module needed for a real upload is importable."""
    return len(get_missing_youtube_api_dependencies()) == 0


def check_youtube_api_dependencies() -> dict:
    """
    Structured dependency report for the UI / worker.
    {
      "available": bool,
      "missing": [pip names],
      "message": str,
    }
    """
    missing = get_missing_youtube_api_dependencies()
    available = len(missing) == 0
    if available:
        message = "YouTube API dependencies 설치됨 — 실제 업로드 가능"
    else:
        message = (
            "실제 YouTube 업로드를 위해 Google API dependencies 설치가 필요합니다. "
            "pip install -r requirements.txt 실행 후 다시 시도하세요. "
            f"(누락: {', '.join(missing)})"
        )
    return {"available": available, "missing": missing, "message": message}
