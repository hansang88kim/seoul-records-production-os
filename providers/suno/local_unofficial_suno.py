"""
providers/suno/local_unofficial_suno.py (v0.3)
───────────────────────────────────────────────
HTTP adapter for locally-running unofficial Suno API wrappers.

Primary target: gcui-art/suno-api (Node.js, localhost:3000)
Auth: user's own SUNO_COOKIE → uses their official Suno account credits.

Policy:
  - No CAPTCHA bypass — if session expires, return auth_required
  - Never log/commit SUNO_COOKIE
  - Prefer WAV download over MP3
  - On any failure → ProviderError with safe details
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Optional

from providers.suno.base import (
    ComposerProvider, ProviderCapabilities, ProviderError,
    CandidateInfo, PROVIDER_ERROR_STATUSES,
)

logger = logging.getLogger(__name__)

# ─── Default config ──────────────────────────────────────────────────────────

_DEFAULT_BASE_URL = "http://localhost:3000"
_DEFAULT_TIMEOUT = 30
_POLL_INTERVAL = 5
_POLL_MAX_ATTEMPTS = 60   # 5 min max wait
_DEFAULT_MODEL = "chirp-v4"


def _get_config() -> dict:
    """Load config from env. Never log cookie values."""
    import os
    return {
        "base_url": os.getenv("SUNO_LOCAL_API_BASE_URL", _DEFAULT_BASE_URL).rstrip("/"),
        "cookie": os.getenv("SUNO_COOKIE", ""),
        "download_format": os.getenv("SUNO_DOWNLOAD_FORMAT", "wav"),
        "timeout": int(os.getenv("SUNO_LOCAL_TIMEOUT", str(_DEFAULT_TIMEOUT))),
    }


def _safe_request(method: str, url: str, cookie: str = "",
                  json_body: dict | None = None, timeout: int = _DEFAULT_TIMEOUT) -> dict:
    """
    Make an HTTP request to the local Suno wrapper.
    Never logs cookies. Returns parsed JSON or raises ProviderError.
    """
    import requests

    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie

    try:
        resp = requests.request(
            method, url, headers=headers,
            json=json_body, timeout=timeout,
        )
    except requests.ConnectionError:
        raise ProviderError(
            "provider_unavailable",
            f"Cannot connect to local Suno API at {url.split('/api')[0]}. "
            "Ensure the server is running (npm run dev).",
        )
    except requests.Timeout:
        raise ProviderError(
            "provider_unavailable",
            f"Local Suno API timed out after {timeout}s.",
        )
    except Exception as e:
        raise ProviderError(
            "unknown_provider_error",
            f"HTTP request failed: {type(e).__name__}",
        )

    if resp.status_code == 401 or resp.status_code == 403:
        raise ProviderError(
            "auth_required",
            "Session expired or invalid. Update SUNO_COOKIE in .env and restart.",
        )

    if resp.status_code == 429:
        raise ProviderError(
            "rate_limited",
            "Rate limited by Suno. Wait before retrying.",
        )

    if resp.status_code >= 400:
        body = resp.text[:300]
        # Detect CAPTCHA/2FA in response
        lower = body.lower()
        if "captcha" in lower or "hcaptcha" in lower:
            raise ProviderError("captcha_required", "CAPTCHA detected. Manual verification required.")
        if "two_factor" in lower or "2fa" in lower or "verification" in lower:
            raise ProviderError("two_factor_required", "2FA detected. Manual verification required.")

        raise ProviderError(
            "generation_failed",
            f"API error HTTP {resp.status_code}",
            {"response_body": body},
        )

    try:
        return resp.json()
    except ValueError:
        raise ProviderError(
            "unknown_provider_error",
            "Invalid JSON response from local Suno API.",
        )


# ─── Normalize gcui-art/suno-api response into CandidateInfo ────────────────

def _normalize_candidates(clips: list[dict]) -> list[CandidateInfo]:
    """Normalize Suno clip objects into CandidateInfo list."""
    candidates = []
    labels = ["A", "B", "C", "D"]
    for i, clip in enumerate(clips[:4]):
        cid = labels[i] if i < len(labels) else str(i)
        meta = clip.get("metadata", {})
        candidates.append(CandidateInfo(
            candidate_id=cid,
            suno_clip_id=clip.get("id"),
            audio_url=clip.get("audio_url"),
            wav_url=clip.get("audio_url_wav") or clip.get("wav_url"),
            duration_seconds=clip.get("duration"),
            status=_map_clip_status(clip.get("status", "")),
            metadata={
                "title": clip.get("title", ""),
                "tags": meta.get("tags", ""),
                "model": clip.get("model_name", ""),
                "image_url": clip.get("image_url", ""),
            },
        ))
    return candidates


def _map_clip_status(raw: str) -> str:
    raw = raw.lower().strip()
    if raw in ("complete", "completed"):
        return "completed"
    if raw in ("streaming", "generating", "processing"):
        return "streaming"
    if raw in ("submitted", "queued"):
        return "pending"
    if raw in ("error", "failed"):
        return "failed"
    return raw or "pending"


# ─── Provider Implementation ────────────────────────────────────────────────

class LocalUnofficialSunoProvider(ComposerProvider):
    """
    HTTP adapter for locally-running unofficial Suno API (gcui-art/suno-api).
    Uses user's own Suno account credits via SUNO_COOKIE.
    """

    PROVIDER_NAME = "local_unofficial_suno"

    def __init__(self):
        self._config = _get_config()

    def get_capabilities(self) -> ProviderCapabilities:
        has_cookie = bool(self._config["cookie"])
        return ProviderCapabilities(
            provider=self.PROVIDER_NAME,
            status="ready" if has_cookie else "auth_required",
            title=True,
            lyrics=True,
            style=True,
            exclude_styles=True,          # via negative_tags
            vocal_gender=False,           # → injected into style tags
            weirdness=False,              # → stored as not_applied
            style_influence=False,        # → stored as not_applied
            instrumental=True,
            model_selector=True,
            persona=False,
            two_candidates=True,
            wav_download=True,            # via wav_url (when available)
            mp3_preview=True,
            supports_polling=True,
            requires_user_session=True,
            requires_credentials=False,
            requires_api_key=False,
            note=(
                "Wraps gcui-art/suno-api on localhost. "
                "vocal_gender → appended to style tags. "
                "weirdness/style_influence → not_applied."
            ),
            fallback_instructions=(
                "If WAV unavailable or session expired, "
                "fall back to ManualImportProvider."
            ),
        )

    def _url(self, path: str) -> str:
        return f"{self._config['base_url']}{path}"

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        return _safe_request(
            method, self._url(path),
            cookie=self._config["cookie"],
            json_body=body,
            timeout=self._config["timeout"],
        )

    # ─── create_song ─────────────────────────────────────────────────────

    def create_song(
        self,
        title: str,
        style: str,
        lyrics: str,
        options: dict | None = None,
    ) -> str:
        """Submit custom_generate to local Suno API. Returns task_id."""
        opts = options or {}

        # Build tags — inject vocal_gender if not directly supported
        tags = style
        vocal_gender = opts.get("vocal_gender", "")
        if vocal_gender and vocal_gender.lower() != "auto":
            gender_tag = f"{vocal_gender.lower()} vocal"
            if gender_tag not in tags.lower():
                tags = f"{tags}, {gender_tag}"

        # Build negative tags from exclude_styles
        exclude = opts.get("exclude_styles", [])
        negative_tags = ", ".join(exclude) if exclude else ""

        payload = {
            "prompt": lyrics,
            "tags": tags,
            "title": title,
            "make_instrumental": opts.get("instrumental", False),
            "model": opts.get("model", _DEFAULT_MODEL),
            "wait_audio": False,
        }
        if negative_tags:
            payload["negative_tags"] = negative_tags

        logger.info("Creating song: title=%s model=%s", title, payload["model"])
        data = self._request("POST", "/api/custom_generate", payload)

        # gcui-art returns a list of clip objects
        clips = data if isinstance(data, list) else data.get("data", data.get("clips", []))
        if not clips:
            raise self.safe_error(
                "generation_failed",
                "No clips returned from local Suno API.",
            )

        # Use first clip's ID as task_id
        task_id = clips[0].get("id", str(uuid.uuid4()))
        # Store full IDs for later retrieval
        self._last_clip_ids = [c.get("id", "") for c in clips]

        logger.info("Song submitted: task_id=%s clips=%d", task_id, len(clips))
        return task_id

    # ─── get_status ──────────────────────────────────────────────────────

    def get_status(self, task_id: str) -> dict:
        """Poll status via /api/get."""
        ids = getattr(self, "_last_clip_ids", [task_id])
        ids_str = ",".join(ids) if ids else task_id

        data = self._request("GET", f"/api/get?ids={ids_str}")
        clips = data if isinstance(data, list) else data.get("data", [data])
        candidates = _normalize_candidates(clips)

        all_done = all(c.status == "completed" for c in candidates)
        any_failed = any(c.status == "failed" for c in candidates)

        return {
            "status": "completed" if all_done else ("failed" if any_failed else "generating"),
            "candidates": [c.__dict__ for c in candidates],
            "progress": sum(1 for c in candidates if c.status == "completed") / max(len(candidates), 1),
            "error": None,
        }

    # ─── get_candidates ──────────────────────────────────────────────────

    def get_candidates(self, task_id: str) -> list[CandidateInfo]:
        status = self.get_status(task_id)
        return [CandidateInfo(**c) for c in status.get("candidates", [])]

    # ─── download_wav ────────────────────────────────────────────────────

    def download_wav(self, task_id: str, output_path: Path) -> Path:
        """Download WAV. Falls back to MP3 URL if wav_url unavailable."""
        import requests

        candidates = self.get_candidates(task_id)
        target = next((c for c in candidates if c.suno_clip_id == task_id), None)
        if not target and candidates:
            target = candidates[0]

        if not target:
            raise self.safe_error("wav_download_unavailable", "No candidate found for download.")

        url = target.wav_url or target.audio_url
        if not url:
            raise self.safe_error(
                "wav_download_unavailable",
                "No audio URL available. Use ManualImportProvider to upload WAV manually.",
            )

        is_wav = target.wav_url is not None
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            resp = requests.get(url, timeout=120, stream=True)
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
        except Exception as e:
            raise self.safe_error(
                "wav_download_unavailable",
                f"Download failed: {type(e).__name__}",
            )

        if not is_wav:
            logger.warning("WAV URL unavailable; downloaded MP3 instead: %s", output_path.name)

        return output_path

    # ─── download_mp3_preview ────────────────────────────────────────────

    def download_mp3_preview(self, task_id: str, output_path: Path) -> Path | None:
        import requests

        candidates = self.get_candidates(task_id)
        target = next((c for c in candidates if c.suno_clip_id == task_id), None)
        if not target and candidates:
            target = candidates[0]

        if not target or not target.audio_url:
            return None

        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            resp = requests.get(target.audio_url, timeout=120, stream=True)
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            return output_path
        except Exception:
            return None

    # ─── get_metadata ────────────────────────────────────────────────────

    def get_metadata(self, task_id: str) -> dict:
        candidates = self.get_candidates(task_id)
        return {
            "provider": self.PROVIDER_NAME,
            "task_id": task_id,
            "candidates": [c.__dict__ for c in candidates],
        }

    # ─── poll_until_complete ─────────────────────────────────────────────

    def poll_until_complete(
        self,
        task_id: str,
        max_attempts: int = _POLL_MAX_ATTEMPTS,
        interval: int = _POLL_INTERVAL,
    ) -> dict:
        """Poll /api/get until all candidates complete or timeout."""
        for attempt in range(max_attempts):
            status = self.get_status(task_id)
            if status["status"] == "completed":
                return status
            if status["status"] == "failed":
                raise self.safe_error("generation_failed", "Suno generation failed.")
            time.sleep(interval)

        raise self.safe_error(
            "polling_timeout",
            f"Suno generation did not complete within {max_attempts * interval}s.",
        )
