"""
services/thumbnail/midjourney_provider.py — Midjourney image generation via
Apiframe (https://apiframe.pro), which drives the user's own Midjourney account.

Flow (Apiframe REST API):
  1. POST https://api.apiframe.pro/imagine
       headers: {Authorization: <APIFRAME_API_KEY>}
       body:    {"prompt": ..., "aspect_ratio": "16:9"}
       → {"task_id": "..."}
  2. Poll POST https://api.apiframe.pro/fetch  body: {"task_id": ...}
       processing → {"status": "processing", "percentage": "40"}
       finished   → {"task_type": "imagine",
                     "original_image_url": <2x2 grid>,
                     "image_urls": [<4 separated images>]}
       failed     → {"status": "failed", ...}
  3. Download image_urls[0] as the candidate image; the other 3 quadrants are
     saved next to it as *_alt2..4.png (best-effort) so the user can swap later.

Notes:
  * The API key comes from APIFRAME_API_KEY (sidebar 🎨 Image Gen → Midjourney).
    It is NEVER logged and is masked out of any error text.
  * Midjourney has no local-file image-to-image here, so ``ref_image_path`` is
    ignored — the 1:1 cover is generated natively from the same prompt instead.
  * negative_prompt is translated to Midjourney's ``--no`` parameter.
  * Third-party Midjourney APIs (Apiframe/LinkrAPI/etc.) are unofficial;
    Midjourney offers no public API. Same accepted-risk category as suno-cli.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from services.thumbnail.image_provider import ImageGenProvider, _finalize_image

APIFRAME_BASE_URL = "https://api.apiframe.pro"
_KEY_ENV_VAR = "APIFRAME_API_KEY"

# Poll every _POLL_INTERVAL_SEC until _default_timeout() seconds have passed.
# MJ fast mode usually completes in ~60s; relax mode can take several minutes.
_POLL_INTERVAL_SEC = 5


def get_apiframe_key() -> str | None:
    """Return the Apiframe API key, or None. Never logged."""
    val = os.environ.get(_KEY_ENV_VAR, "")
    return val.strip() or None


def _default_timeout() -> int:
    """Overall generation timeout in seconds (SEOUL_MJ_TIMEOUT, default 300)."""
    try:
        return max(30, int(os.environ.get("SEOUL_MJ_TIMEOUT", "300")))
    except ValueError:
        return 300


def _mask(text: str, secret: str | None) -> str:
    """Remove the API key from any surfaced text."""
    if secret and secret in text:
        return text.replace(secret, "***")
    return text


class MidjourneyApiframeProvider(ImageGenProvider):
    """Real generation on the user's Midjourney account via Apiframe."""

    name = "midjourney-apiframe"
    is_real = True

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or get_apiframe_key()
        self.model = "midjourney"

    # ── internal HTTP helpers ────────────────────────────────────────────

    def _headers(self) -> dict:
        return {"Content-Type": "application/json", "Authorization": self._api_key}

    def _submit_imagine(self, prompt: str, aspect: str) -> tuple[str | None, str | None]:
        """POST /imagine. Returns (task_id, error)."""
        import requests
        try:
            resp = requests.post(
                f"{APIFRAME_BASE_URL}/imagine",
                headers=self._headers(),
                json={"prompt": prompt, "aspect_ratio": aspect},
                timeout=60,
            )
        except Exception as e:
            return None, _mask(f"imagine request failed: {type(e).__name__}: {e}", self._api_key)
        if resp.status_code != 200:
            return None, _mask(f"imagine HTTP {resp.status_code}: {resp.text[:300]}", self._api_key)
        try:
            data = resp.json()
        except Exception:
            return None, "imagine returned invalid JSON"
        task_id = data.get("task_id") or data.get("taskId")
        if not task_id:
            err = data.get("errors") or data.get("error") or data.get("message") or data
            return None, _mask(f"imagine returned no task_id: {str(err)[:300]}", self._api_key)
        return str(task_id), None

    def _poll_until_done(self, task_id: str) -> tuple[list[str] | None, str | None]:
        """Poll /fetch until image_urls appear. Returns (image_urls, error)."""
        import requests
        deadline = time.time() + _default_timeout()
        last_status = "submitted"
        while time.time() < deadline:
            try:
                resp = requests.post(
                    f"{APIFRAME_BASE_URL}/fetch",
                    headers=self._headers(),
                    json={"task_id": task_id},
                    timeout=30,
                )
            except Exception as e:
                # Transient network error — keep polling until the deadline.
                last_status = f"fetch error: {type(e).__name__}"
                time.sleep(_POLL_INTERVAL_SEC)
                continue
            if resp.status_code != 200:
                last_status = f"fetch HTTP {resp.status_code}"
                time.sleep(_POLL_INTERVAL_SEC)
                continue
            try:
                data = resp.json()
            except Exception:
                time.sleep(_POLL_INTERVAL_SEC)
                continue

            # Completion is signalled by the presence of image URLs (the
            # finished payload has no reliable "status" field per the docs).
            urls = data.get("image_urls") or []
            if urls:
                return list(urls), None
            if data.get("original_image_url"):
                return [data["original_image_url"]], None

            status = str(data.get("status", "")).lower()
            if status in ("failed", "error"):
                err = data.get("errors") or data.get("error") or data.get("message") or "task failed"
                return None, _mask(f"generation failed: {str(err)[:300]}", self._api_key)
            last_status = status or last_status
            time.sleep(_POLL_INTERVAL_SEC)
        return None, f"timed out after {_default_timeout()}s (last status: {last_status})"

    def _download(self, url: str, out: Path) -> str | None:
        """Download one image URL to out. Returns error or None."""
        import requests
        try:
            resp = requests.get(url, timeout=120)
            if resp.status_code != 200:
                return f"image download HTTP {resp.status_code}"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(resp.content)
            return None
        except Exception as e:
            return _mask(f"image download failed: {type(e).__name__}: {e}", self._api_key)

    # ── ImageGenProvider interface ───────────────────────────────────────

    def generate(self, prompt, out_path, negative_prompt="", index=0, meta=None,
                 aspect="16:9", ref_image_path=None):
        if not self._api_key:
            return {"ok": False, "provider": self.name, "model": self.model,
                    "path": None,
                    "error": "no API key (enter the Apiframe key in the sidebar 🎨 Image Gen, "
                             "or set APIFRAME_API_KEY)"}

        # Midjourney takes negatives via --no (comma-separated), not prose.
        full_prompt = prompt.strip()
        if negative_prompt:
            neg = negative_prompt.strip().rstrip(",")
            if neg:
                full_prompt = f"{full_prompt} --no {neg}"
        # ref_image_path is intentionally ignored (no local-file i2i support);
        # the 1:1 is composed natively via aspect_ratio instead.

        task_id, err = self._submit_imagine(full_prompt, aspect)
        if err:
            return {"ok": False, "provider": self.name, "model": self.model,
                    "path": None, "error": err}

        urls, err = self._poll_until_done(task_id)
        if err or not urls:
            return {"ok": False, "provider": self.name, "model": self.model,
                    "path": None, "error": err or "no image URLs returned",
                    "task_id": task_id}

        out = Path(out_path)
        dl_err = self._download(urls[0], out)
        if dl_err:
            return {"ok": False, "provider": self.name, "model": self.model,
                    "path": None, "error": dl_err, "task_id": task_id}
        _finalize_image(str(out), aspect)  # strip stray bars + lock exact size

        # Best-effort: keep the other 3 quadrants next to the primary so the
        # user can swap manually later. Failures here never fail the task.
        for n, alt_url in enumerate(urls[1:4], start=2):
            try:
                alt = out.with_name(f"{out.stem}_alt{n}{out.suffix}")
                if self._download(alt_url, alt) is None:
                    _finalize_image(str(alt), aspect)
            except Exception:
                pass

        return {"ok": True, "provider": self.name, "model": self.model,
                "path": str(out), "error": None, "task_id": task_id}
