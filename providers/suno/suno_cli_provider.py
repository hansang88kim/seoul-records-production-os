"""
providers/suno/suno_cli_provider.py (v0.4.2)
──────────────────────────────────────────────
Subprocess adapter for paperfoot/suno-cli (Rust binary).

Binary: SUNO_CLI_BIN env → "suno" on PATH.
Auth: suno auth --login (one-time, extracts from browser).

IMPORTANT:
  - generate: do NOT use --json (conflicts with --wait --download)
  - status/credits/info: use --json for structured output
  - --model values: v5.5, v5, v4.5 (no "chirp-" prefix)
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

_DEFAULT_TIMEOUT = 300
_GENERATE_TIMEOUT = 600  # 10 min for --wait


# ─── Binary resolution ──────────────────────────────────────────────────────

def _get_suno_bin() -> str:
    env_bin = os.getenv("SUNO_CLI_BIN", "").strip()
    if env_bin:
        p = Path(env_bin)
        if p.exists():
            return str(p)
        found = shutil.which(env_bin)
        if found:
            return found
        return env_bin
    found = shutil.which("suno")
    return found or "suno"


def _suno_available() -> bool:
    suno_bin = _get_suno_bin()
    if Path(suno_bin).exists():
        return True
    return shutil.which(suno_bin) is not None


# ─── Subprocess helpers ──────────────────────────────────────────────────────

def _redact_stderr(stderr: str) -> str:
    """
    Redact actual credential VALUES from stderr, but keep error messages visible.
    Only redact lines that look like they contain raw credential strings
    (long base64-like tokens), not error messages that mention 'JWT expired'.
    """
    if not stderr:
        return ""
    import re
    s = stderr[:500]
    # Redact long base64/JWT-like tokens (40+ chars of alphanumeric/base64)
    s = re.sub(r'[A-Za-z0-9_\-]{40,}', '***REDACTED_TOKEN***', s)
    # Redact cookie= or token= values
    s = re.sub(r'(cookie|token|key|secret|password)\s*[=:]\s*\S+', r'=***REDACTED***', s, flags=re.IGNORECASE)
    return s


def _run_suno_json(
    args: list[str],
    timeout: int = _DEFAULT_TIMEOUT,
    suno_bin: str | None = None,
) -> dict:
    """
    Run a suno CLI command WITH --json. For read-only commands only:
    status, credits, info, list, agent-info.
    """
    bin_path = suno_bin or _get_suno_bin()
    cmd = [bin_path] + args + ["--json"]

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, env=env)
    except FileNotFoundError:
        raise ProviderError(
            "provider_unavailable",
            f"suno CLI not found at '{bin_path}'. Set SUNO_CLI_BIN in .env.",
        )
    except subprocess.TimeoutExpired:
        raise ProviderError("polling_timeout", f"Timed out after {timeout}s.")

    stdout = proc.stdout.strip()
    if not stdout:
        if proc.returncode != 0:
            raise ProviderError(
                "generation_failed",
                f"suno exited with code {proc.returncode}",
                {"stderr": _redact_stderr(proc.stderr), "command": f"suno {' '.join(args)} --json"},
            )
        return {}

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        raise ProviderError(
            "unknown_provider_error", "Invalid JSON from suno CLI.",
            {"stdout_excerpt": stdout[:200]},
        )

    if data.get("status") == "error":
        err = data.get("error", {})
        code = err.get("code", "unknown_provider_error")
        msg = err.get("message", "Unknown error")
        suggestion = err.get("suggestion", "")
        raise ProviderError(_map_error_code(code), f"{msg}. {suggestion}".strip())

    return data


def _run_suno_raw(
    args: list[str],
    timeout: int = _DEFAULT_TIMEOUT,
    suno_bin: str | None = None,
) -> subprocess.CompletedProcess:
    """
    Run a suno CLI command WITHOUT --json and WITHOUT capturing output.

    For generate + side-effect commands. Output goes directly to the console
    so Chrome CAPTCHA solver can work (capture_output=True breaks it by
    switching suno-cli to piped/JSON mode).

    Returns the CompletedProcess (stdout/stderr will be None).
    """
    bin_path = suno_bin or _get_suno_bin()
    cmd = [bin_path] + args

    try:
        proc = subprocess.run(cmd, timeout=timeout, encoding="utf-8")
    except FileNotFoundError:
        raise ProviderError(
            "provider_unavailable",
            f"suno CLI not found at '{bin_path}'. Set SUNO_CLI_BIN in .env.",
        )
    except subprocess.TimeoutExpired:
        raise ProviderError("polling_timeout", f"Timed out after {timeout}s.")

    if proc.returncode != 0:
        # Semantic exit codes from paperfoot/suno-cli:
        #   1 = general error, 2 = usage/config, 3 = auth expired
        if proc.returncode == 3:
            raise ProviderError(
                "auth_required",
                "Suno session expired. Run: suno auth --refresh (or suno auth --login)",
                {"exit_code": proc.returncode, "command_args": args[:6]},
            )
        raise ProviderError(
            "generation_failed",
            f"suno exited with code {proc.returncode}",
            {"exit_code": proc.returncode, "command_args": args[:6]},
        )
    return proc


def _map_error_code(code: str) -> str:
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
        },
    )


# ─── Provider ───────────────────────────────────────────────────────────────

class SunoCliProvider(ComposerProvider):
    """
    Subprocess adapter for paperfoot/suno-cli.
    Binary: SUNO_CLI_BIN env → "suno" on PATH.
    """

    PROVIDER_NAME = "suno_cli"

    def __init__(self):
        self._bin = _get_suno_bin()
        self._last_clip_ids: list[str] = []
        self._last_download_dir: str = ""

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider=self.PROVIDER_NAME,
            status="ready" if _suno_available() else "provider_unavailable",
            title=True, lyrics=True, style=True,
            exclude_styles=True, vocal_gender=True,
            weirdness=True, style_influence=True,
            instrumental=True, model_selector=True, persona=True,
            two_candidates=True, wav_download=False, mp3_preview=True,
            supports_polling=True, requires_user_session=True,
            note=f"paperfoot/suno-cli at '{self._bin}'.",
            fallback_instructions="WAV: download from suno.com → Manual WAV Import.",
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
        suno generate --title --tags --lyrics-file --wait --download <dir>
        NO --json flag (conflicts with --wait --download).
        Returns comma-separated clip IDs parsed from downloaded filenames.
        """
        opts = options or {}

        # Write lyrics to temp file
        lyrics_file = Path(tempfile.mktemp(suffix=".txt", prefix="suno_lyrics_"))
        lyrics_file.write_text(lyrics, encoding="utf-8")

        # Download directory
        download_dir = opts.get("download_dir")
        if download_dir:
            download_path = Path(download_dir)
        else:
            download_path = Path(tempfile.mkdtemp(prefix="suno_dl_"))
        download_path.mkdir(parents=True, exist_ok=True)

        # Build command — match exact paperfoot/suno-cli v0.5.7 syntax
        cmd = [
            "generate",
            "--title", title,
            "--tags", style,
            "--lyrics-file", str(lyrics_file),
            "--wait",
            "--download", str(download_path),
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
            cmd.extend(["--weirdness", str(int(weirdness))])

        style_influence = opts.get("style_influence")
        if style_influence is not None:
            cmd.extend(["--style-influence", str(int(style_influence))])

        if opts.get("instrumental"):
            cmd.append("--instrumental")

        # Model: only pass if explicitly set (suno-cli uses v5.5, v5, v4.5 format)
        model = opts.get("model")
        if model:
            # Normalize chirp-v4 → v4, chirp-v4-5 → v4.5
            m = model.lower().replace("chirp-", "").replace("_", ".").replace("-", ".")
            if m in ("v5.5", "v5", "v4.5", "v4", "v3.5"):
                cmd.extend(["--model", m])

        persona = opts.get("persona")
        if persona:
            cmd.extend(["--persona", persona])

        logger.info("suno generate: title=%s download=%s", title, download_path)

        try:
            proc = _run_suno_raw(cmd, timeout=_GENERATE_TIMEOUT, suno_bin=self._bin)
        finally:
            lyrics_file.unlink(missing_ok=True)

        self._last_download_dir = str(download_path)

        # Parse clip IDs from downloaded filenames
        # Format: title-slug-CLIPID8.mp3
        mp3s = sorted(download_path.glob("*.mp3"))
        clip_ids = []
        for mp3 in mp3s:
            # Last 8 chars before .mp3 extension are the clip ID fragment
            stem = mp3.stem
            if len(stem) >= 8:
                clip_ids.append(stem)  # full stem as ID reference

        if not clip_ids:
            # Try parsing stdout for clip IDs
            stdout = proc.stdout or ""
            import re
            uuids = re.findall(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', stdout)
            clip_ids = uuids if uuids else ["unknown"]

        task_id = ",".join(clip_ids)
        self._last_clip_ids = clip_ids
        logger.info("suno generate done: %d files in %s", len(mp3s), download_path)
        return task_id

    # ─── get_status ──────────────────────────────────────────────────────

    def get_status(self, task_id: str) -> dict:
        ids = task_id.split(",")
        try:
            data = _run_suno_json(["status"] + ids, suno_bin=self._bin)
        except ProviderError:
            # If status fails, check if files exist from generate
            if self._last_download_dir:
                mp3s = list(Path(self._last_download_dir).glob("*.mp3"))
                if mp3s:
                    return {
                        "status": "completed",
                        "candidates": [{"candidate_id": chr(65+i), "status": "completed",
                                        "file_path": str(f)} for i, f in enumerate(mp3s)],
                        "progress": 1.0,
                        "error": None,
                    }
            raise

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

    # ─── download ────────────────────────────────────────────────────────

    def download_wav(self, task_id: str, output_path: Path) -> Path:
        raise ProviderError(
            "wav_download_unavailable",
            "suno-cli downloads MP3 only. WAV: download from suno.com → Manual WAV Import.",
        )

    def download_mp3_preview(self, task_id: str, output_path: Path) -> Path | None:
        # Files already downloaded by create_song --wait --download
        if self._last_download_dir:
            mp3s = sorted(Path(self._last_download_dir).glob("*.mp3"))
            if mp3s:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                import shutil as _sh
                _sh.copy2(mp3s[0], output_path)
                return output_path

        # Fallback: suno download (no --json for download either)
        ids = task_id.split(",")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            _run_suno_raw(
                ["download"] + ids[:1] + ["--output", str(output_path.parent)],
                timeout=120, suno_bin=self._bin,
            )
        except ProviderError:
            return None
        mp3s = sorted(output_path.parent.glob("*.mp3"))
        if mp3s and mp3s[0] != output_path:
            mp3s[0].rename(output_path)
            return output_path
        return None

    # ─── metadata ────────────────────────────────────────────────────────

    def get_metadata(self, task_id: str) -> dict:
        ids = task_id.split(",")
        try:
            data = _run_suno_json(["info"] + ids[:1], suno_bin=self._bin)
            return {"provider": self.PROVIDER_NAME, "task_id": task_id, "data": data.get("data", {})}
        except ProviderError:
            return {"provider": self.PROVIDER_NAME, "task_id": task_id}

    def check_credits(self) -> dict:
        return _run_suno_json(["credits"], timeout=30, suno_bin=self._bin)

    def check_auth(self) -> dict:
        return _run_suno_json(["auth"], timeout=15, suno_bin=self._bin)
