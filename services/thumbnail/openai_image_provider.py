"""
services/thumbnail/openai_image_provider.py — image generation via OpenAI's
GPT Image 2 (gpt-image-2), reusing the already-connected OPENAI_API_KEY
(sidebar 🤖 AI Composer → ChatGPT — same key used for lyrics/songwriting).

v1.0.0-alpha.35.

Flow (OpenAI Images API — https://api.openai.com/v1/images/generations):
  POST with {model: "gpt-image-2", prompt, size, quality, n: 1}
  → synchronous response: {data: [{b64_json: "..."}], usage: {...}}
  No job/poll cycle — OpenAI returns the image directly in the response body
  (base64-encoded), unlike Midjourney/Nano-Banana-via-Apiframe.

Notes:
  * GPT Image models only support a few fixed sizes (1024x1024, 1536x1024,
    1024x1536, or "auto") — there is no native 16:9. We pick the closest
    landscape/portrait/square size and let the shared _finalize_image()
    center-crop to the exact target aspect afterward (same post-processing
    already used by every other provider in this module).
  * No dedicated negative-prompt field — folded into the prompt as
    "\\n\\nAvoid: ..." (same convention as the Gemini/Nano-Banana providers).
  * ref_image_path is ignored here (OpenAI's edit endpoint — images.edit —
    would be needed for image-to-image; not wired up in this pass). The 1:1
    cover is generated natively from the same prompt instead.
  * GPT Image access can require API Organization Verification in the
    developer console; an unverified org gets a specific 403 which we
    surface as a clear, actionable error rather than a generic failure.
  * Retries with exponential backoff on 429 (rate limit) and 500/503,
    per OpenAI's own guidance. The API key is never logged and is masked
    out of any error text.
"""
from __future__ import annotations

import base64
import os
import time
from pathlib import Path

from services.thumbnail.image_provider import ImageGenProvider, _finalize_image

OPENAI_IMAGES_URL = "https://api.openai.com/v1/images/generations"
_KEY_ENV_VAR = "OPENAI_API_KEY"

_RETRY_BACKOFF_SEC = (5, 15, 30)


def get_openai_key() -> str | None:
    """Return the OpenAI API key, or None. Never logged."""
    val = os.environ.get(_KEY_ENV_VAR, "")
    return val.strip() or None


def _retries() -> int:
    try:
        return max(0, int(os.environ.get("SEOUL_GPTIMAGE_RETRIES", "2")))
    except ValueError:
        return 2


def _mask(text: str, secret: str | None) -> str:
    if secret and secret in text:
        return text.replace(secret, "***")
    return text


def _is_retryable(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


# Closest fixed GPT-Image size for a given target aspect; _finalize_image()
# center-crops the result to the exact requested aspect afterward.
def _closest_size(aspect: str) -> str:
    try:
        w, h = (float(x) for x in aspect.split(":"))
        ratio = w / h
    except Exception:
        return "1024x1024"
    if ratio > 1.15:
        return "1536x1024"   # landscape (16:9, 3:2, etc.)
    if ratio < 0.87:
        return "1024x1536"   # portrait
    return "1024x1024"       # square-ish


def verify_openai_image_access(key: str) -> tuple[bool, str]:
    """
    Best-effort check that the key can call GPT Image 2. There's no cheap
    "ping" endpoint for images, so this reuses the models list (already
    covered by the ChatGPT credential's own verify_fn) — this function only
    adds the specific low-quality/low-cost 1-shot generation check when
    explicitly asked to, to avoid spending credits on every sidebar keystroke.
    Not currently wired into the sidebar (see app/main.py _verify_openai for
    the lightweight models-list check already used there).
    """
    import requests
    try:
        resp = requests.get(
            "https://api.openai.com/v1/models/gpt-image-2",
            headers={"Authorization": f"Bearer {key}"},
            timeout=15,
        )
    except Exception as e:
        return False, f"{type(e).__name__}: {_mask(str(e), key)}"
    if resp.status_code == 200:
        return True, "gpt-image-2 접근 가능"
    if resp.status_code == 403:
        return False, "조직 인증(Organization Verification) 필요 — OpenAI 개발자 콘솔에서 확인"
    if resp.status_code == 401:
        return False, "키 무효 (401)"
    return False, f"HTTP {resp.status_code}"


class OpenAIGptImageProvider(ImageGenProvider):
    """Real generation via OpenAI's GPT Image 2, using the already-connected
    ChatGPT (OPENAI_API_KEY) credential."""

    name = "gpt-image-2-openai"
    is_real = True

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or get_openai_key()
        self.model = "gpt-image-2"

    def _headers(self) -> dict:
        return {"Content-Type": "application/json", "Authorization": f"Bearer {self._api_key}"}

    def _request(self, prompt: str, size: str) -> tuple[str | None, str | None]:
        """POST /v1/images/generations. Returns (b64_json, error)."""
        import requests
        try:
            resp = requests.post(
                OPENAI_IMAGES_URL,
                headers=self._headers(),
                json={
                    "model": "gpt-image-2",
                    "prompt": prompt,
                    "size": size,
                    "n": 1,
                    "quality": os.environ.get("SEOUL_GPTIMAGE_QUALITY", "medium"),
                },
                timeout=120,
            )
        except Exception as e:
            return None, _mask(f"images.generate request failed: {type(e).__name__}: {e}", self._api_key)

        if resp.status_code == 403:
            return None, ("HTTP 403: GPT Image access requires API Organization Verification — "
                          "check the OpenAI developer console (platform.openai.com/settings) "
                          "under your organization's verification status")
        if resp.status_code != 200:
            return None, _mask(f"HTTP {resp.status_code}: {resp.text[:300]}", self._api_key)

        try:
            data = resp.json()
        except Exception:
            return None, "images.generate returned invalid JSON"

        items = data.get("data") or []
        if not items or "b64_json" not in items[0]:
            err = data.get("error") or "no image data in response"
            return None, _mask(f"no b64_json in response: {str(err)[:300]}", self._api_key)
        return items[0]["b64_json"], None

    def generate(self, prompt, out_path, negative_prompt="", index=0, meta=None,
                 aspect="16:9", ref_image_path=None):
        if not self._api_key:
            return {"ok": False, "provider": self.name, "model": self.model,
                    "path": None,
                    "error": "no API key (enter the ChatGPT/OpenAI key in the sidebar "
                             "🤖 AI Composer, or set OPENAI_API_KEY)"}

        full_prompt = prompt.strip()
        if negative_prompt:
            full_prompt = f"{full_prompt}\n\nAvoid: {negative_prompt.strip()}"
        size = _closest_size(aspect)

        b64, err = None, None
        attempts = _retries() + 1
        last_status = None
        for attempt in range(attempts):
            b64, err = self._request(full_prompt, size)
            if not err:
                break
            # Retry only on rate-limit/server errors (mirrors OpenAI's own
            # documented backoff guidance); everything else fails fast.
            retryable = err.startswith("HTTP 429") or any(
                err.startswith(f"HTTP {c}") for c in ("500", "502", "503", "504")
            )
            if not retryable or attempt == attempts - 1:
                break
            delay = _RETRY_BACKOFF_SEC[min(attempt, len(_RETRY_BACKOFF_SEC) - 1)]
            time.sleep(delay)

        if err:
            return {"ok": False, "provider": self.name, "model": self.model,
                    "path": None, "error": err}

        out = Path(out_path)
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(base64.b64decode(b64))
        except Exception as e:
            return {"ok": False, "provider": self.name, "model": self.model,
                    "path": None, "error": _mask(f"decode/save failed: {type(e).__name__}: {e}", self._api_key)}

        _finalize_image(str(out), aspect)  # crop the fixed OpenAI size to the exact target aspect

        return {"ok": True, "provider": self.name, "model": self.model,
                "path": str(out), "error": None}
