"""
services/thumbnail/apiframe_nanobanana_provider.py — Nano Banana 2 (Google
Gemini 3.1 Flash Image) generation via Apiframe v2, reusing the same
Apiframe API key already connected for Midjourney (sidebar 🎨 Image Gen).

v1.0.0-alpha.34: added as a direct replacement for the Midjourney-via-Apiframe
engine option. Nano Banana 2 is Google's own officially licensed model —
Apiframe is simply reselling official API access to it here, not automating
an unofficial platform (unlike Midjourney, which has no public API). This
sidesteps the account-ban / self-bot risk category entirely while reusing
the exact same Apiframe v2 connection, job-submit/poll pattern, and
capacity-error auto-retry already proven working end-to-end in production
(services/thumbnail/midjourney_provider.py).

Flow (Apiframe v2 REST API — https://apiframe.ai/docs, confirmed via the
account's own Playground code sample):
  1. POST https://api.apiframe.ai/v2/images/generate
       headers: {X-API-Key: <APIFRAME_API_KEY>}
       body:    {"model": "nano-banana-2", "prompt": ...,
                 "nanoBananaParams": {"aspect_ratio": "16:9"}}
       → 202 {"jobId": "...", "status": "QUEUED"}
  2. Poll GET https://api.apiframe.ai/v2/jobs/{jobId}
       QUEUED/PROCESSING → {"status": ..., "progress": 0-100}
       COMPLETED         → {"status": "COMPLETED",
                             "result": {"images": [...]}}
       FAILED            → {"status": "FAILED", "error": "..."}
  3. Download images[0] as the candidate image.

Notes:
  * The API key comes from APIFRAME_API_KEY (sidebar 🎨 Image Gen) — the same
    key already used for Midjourney; no separate credential needed.
  * Gemini/Nano Banana has no dedicated negative-prompt field, so
    negative_prompt is folded into the prompt text as "\\n\\nAvoid: ..." —
    same convention already used by the direct-Gemini providers in
    image_provider.py.
  * ref_image_path is currently ignored (image-to-image editing would use a
    separate Apiframe endpoint not wired up here); the 1:1 cover is generated
    natively from the same prompt + aspect_ratio instead.
  * "No available capacity" / HTTP 503 are transient provider-side queue-full
    errors (Apiframe FAQ: retry with exponential backoff — failed jobs are
    auto-refunded). Same auto-retry behavior as the Midjourney provider.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from services.thumbnail.image_provider import ImageGenProvider, _finalize_image
from services.thumbnail.midjourney_provider import (
    APIFRAME_BASE_URL, get_apiframe_key, verify_apiframe_key,  # re-exported for reuse
    _mask, _is_capacity_error, _capacity_retries, _CAPACITY_BACKOFF_SEC,
)

_POLL_INTERVAL_SEC = 3


def _default_timeout() -> int:
    """Overall generation timeout in seconds (SEOUL_NANOBANANA_TIMEOUT, default 180)."""
    try:
        return max(30, int(os.environ.get("SEOUL_NANOBANANA_TIMEOUT", "180")))
    except ValueError:
        return 180


# Apiframe's images/generate validates the "prompt" field to <=2000 chars
# (confirmed by a real 400: "Too big: expected string to have <=2000
# characters"). The main creative prompt matters most, so when folding in
# negative_prompt would push the total over the limit, trim the negative
# portion first (never the main prompt); if the main prompt alone is
# already over, trim that too as a last resort.
_MAX_PROMPT_CHARS = 2000


def _fit_prompt(main_prompt: str, negative_prompt: str) -> str:
    main_prompt = main_prompt.strip()
    if not negative_prompt:
        return main_prompt[:_MAX_PROMPT_CHARS]

    negative_prompt = negative_prompt.strip()
    suffix = f"\n\nAvoid: {negative_prompt}"
    full = f"{main_prompt}{suffix}"
    if len(full) <= _MAX_PROMPT_CHARS:
        return full

    # Trim the negative-prompt suffix to whatever room is left after the main
    # prompt (main prompt is never cut for this — it's the creative content).
    room = _MAX_PROMPT_CHARS - len(main_prompt) - len("\n\nAvoid: ")
    if room > 20:  # only worth keeping if it leaves a meaningful fragment
        return f"{main_prompt}\n\nAvoid: {negative_prompt[:room]}"
    # No room at all for a negative suffix — just send the (possibly
    # truncated) main prompt.
    return main_prompt[:_MAX_PROMPT_CHARS]


class ApiframeNanoBananaProvider(ImageGenProvider):
    """Nano Banana 2 generation via the already-connected Apiframe account."""

    name = "nanobanana2-apiframe"
    is_real = True

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or get_apiframe_key()
        self.model = "nano-banana-2"

    # ── internal HTTP helpers ────────────────────────────────────────────

    def _headers(self) -> dict:
        return {"Content-Type": "application/json", "X-API-Key": self._api_key}

    def _submit(self, prompt: str, aspect: str) -> tuple[str | None, str | None]:
        """POST /v2/images/generate. Returns (job_id, error)."""
        import requests
        try:
            resp = requests.post(
                f"{APIFRAME_BASE_URL}/images/generate",
                headers=self._headers(),
                json={
                    "model": "nano-banana-2",
                    "prompt": prompt,
                    "nanoBananaParams": {"aspect_ratio": aspect, "resolution": "1K"},
                },
                timeout=60,
            )
        except Exception as e:
            return None, _mask(f"generate request failed: {type(e).__name__}: {e}", self._api_key)

        if resp.status_code not in (200, 202):
            return None, _mask(f"generate HTTP {resp.status_code}: {resp.text[:300]}", self._api_key)
        try:
            data = resp.json()
        except Exception:
            return None, "generate returned invalid JSON"
        job_id = data.get("jobId") or data.get("job_id") or data.get("id")
        if not job_id:
            err = data.get("error") or data.get("message") or data
            return None, _mask(f"generate returned no jobId: {str(err)[:300]}", self._api_key)
        return str(job_id), None

    def _poll_until_done(self, job_id: str) -> tuple[list[str] | None, str | None]:
        """Poll GET /v2/jobs/:id until COMPLETED/FAILED. Returns (image_urls, error)."""
        import requests
        deadline = time.time() + _default_timeout()
        last_status = "QUEUED"
        while time.time() < deadline:
            try:
                resp = requests.get(
                    f"{APIFRAME_BASE_URL}/jobs/{job_id}",
                    headers=self._headers(),
                    timeout=30,
                )
            except Exception as e:
                last_status = f"poll error: {type(e).__name__}"
                time.sleep(_POLL_INTERVAL_SEC)
                continue
            if resp.status_code != 200:
                last_status = f"poll HTTP {resp.status_code}"
                time.sleep(_POLL_INTERVAL_SEC)
                continue
            try:
                data = resp.json()
            except Exception:
                time.sleep(_POLL_INTERVAL_SEC)
                continue

            status = str(data.get("status", "")).upper()
            if status == "COMPLETED":
                result = data.get("result") or {}
                if isinstance(result, dict):
                    urls = result.get("images") or []
                elif isinstance(result, str):
                    urls = [result]
                else:
                    urls = []
                if urls:
                    return urls, None
                return None, "job completed but no image URLs in result"
            if status == "FAILED":
                err = data.get("error") or "task failed"
                return None, _mask(f"generation failed: {str(err)[:300]}", self._api_key)

            last_status = f"{status} ({data.get('progress', 0)}%)"
            time.sleep(_POLL_INTERVAL_SEC)
        return None, f"timed out after {_default_timeout()}s (last status: {last_status})"

    def _download(self, url: str, out: Path) -> str | None:
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

        # Gemini/Nano Banana has no dedicated negative-prompt field — fold it
        # into the prompt text, same convention as the direct-Gemini providers.
        # Apiframe hard-limits the "prompt" field to 2000 chars — _fit_prompt
        # trims the negative-prompt suffix (never the main prompt) to fit.
        full_prompt = _fit_prompt(prompt, negative_prompt)
        # ref_image_path is intentionally ignored (no i2i wiring here yet);
        # the 1:1 is composed natively via aspect_ratio instead.

        job_id, err, urls = None, None, None
        attempts = _capacity_retries() + 1
        for attempt in range(attempts):
            job_id, err = self._submit(full_prompt, aspect)
            if not err:
                urls, err = self._poll_until_done(job_id)
            if not err:
                break
            if not _is_capacity_error(err) or attempt == attempts - 1:
                break
            delay = _CAPACITY_BACKOFF_SEC[min(attempt, len(_CAPACITY_BACKOFF_SEC) - 1)]
            time.sleep(delay)

        if err:
            return {"ok": False, "provider": self.name, "model": self.model,
                    "path": None, "error": err, "task_id": job_id}

        out = Path(out_path)
        dl_err = self._download(urls[0], out)
        if dl_err:
            return {"ok": False, "provider": self.name, "model": self.model,
                    "path": None, "error": dl_err, "task_id": job_id}
        _finalize_image(str(out), aspect)

        return {"ok": True, "provider": self.name, "model": self.model,
                "path": str(out), "error": None, "task_id": job_id}
