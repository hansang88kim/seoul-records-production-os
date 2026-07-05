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


def check_midjourney_dependencies() -> dict:
    """Structured readiness report for Midjourney generation via Apiframe.

    Requires only `requests` (always available) + an Apiframe API key, so
    readiness == key presence. The API key VALUE is never included.
    """
    from services.thumbnail.midjourney_provider import get_apiframe_key
    key = get_apiframe_key() is not None
    return {
        "api_key_present": key,
        "ready": key,
        "model": "midjourney (Apiframe)",
        "key_hint": (
            "Enter your Apiframe API key in the left sidebar (🎨 Image Gen → "
            "Midjourney), or set APIFRAME_API_KEY. Key (v2, starts with afk_): "
            "https://apiframe.ai dashboard"
        ),
        "key_env_vars": ["APIFRAME_API_KEY"],
    }


def check_apiframe_nanobanana_dependencies() -> dict:
    """
    Structured readiness report for Nano Banana 2 via Apiframe (v1.0.0-alpha.34).
    Reuses the same APIFRAME_API_KEY already connected for Midjourney — no
    separate credential. Readiness == key presence; the key VALUE is never
    included.
    """
    from services.thumbnail.midjourney_provider import get_apiframe_key
    key = get_apiframe_key() is not None
    return {
        "api_key_present": key,
        "ready": key,
        "model": "nano-banana-2 (Apiframe)",
        "key_hint": (
            "Enter your Apiframe API key in the left sidebar (🎨 Image Gen), "
            "or set APIFRAME_API_KEY. Same key used for Midjourney — no "
            "separate credential needed. Key (v2, starts with afk_): "
            "https://apiframe.ai dashboard"
        ),
        "key_env_vars": ["APIFRAME_API_KEY"],
    }


def check_gpt_image_dependencies() -> dict:
    """
    Structured readiness report for GPT Image 2 via OpenAI (v1.0.0-alpha.35).
    Reuses the same OPENAI_API_KEY already connected for ChatGPT/lyrics — no
    separate credential. Readiness == key presence; the key VALUE is never
    included.
    """
    from services.thumbnail.openai_image_provider import get_openai_key
    key = get_openai_key() is not None
    return {
        "api_key_present": key,
        "ready": key,
        "model": "gpt-image-2 (OpenAI)",
        "key_hint": (
            "Enter your ChatGPT/OpenAI API key in the left sidebar "
            "(🤖 AI Composer), or set OPENAI_API_KEY. Same key used for "
            "lyrics/songwriting — no separate credential needed. Note: GPT "
            "Image access may require API Organization Verification in the "
            "OpenAI developer console."
        ),
        "key_env_vars": ["OPENAI_API_KEY"],
    }
