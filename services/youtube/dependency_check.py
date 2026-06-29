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
