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

    Returns keys: sdk_installed, api_key_present, ready, model, install_hint,
    key_hint, key_env_vars. The API key VALUE is never included.
    """
    sdk = is_genai_installed()
    key = get_api_key() is not None
    import os
    model = os.environ.get("SEOUL_IMAGE_MODEL", DEFAULT_IMAGE_MODEL)
    return {
        "sdk_installed": sdk,
        "api_key_present": key,
        "ready": sdk and key,
        "model": model,
        "install_hint": "pip install google-genai",
        "key_hint": (
            "Get a free key at https://aistudio.google.com/apikey and set "
            "GEMINI_API_KEY (free tier: ~500 images/day on " + DEFAULT_IMAGE_MODEL + ")."
        ),
        "key_env_vars": list(_API_KEY_ENV_VARS),
    }
