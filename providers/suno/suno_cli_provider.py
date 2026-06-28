"""
providers/suno/suno_cli_provider.py (v0.4)
──────────────────────────────────────────
Subprocess adapter for paperfoot/suno-cli (Rust binary).

Auth: auto-extracts from Chrome/Arc/Brave/Firefox/Edge via `suno auth --login`.
No CAPTCHA solving, no 2Captcha, no Playwright.

WAV note: Suno only provides WAV for Pro/Premier subscribers via suno.com.
This CLI downloads MP3 with embedded lyrics. For distribution masters,
use ManualImportProvider to import WAV from suno.com.

All commands use --json for structured output.
Progress/errors go to stderr; JSON to stdout.
Credentials are never logged.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from providers.suno.base import (
    ComposerProvider, ProviderCapabilities, ProviderError, CandidateInfo,
)

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 300  # 5 min for generation with --wait


def _suno_available() -> bool:
    """Check if 'suno' binary is on PATH."""
    return shutil.which("suno") is not None


def _run_suno(args: list[str], timeout: int = _DEFAULT_TIMEOUT) -> dict:
    """
    Run a suno CLI command with --json and return parsed JSON.
    Never logs credentials. Raises ProviderError on failure.
    """
    cmd = ["suno"] + args + ["--json"]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise ProviderError(
            "provider_unavailable",
            "suno CLI binary not found. Install from: "
            "https://github.com/paperfoot/suno-cli/releases",
        )
    except subprocess.TimeoutExpired:
        raise ProviderError(
            "polling_timeout",
            f"suno command timed out after {timeout}s.",
        )

    # Parse JSON from stdout
    stdout = proc.stdout.strip()
    if not stdout:
        if proc.returncode != 0:
            # Check stderr for clues (but redact credentials)
            stderr_safe = proc.stderr[:300] if proc.stderr else ""
            for word in ("cookie", "token", "jwt", "session", "key"):
                if word in stderr_safe.lower():
                    stderr_safe = "[stderr redacted — may contain credentials]"
                    break
            raise ProviderError(
                "generation_failed",
                f"suno CLI exited with code {proc.returncode}",
                {"stderr": stderr_safe},
            )
        return {}

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        raise ProviderError(
            "unknown_provider_error",
            "suno CLI returned invalid JSON.",
            {"stdout_excerpt": stdout[:200]},
        )

    # Check for error in JSON response
    if data.get("status") == "error":
        err = data.get("error", {})
        code = err.get("code", "unknown_provider_error")
        msg = err.get("message", "Unknown error")
        suggestion = err.get("suggestion", "")

        # Map suno-cli error codes to our standard statuses
        status = _map_error_code(code)
        raise ProviderError(status, f"{msg}. {suggestion}".strip())

    return data


def _map_error_code(code: str) -> str:
    """Map suno-cli error codes to Seoul Records provider error statuses."""
    mapping = {
        "auth_expired": "auth_required",
        "auth_missing": "auth_required",
        "auth_failed": "auth_required",
        "captcha": "captcha_required",
        "rate_limit": "rate_limited",
        "insufficient_credits": "generation_failed",
        "generation_failed": "generation_failed",
        "not_found": "generation_failed",
        "network": "provider_unavailable",
        "timeout": "polling_timeout",
    }
    return mapping.get(code, "unknown_provider_error")


def _normalize_clip(clip: dict, candidate_id: str) -> CandidateInfo:
    """Normalize a suno-cli clip object to CandidateInfo."""
    return CandidateInfo(
        candidate_id=candidate_id,
        suno_clip_id=clip.get("id", ""),
        audio_url=clip.get("audio_url"),
        wav_url=None,  # suno-cli downloads MP3; WAV requires Pro via suno.com
        duration_seconds=clip.get("duration"),
        status="completed" if clip.get("status") in ("complete", "completed") else clip.get("status", "pending"),
        metadata={
            "title": clip.get("title", ""),
            "tags": clip.get("tags", clip.get("metadata", {}).get("tags", "")),
            "model": clip.get("model_name", clip.get("model", "")),
            "image_url": clip.get("image_url", ""),
        },
    )


class SunoCliProvider(ComposerProvider):
    """
    Subprocess adapter for paperfoot/suno-cli.

    Requires: `suno` binary on PATH + `suno auth --login` completed.
    No CAPTCHA solving needed — uses browser's existing auth session.
    """

    PROVIDER_NAME = "suno_cli"

    def get_capabilities(self) -> ProviderCapabilities:
        available = _suno_available()
        return ProviderCapabilities(
            provider=self.PROVIDER_NAME,
            status="ready" if available else "provider_unavailable",
            title=True,
            lyrics=True,
            style=True,
            exclude_styles=True,       # --exclude flag
            vocal_gender=True,         # --vocal flag
            weirdness=True,            # --weirdness flag
            style_influence=True,      # --style-influence flag
            instrumental=True,         # --instrumental flag
            model_selector=True,       # --model flag
            persona=True,              # --persona flag
            two_candidates=True,
            wav_download=False,        # MP3 only; WAV requires Pro via suno.com
            mp3_preview=True,
            supports_polling=True,     # --wait flag
            requires_user_session=True,
            note=(
                "Subprocess adapter for paperfoot/suno-cli (Rust). "
                "Auto-auth from browser. All Suno v5.5 params supported. "
                "Downloads MP3; WAV requires Suno Pro via suno.com → ManualImport."
            ),
            fallback_instructions=(
                "For WAV distribution masters: download WAV from suno.com, "
                "then import via Song Generation tab → Manual WAV Import."
            ),
        )

    def create_song(
        self,
        title: str,
        style: str,
        lyrics: str,
        options: dict | None = None,
    ) -> str:
        """Submit song generation via `suno generate`. Returns task_id (clip IDs)."""
        if not _suno_available():
            raise ProviderError(
                "provider_unavailable",
                "suno CLI binary not found. Install from: "
                "https://github.com/paperfoot/suno-cli/releases",
            )

        opts = options or {}

        # Write lyrics to temp file
        lyrics_file = Path(tempfile.mktemp(suffix=".txt"))
        lyrics_file.write_text(lyrics, encoding="utf-8")

        cmd = [
            "generate",
            "--title", title,
            "--tags", style,
            "--lyrics-file", str(lyrics_file),
        ]

        # Optional flags
        exclude = opts.get("exclude_styles", [])
        if exclude:
            cmd.extend(["--exclude", ", ".join(exclude)])

        vocal = opts.get("vocal_gender", "")
        if vocal and vocal.lower() != "auto":
            cmd.extend(["--vocal", vocal.lower()])

        weirdness = opts.get("weirdness")
        if weirdness is not None:
            cmd.extend(["--weirdness", str(weirdness)])

        style_influence = opts.get("style_influence")
        if style_influence is not None:
            cmd.extend(["--style-influence", str(style_influence)])

        if opts.get("instrumental"):
            cmd.append("--instrumental")

        model = opts.get("model")
        if model:
            cmd.extend(["--model", model])

        persona = opts.get("persona")
        if persona:
            cmd.extend(["--persona", persona])

        logger.info("suno generate: title=%s", title)

        try:
            data = _run_suno(cmd, timeout=_DEFAULT_TIMEOUT)
        finally:
            lyrics_file.unlink(missing_ok=True)

        # Extract clip IDs from response
        clips = data.get("data", [])
        if isinstance(clips, dict):
            clips = [clips]
        if not clips:
            raise ProviderError("generation_failed", "No clips returned from suno generate.")

        clip_ids = [c.get("id", "") for c in clips if c.get("id")]
        self._last_clip_ids = clip_ids
        task_id = ",".join(clip_ids)

        logger.info("suno generate submitted: %d clips", len(clip_ids))
        return task_id

    def get_status(self, task_id: str) -> dict:
        """Poll status via `suno status`."""
        ids = task_id.split(",")
        data = _run_suno(["status"] + ids)

        clips = data.get("data", [])
        if isinstance(clips, dict):
            clips = [clips]

        labels = ["A", "B", "C", "D"]
        candidates = [
            _normalize_clip(c, labels[i] if i < len(labels) else str(i)).__dict__
            for i, c in enumerate(clips)
        ]

        all_done = all(c.get("status") == "completed" for c in candidates)
        any_failed = any(c.get("status") == "failed" for c in candidates)

        return {
            "status": "completed" if all_done else ("failed" if any_failed else "generating"),
            "candidates": candidates,
            "progress": sum(1 for c in candidates if c.get("status") == "completed") / max(len(candidates), 1),
            "error": None,
        }

    def get_candidates(self, task_id: str) -> list[CandidateInfo]:
        status = self.get_status(task_id)
        return [CandidateInfo(**c) for c in status.get("candidates", [])]

    def download_wav(self, task_id: str, output_path: Path) -> Path:
        """
        WAV download is NOT available via suno-cli (MP3 only).
        WAV requires Suno Pro/Premier subscription + download from suno.com.
        """
        raise ProviderError(
            "wav_download_unavailable",
            "suno-cli downloads MP3 only. WAV requires Suno Pro/Premier subscription. "
            "Download WAV from suno.com, then import via Manual WAV Import.",
        )

    def download_mp3_preview(self, task_id: str, output_path: Path) -> Path | None:
        """Download MP3 via `suno download`."""
        ids = task_id.split(",")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        download_dir = output_path.parent

        try:
            _run_suno(["download"] + ids + ["--output", str(download_dir)], timeout=120)
        except ProviderError:
            return None

        # Find downloaded MP3 files
        mp3s = sorted(download_dir.glob("*.mp3"))
        if mp3s:
            # Rename first MP3 to expected output path
            mp3s[0].rename(output_path)
            return output_path
        return None

    def get_metadata(self, task_id: str) -> dict:
        """Get clip metadata via `suno info`."""
        ids = task_id.split(",")
        try:
            data = _run_suno(["info"] + ids[:1])  # info takes single ID
            return {
                "provider": self.PROVIDER_NAME,
                "task_id": task_id,
                "data": data.get("data", {}),
            }
        except ProviderError:
            return {"provider": self.PROVIDER_NAME, "task_id": task_id}

    def check_credits(self) -> dict:
        """Check remaining Suno credits via `suno credits`."""
        return _run_suno(["credits"], timeout=30)

    def check_auth(self) -> dict:
        """Check auth status via `suno auth`."""
        return _run_suno(["auth"], timeout=15)
