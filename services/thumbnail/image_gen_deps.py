"""
services/thumbnail/image_gen_deps.py — runtime check for real image generation.

Mirrors the YouTube/Telegram dependency-check pattern: the UI uses this to decide
whether the "generate real images" path is available, and to show a clear install
/ setup hint instead of failing silently. Never exposes the API key value.
"""
from __future__ import annotations

from services.thumbnail.image_provider import (
    DEFAULT_IMAGE_MODEL,
    get_api_key,
    _API_KEY_ENV_VARS,
)


def is_genai_installed() -> bool:
    try:
        import google.genai  # noqa: F401
        return True
    except Exception:
        return False


def check_image_gen_dependencies() -> dict:
    """Structured readiness report for real (Gemini/Nano Banana) image generation.

    The default REST backend needs only `requests` (always available), so
    readiness depends on an API key alone. The google-genai SDK is optional and
    only required for the SDK backend / Imagen models. The API key VALUE is never
    included.
    """
    sdk = is_genai_installed()
    key = get_api_key() is not None
    import os
    model = os.environ.get("SEOUL_IMAGE_MODEL", DEFAULT_IMAGE_MODEL)
    backend = os.environ.get("SEOUL_IMAGE_BACKEND", "rest").strip().lower()
    # REST works with just a key; SDK backend additionally needs google-genai.
    ready = key and (backend != "sdk" or sdk)
    return {
        "sdk_installed": sdk,
        "api_key_present": key,
        "ready": ready,
        "backend": backend,
        "model": model,
        "install_hint": "pip install google-genai (only for SDK backend / Imagen)",
        "key_hint": (
            "Enter your Gemini API key in the left sidebar (🤖 AI Composer → Gemini), "
            "or set GOOGLE_GEMINI_API_KEY. Free key: https://aistudio.google.com/apikey"
        ),
        "key_env_vars": list(_API_KEY_ENV_VARS),
    }
