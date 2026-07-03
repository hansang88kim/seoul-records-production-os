"""
services/thumbnail/midjourney_provider.py — Midjourney image generation via
Apiframe v2 (https://apiframe.ai), which drives the user's own Midjourney
account.

v1.0.0-alpha.32: rewritten for Apiframe v2. Accounts created after
2026-04-28 are issued v2 keys (prefix "afk_") which are NOT compatible with
the old v1 endpoint (api.apiframe.pro/imagine) this module originally used —
that call now fails with a clear "your key is v2" 400 error from Apiframe
itself. v2 uses a different base URL, a unified /images/generate endpoint
across all models (Midjourney is just model="midjourney"), a different auth
header, and job polling under /jobs/:id instead of /fetch.

Flow (Apiframe v2 REST API — https://apiframe.ai/docs):
  1. POST https://api.apiframe.ai/v2/images/generate
       headers: {X-API-Key: <APIFRAME_API_KEY>}
       body:    {"prompt": ..., "model": "midjourney",
                 "midjourneyParams": {"aspect_ratio": "16:9"}}
       → 202 {"jobId": "...", "status": "QUEUED"}
  2. Poll GET https://api.apiframe.ai/v2/jobs/{jobId}
       QUEUED/PROCESSING → {"status": ..., "progress": 0-100}
       COMPLETED         → {"status": "COMPLETED",
                             "result": {"images": [...4 urls...],
                                        "gridUrl": "..."}}
       FAILED            → {"status": "FAILED", "error": "..."}
  3. Download images[0] as the candidate image; the other 3 quadrants are
     saved next to it as *_alt2..4.png (best-effort) so the user can swap
     later.

Notes:
  * The API key comes from APIFRAME_API_KEY (sidebar 🎨 Image Gen → Midjourney).
    It is NEVER logged and is masked out of any error text.
  * Midjourney has no local-file image-to-image here, so ``ref_image_path`` is
    ignored — the 1:1 cover is generated natively from the same prompt instead.
  * negative_prompt is appended to the prompt text as Midjourney's native
    ``--no`` parameter (the unified /images/generate endpoint has no separate
    negative-prompt field — model-specific syntax goes in the prompt itself,
    same as Midjourney's own Discord /imagine command).
  * Third-party Midjourney APIs (Apiframe/LinkrAPI/etc.) are unofficial;
    Midjourney offers no public API. Same accepted-risk category as suno-cli.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from services.thumbnail.image_provider import ImageGenProvider, _finalize_image

APIFRAME_BASE_URL = "https://api.apiframe.ai/v2"
_KEY_ENV_VAR = "APIFRAME_API_KEY"

# Apiframe recommends polling every 2-3s for image jobs.
_POLL_INTERVAL_SEC = 3


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


def verify_apiframe_key(key: str) -> tuple[bool, str]:
    """
    GET /v2/me — used by the sidebar credential field to confirm the key is
    real (Apiframe v2, active) before the user tries a real generation.
    """
    import requests
    try:
        resp = requests.get(
            f"{APIFRAME_BASE_URL}/me",
            headers={"X-API-Key": key},
            timeout=15,
        )
    except Exception as e:
        return False, f"{type(e).__name__}: {_mask(str(e), key)}"

    if resp.status_code == 200:
        try:
            data = resp.json()
            team = data.get("team", {})
            plan = team.get("plan", "?")
            credits = team.get("credits", "?")
            return True, f"연결됨 · plan={plan} · 잔여 크레딧={credits}"
        except Exception:
            return True, "연결됨"
    if resp.status_code == 401:
        return False, "키 무효 (401) — Apiframe 대시보드에서 키 다시 확인"
    if not key.startswith("afk_"):
        return False, f"HTTP {resp.status_code} — 키가 'afk_'로 시작하지 않으면 v1 키일 수 있음(v2 필요)"
    return False, f"HTTP {resp.status_code}: {_mask(resp.text[:200], key)}"


class MidjourneyApiframeProvider(ImageGenProvider):
    """Real generation on the user's Midjourney account via Apiframe v2."""

    name = "midjourney-apiframe"
    is_real = True

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or get_apiframe_key()
        self.model = "midjourney"

    # ── internal HTTP helpers ────────────────────────────────────────────

    def _headers(self) -> dict:
        return {"Content-Type": "application/json", "X-API-Key": self._api_key}

    def _submit_imagine(self, prompt: str, aspect: str) -> tuple[str | None, str | None]:
        """POST /v2/images/generate. Returns (job_id, error)."""
        import requests
        try:
            resp = requests.post(
                f"{APIFRAME_BASE_URL}/images/generate",
                headers=self._headers(),
                json={
                    "prompt": prompt,
                    "model": "midjourney",
                    "midjourneyParams": {"aspect_ratio": aspect},
                },
                timeout=60,
            )
        except Exception as e:
            return None, _mask(f"imagine request failed: {type(e).__name__}: {e}", self._api_key)

        if resp.status_code not in (200, 202):
            return None, _mask(f"imagine HTTP {resp.status_code}: {resp.text[:300]}", self._api_key)
        try:
            data = resp.json()
        except Exception:
            return None, "imagine returned invalid JSON"
        job_id = data.get("jobId") or data.get("job_id") or data.get("id")
        if not job_id:
            err = data.get("error") or data.get("message") or data
            return None, _mask(f"imagine returned no jobId: {str(err)[:300]}", self._api_key)
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
                # Transient network error — keep polling until the deadline.
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
                    if not urls and result.get("gridUrl"):
                        urls = [result["gridUrl"]]
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

        # Midjourney takes negatives via --no (comma-separated), not a
        # separate API field — same syntax as Midjourney's own /imagine.
        full_prompt = prompt.strip()
        if negative_prompt:
            neg = negative_prompt.strip().rstrip(",")
            if neg:
                full_prompt = f"{full_prompt} --no {neg}"
        # ref_image_path is intentionally ignored (no local-file i2i support);
        # the 1:1 is composed natively via aspect_ratio instead.

        job_id, err = self._submit_imagine(full_prompt, aspect)
        if err:
            return {"ok": False, "provider": self.name, "model": self.model,
                    "path": None, "error": err}

        urls, err = self._poll_until_done(job_id)
        if err or not urls:
            return {"ok": False, "provider": self.name, "model": self.model,
                    "path": None, "error": err or "no image URLs returned",
                    "task_id": job_id}

        out = Path(out_path)
        dl_err = self._download(urls[0], out)
        if dl_err:
            return {"ok": False, "provider": self.name, "model": self.model,
                    "path": None, "error": dl_err, "task_id": job_id}
        _finalize_image(str(out), aspect)  # strip stray bars + lock exact size

        # Best-effort: keep the other 3 quadrants (if any) next to the
        # primary so the user can swap manually later. Failures here never
        # fail the task.
        for n, alt_url in enumerate(urls[1:4], start=2):
            try:
                alt = out.with_name(f"{out.stem}_alt{n}{out.suffix}")
                if self._download(alt_url, alt) is None:
                    _finalize_image(str(alt), aspect)
            except Exception:
                pass

        return {"ok": True, "provider": self.name, "model": self.model,
                "path": str(out), "error": None, "task_id": job_id}
