"""
providers/suno/suno_cli_provider.py (v0.4.2)
──────────────────────────────────────────────
Subprocess adapter for paperfoot/suno-cli (Rust binary).

Auth: auto-extracts from Chrome/Arc/Brave/Firefox/Edge via `suno auth --login`.
No CAPTCHA solving, no 2Captcha, no Playwright.

Binary location: reads SUNO_CLI_BIN from env, falls back to "suno" on PATH.
All commands use --json for structured output.
Credentials are never logged.
"""
from __future__ import annotations

import json
import logging
import os
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


# ─── Binary resolution ──────────────────────────────────────────────────────

def _get_suno_bin() -> str:
    """
    Resolve the suno CLI binary path.
    Priority: SUNO_CLI_BIN env → "suno" on PATH.
    """
    env_bin = os.getenv("SUNO_CLI_BIN", "").strip()
    if env_bin:
        # Absolute or relative path from env
        p = Path(env_bin)
        if p.exists():
            return str(p)
        # Maybe it's just a name like "suno" — check PATH
        found = shutil.which(env_bin)
        if found:
            return found
        # Return as-is; subprocess will raise FileNotFoundError
        return env_bin
    # Default: look on PATH
    found = shutil.which("suno")
    return found or "suno"


def _suno_available() -> bool:
    """Check if the suno binary is reachable."""
    suno_bin = _get_suno_bin()
    if Path(suno_bin).exists():
        return True
    return shutil.which(suno_bin) is not None


def _run_suno(
    args: list[str],
    timeout: int = _DEFAULT_TIMEOUT,
    suno_bin: str | None = None,
) -> dict:
    """
    Run a suno CLI command with --json and return parsed JSON.
    Never logs credentials. Raises ProviderError on failure.
    """
    bin_path = suno_bin or _get_suno_bin()
    cmd = [bin_path] + args + ["--json"]

    logger.debug("Running: %s %s --json", bin_path, " ".join(args[:4]))

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
            f"suno CLI binary not found at '{bin_path}'. "
            "Set SUNO_CLI_BIN in .env or install from: "
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
            stderr_safe = proc.stderr[:300] if proc.stderr else ""
            for word in ("cookie", "token", "jwt", "session", "key", "secret"):
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
        wav_url=None,
        duration_seconds=clip.get("duration"),
        status="completed" if clip.get("status") in ("complete", "completed") else clip.get("status", "pending"),
        metadata={
            "title": clip.get("title", ""),
            "tags": clip.get("tags", clip.get("metadata", {}).get("tags", "")),
            "model": clip.get("model_name", clip.get("model", "")),
            "image_url": clip.get("image_url", ""),
        },
    )


# ─── Provider ───────────────────────────────────────────────────────────────

class SunoCliProvider(ComposerProvider):
    """
    Subprocess adapter for paperfoot/suno-cli.

    Binary: reads SUNO_CLI_BIN from env, falls back to "suno" on PATH.
    Auth: `suno auth --login` (one-time, extracts from browser).
    No CAPTCHA solving needed.
    """

    PROVIDER_NAME = "suno_cli"

    def __init__(self):
        self._bin = _get_suno_bin()

    def get_capabilities(self) -> ProviderCapabilities:
        available = _suno_available()
        return ProviderCapabilities(
            provider=self.PROVIDER_NAME,
            status="ready" if available else "provider_unavailable",
            title=True,
            lyrics=True,
            style=True,
            exclude_styles=True,
            vocal_gender=True,
            weirdness=True,
            style_influence=True,
            instrumental=True,
            model_selector=True,
            persona=True,
            two_candidates=True,
            wav_download=False,
            mp3_preview=True,
            supports_polling=True,
            requires_user_session=True,
            note=(
                f"paperfoot/suno-cli at '{self._bin}'. "
                "Downloads MP3; WAV requires Suno Pro via suno.com → ManualImport."
            ),
            fallback_instructions=(
                "For WAV distribution masters: download WAV from suno.com, "
                "then import via Song Generation tab → Manual WAV Import."
            ),
        )

    # ─── create_song ─────────────────────────────────────────────────────

    def create_song(
        self,
        title: str,
        style: str,
        lyrics: str,
        options: dict | None = None,
    ) -> str:
        """
        Generate song via `suno generate --wait --download <dir>`.
        Waits for completion and downloads MP3 in one call.
        Returns comma-separated clip IDs as task_id.
        """
        opts = options or {}

        # Write lyrics to temp file (UTF-8)
        lyrics_file = Path(tempfile.mktemp(suffix=".txt", prefix="suno_lyrics_"))
        lyrics_file.write_text(lyrics, encoding="utf-8")

        # Download directory
        download_dir = opts.get("download_dir")
        if download_dir:
            download_path = Path(download_dir)
        else:
            download_path = Path(tempfile.mkdtemp(prefix="suno_dl_"))
        download_path.mkdir(parents=True, exist_ok=True)

        cmd = [
            "generate",
            "--title", title,
            "--tags", style,
            "--lyrics-file", str(lyrics_file),
            "--wait",
            "--download", str(download_path),
        ]

        # ── Optional flags ────────────────────────────────────────────────
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

        logger.info("suno generate: title=%s download=%s", title, download_path)

        try:
            data = _run_suno(cmd, timeout=_DEFAULT_TIMEOUT, suno_bin=self._bin)
        finally:
            lyrics_file.unlink(missing_ok=True)

        # Extract clip IDs
        clips = data.get("data", [])
        if isinstance(clips, dict):
            clips = [clips]
        if not clips:
            raise ProviderError("generation_failed", "No clips returned from suno generate.")

        clip_ids = [c.get("id", "") for c in clips if c.get("id")]
        self._last_clip_ids = clip_ids
        self._last_download_dir = str(download_path)

        task_id = ",".join(clip_ids)
        logger.info("suno generate complete: %d clips → %s", len(clip_ids), download_path)
        return task_id

    # ─── get_status ──────────────────────────────────────────────────────

    def get_status(self, task_id: str) -> dict:
        """Poll status via `suno status <ids>`."""
        ids = task_id.split(",")
        data = _run_suno(["status"] + ids, suno_bin=self._bin)

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

    # ─── download_wav ────────────────────────────────────────────────────

    def download_wav(self, task_id: str, output_path: Path) -> Path:
        """WAV not available via suno-cli. Use ManualImportProvider."""
        raise ProviderError(
            "wav_download_unavailable",
            "suno-cli downloads MP3 only. WAV requires Suno Pro/Premier. "
            "Download WAV from suno.com, then import via Manual WAV Import.",
        )

    # ─── download_mp3_preview ────────────────────────────────────────────

    def download_mp3_preview(self, task_id: str, output_path: Path) -> Path | None:
        """
        Download MP3 via `suno download <ids> --output <dir>`.
        If create_song was called with --wait --download, files may already exist.
        """
        # Check if files already downloaded by create_song
        last_dir = getattr(self, "_last_download_dir", None)
        if last_dir:
            mp3s = sorted(Path(last_dir).glob("*.mp3"))
            if mp3s:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                import shutil as _sh
                _sh.copy2(mp3s[0], output_path)
                return output_path

        # Fallback: explicit download
        ids = task_id.split(",")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        download_dir = output_path.parent

        try:
            _run_suno(
                ["download"] + ids + ["--output", str(download_dir)],
                timeout=120,
                suno_bin=self._bin,
            )
        except ProviderError:
            return None

        mp3s = sorted(download_dir.glob("*.mp3"))
        if mp3s:
            if mp3s[0] != output_path:
                mp3s[0].rename(output_path)
            return output_path
        return None

    # ─── get_metadata ────────────────────────────────────────────────────

    def get_metadata(self, task_id: str) -> dict:
        ids = task_id.split(",")
        try:
            data = _run_suno(["info"] + ids[:1], suno_bin=self._bin)
            return {"provider": self.PROVIDER_NAME, "task_id": task_id, "data": data.get("data", {})}
        except ProviderError:
            return {"provider": self.PROVIDER_NAME, "task_id": task_id}

    # ─── Utility ─────────────────────────────────────────────────────────

    def check_credits(self) -> dict:
        return _run_suno(["credits"], timeout=30, suno_bin=self._bin)

    def check_auth(self) -> dict:
        return _run_suno(["auth"], timeout=15, suno_bin=self._bin)
