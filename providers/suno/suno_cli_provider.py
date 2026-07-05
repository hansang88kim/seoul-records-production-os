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
import sys as _sys

def _win_creation_flags() -> dict:
    """
    On Windows, isolate the suno child process from the parent's console
    signals so a Ctrl+C (STATUS_CONTROL_C_EXIT) inside suno.exe / Chrome
    cannot kill the parent.

    CREATE_NEW_PROCESS_GROUP gives suno its own signal group.

    We deliberately do NOT use DETACHED_PROCESS / CREATE_NO_WINDOW here:
    suno-cli opens a piloted Chrome to solve hCaptcha, which needs a
    normal console/desktop association to render. The worker process that
    calls this is itself already detached from Streamlit, so isolating the
    signal group is sufficient to protect the Streamlit server.
    """
    if _sys.platform == "win32":
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        return {"creationflags": CREATE_NEW_PROCESS_GROUP}
    return {}




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
        proc = subprocess.run(cmd, timeout=timeout, encoding="utf-8",
                              errors="replace", **_win_creation_flags())
    except FileNotFoundError:
        raise ProviderError(
            "provider_unavailable",
            f"suno CLI not found at '{bin_path}'. Set SUNO_CLI_BIN in .env.",
        )
    except subprocess.TimeoutExpired:
        raise ProviderError("polling_timeout", f"Timed out after {timeout}s.")

    if proc.returncode != 0:
        # Semantic exit codes from paperfoot/suno-cli:
        #   1 = general error, 2 = config/CAPTCHA/input, 3 = auth expired
        if proc.returncode == 3:
            raise ProviderError(
                "auth_required",
                "Suno 세션 만료 — 새 쿠키를 입력하세요.",
                {"exit_code": proc.returncode, "command_args": args[:6]},
            )
        if proc.returncode == 2:
            # Often a CAPTCHA-loading failure or an input/style problem.
            raise ProviderError(
                "captcha_required",
                "생성 실패 (exit 2) — CAPTCHA 로딩 실패 또는 입력 오류일 수 있습니다. "
                "다시 시도하면 대부분 해결됩니다.",
                {"exit_code": proc.returncode, "command_args": args[:6]},
            )
        raise ProviderError(
            "generation_failed",
            f"suno 종료 코드 {proc.returncode}",
            {"exit_code": proc.returncode, "command_args": args[:6]},
        )
    return proc


def _map_error_code(code: str) -> str:
    mapping = {
        "auth_expired": "auth_required",
        "auth_missing": "auth_required",
        "auth_failed": "auth_required",
        "captcha": "captcha_required",
        "config_error": "captcha_required",  # "hcaptcha never finished loading"
        "hcaptcha": "captcha_required",
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

def _extract_credits(data) -> int | None:
    """
    Safely extract credit balance from suno credits JSON.
    Handles various shapes: {credits_left: N}, {data: {credits: N}},
    {data: N}, or a bare int. Never raises AttributeError.
    """
    if data is None:
        return None
    if isinstance(data, (int, float)):
        return int(data)
    if not isinstance(data, dict):
        return None

    # Try top-level keys first
    for key in ("credits_left", "credits", "balance", "remaining"):
        val = data.get(key)
        if isinstance(val, (int, float)):
            return int(val)

    # Try nested under "data"
    inner = data.get("data")
    if isinstance(inner, (int, float)):
        return int(inner)
    if isinstance(inner, dict):
        for key in ("credits_left", "credits", "balance", "remaining"):
            val = inner.get(key)
            if isinstance(val, (int, float)):
                return int(val)

    return None


# Hyphen variants that may prefix a "negative" style token:
#   - U+002D hyphen-minus, U+2010 hyphen, U+2011 non-breaking hyphen,
#   - U+2012 figure dash, U+2013 en dash, U+2014 em dash, U+2212 minus sign
_NEG_HYPHENS = "\u002d\u2010\u2011\u2012\u2013\u2014\u2212"


def _split_style_and_excludes(style: str) -> tuple[str, list[str]]:
    """
    Clean the style tags: remove any "negative" tokens (e.g. "-sax lead",
    "‑trot") and return them separately so they go to --exclude instead.

    Suno treats anything inside --tags as a POSITIVE style, so a leading
    hyphen does NOT negate — it actually makes Suno add that instrument.
    Negatives must go to the --exclude flag. This guards against negatives
    leaking into the style text from any source (old session state, manual
    entry, special hyphen characters, etc.).

    Returns (clean_style, extracted_excludes).
    """
    if not style:
        return "", []
    parts = [p.strip() for p in style.split(",")]
    clean_parts: list[str] = []
    extracted: list[str] = []
    for part in parts:
        if not part:
            continue
        # Does this token start with any hyphen/dash variant? → it's a negative
        first = part[0]
        if first in _NEG_HYPHENS:
            term = part.lstrip(_NEG_HYPHENS).strip()
            if term:
                extracted.append(term)
        else:
            clean_parts.append(part)
    clean_style = ", ".join(clean_parts)
    return clean_style, extracted


class SunoCliProvider(ComposerProvider):
    """
    Subprocess adapter for paperfoot/suno-cli.
    Binary: SUNO_CLI_BIN env → "suno" on PATH.
    """

    PROVIDER_NAME = "suno_cli"

    def __init__(self):
        self._bin = _get_suno_bin()
        self._last_clip_ids: list[str] = []

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

    # ─── auto-auth ───────────────────────────────────────────────────────

    def _ensure_auth(self, force: bool = False) -> bool:
        """
        Authenticate using SUNO_COOKIE from env.
        Runs: suno auth --cookie <cookie>  (no capture — like manual CLI)

        Always re-authenticates (no caching) — re-running auth --cookie
        before every generation/retry gives the most reliable session for
        the piloted-Chrome hCaptcha flow.

        Returns True only if auth command succeeds AND the session is
        verified working (credits check passes). Never logs the cookie.
        """
        from services.metadata_consistency_service import redact_sensitive
        cookie = os.getenv("SUNO_COOKIE", "").strip()
        if not cookie:
            logger.warning("SUNO_COOKIE not set — skipping auto-auth")
            return False

        # Step 1: run auth --cookie (no capture_output — needed for CLI internals)
        try:
            proc = subprocess.run(
                [self._bin, "auth", "--cookie", cookie],
                timeout=30, **_win_creation_flags(),
            )
            if proc.returncode != 0:
                logger.warning("auth --cookie returned code %d", proc.returncode)
                return False
        except FileNotFoundError:
            logger.error("suno binary not found at %s", self._bin)
            return False
        except Exception as e:
            logger.warning("auth --cookie failed: %s", type(e).__name__)
            return False

        # Step 2: verify the session actually works via credits
        # (auth can return 0 but session still be invalid)
        try:
            data = _run_suno_json(["credits"], timeout=20, suno_bin=self._bin)
            credits = _extract_credits(data)
            logger.info("Auth verified — credits: %s", credits)
            return True
        except ProviderError as e:
            if e.status == "auth_required":
                logger.warning("Auth succeeded but session invalid (expired cookie)")
                return False
            # Credits check failed for non-auth reason — assume auth is OK
            logger.warning("Credits check error (non-auth): %s", e.status)
            return True
        except Exception as e:
            logger.warning("Credits verify error: %s", type(e).__name__)
            return True  # Don't block on transient credit-check errors

    def verify_ready(self) -> dict:
        """
        Full pre-generation check, mirrors the manual CLI workflow:
          1. suno auth --cookie <cookie>   (authenticate)
          2. suno credits --json           (verify session + get balance)
        Returns: {"ok": bool, "authenticated": bool, "credits": int|None, "message": str}
        Never exposes the cookie value.
        """
        result = {"ok": False, "authenticated": False, "credits": None, "message": ""}

        # Step 1: cookie present?
        from services.metadata_consistency_service import redact_sensitive
        cookie = os.getenv("SUNO_COOKIE", "").strip()
        if not cookie:
            result["message"] = "SUNO_COOKIE 미설정 — 사이드바에서 쿠키를 입력하세요"
            return result

        # Step 2: authenticate
        authed = self._ensure_auth()
        result["authenticated"] = authed
        if not authed:
            result["message"] = "쿠키 인증 실패 — 쿠키가 만료되었을 수 있습니다. 새 쿠키를 입력하세요"
            return result

        # Step 3: verify credits (proves the session actually works)
        try:
            data = _run_suno_json(["credits"], timeout=20, suno_bin=self._bin)
            credits = _extract_credits(data)
            result["credits"] = credits
            result["ok"] = True
            result["message"] = f"인증 완료 · 크레딧 {credits}" if credits is not None else "인증 완료"
        except ProviderError as e:
            if e.status == "auth_required":
                result["message"] = "세션 만료 — 새 쿠키를 입력하세요"
            else:
                result["message"] = f"크레딧 확인 실패: {e}"
        except Exception as e:
            result["message"] = f"크레딧 확인 오류: {type(e).__name__}: {e}"

        return result

    # ─── create_song ─────────────────────────────────────────────────────

    def create_song(
        self,
        title: str,
        style: str,
        lyrics: str,
        options: dict | None = None,
        progress_callback=None,
    ) -> str:
        """
        Full generation flow (mirrors the working manual CLI workflow):
          1. suno auth --cookie <cookie>   (authenticate — REQUIRED, raises on fail)
          2. suno generate ... --wait      (blocks until generation completes)
          3. suno list                     (resolve clip IDs by title match)

        v1.0.0-alpha.29: NO local auto-download. This deliberately does NOT
        pass --download to the CLI — the user downloads the finished song
        manually from suno.com (Suno Pro/Premier gives WAV; MP3 preview via
        `download_mp3_preview()` remains available as an explicit opt-in call
        for callers that still want it, e.g. workflows/suno_one_song_dry_run.py).

        NO --json flag on generate (conflicts with --wait).
        Returns comma-separated clip IDs resolved via `suno list`.
        """
        # ── Step 1: Authenticate (REQUIRED) ──────────────────────────────
        # Always re-auth before every generation. The cookie session is
        # short-lived, so this must run on each call.
        from services.metadata_consistency_service import redact_sensitive
        cookie = os.getenv("SUNO_COOKIE", "").strip()
        if not cookie:
            raise ProviderError(
                "auth_required",
                "SUNO_COOKIE가 설정되지 않았습니다. 사이드바에서 쿠키를 입력하세요.",
            )

        authed = self._ensure_auth()
        if not authed:
            raise ProviderError(
                "auth_required",
                "Suno 인증 실패 — 쿠키가 만료되었습니다. 새 쿠키를 입력하세요.",
            )

        opts = options or {}

        # SAFETY: strip any negative tokens (e.g. "-sax lead", "‑trot") that
        # leaked into the style text — they must go to --exclude, not --tags.
        # (Suno reads --tags as positive styles, so "-sax" would ADD sax.)
        style, extracted_negs = _split_style_and_excludes(style or "")
        style = style.strip()
        if not style:
            raise ProviderError(
                "generation_failed",
                "스타일이 비어 있습니다 — 스타일 태그를 입력하거나 '프리셋 적용'을 누르세요.",
            )

        # Write lyrics to temp file
        lyrics_file = Path(tempfile.mktemp(suffix=".txt", prefix="suno_lyrics_"))
        lyrics_file.write_text(lyrics, encoding="utf-8")

        # NOTE: no local download directory is created or passed to the CLI.
        # `opts.get("download_dir")`, if present, is accepted but ignored —
        # kept only so callers that still pass it (e.g. for report-file
        # placement in app/tabs/song_lab.py) don't need to change their call
        # sites. It has no effect on the `suno generate` command below.

        # Build command — match exact paperfoot/suno-cli v0.5.7 syntax
        cmd = [
            "generate",
            "--title", title,
            "--tags", style,
            "--lyrics-file", str(lyrics_file),
            "--wait",
        ]

        # Optional flags — combine explicit excludes + any negatives pulled
        # out of the style text. Dedupe while preserving order.
        exclude = list(opts.get("exclude_styles", []) or [])
        for neg in extracted_negs:
            if neg not in exclude:
                exclude.append(neg)
        # Also strip any stray hyphen prefixes from the exclude items themselves
        exclude = [e.lstrip(_NEG_HYPHENS).strip() for e in exclude if e.lstrip(_NEG_HYPHENS).strip()]
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

        logger.info("suno generate: title=%s (no local download)", title)

        # ── Generate with CAPTCHA auto-retry ─────────────────────────────
        # CAPTCHA loading on suno.com is intermittent (server-side). Retry
        # many times, re-authenticating before each attempt. The retry count
        # is configurable via SUNO_CAPTCHA_RETRIES (default 10).
        max_attempts = int(os.getenv("SUNO_CAPTCHA_RETRIES", "10"))
        max_attempts = max(1, min(max_attempts, 30))  # clamp 1-30
        proc = None
        last_err = None
        import time as _t
        try:
            for attempt in range(1, max_attempts + 1):
                try:
                    if attempt > 1:
                        logger.info("CAPTCHA retry %d/%d — re-authenticating", attempt, max_attempts)
                        if progress_callback:
                            progress_callback(
                                f"🔄 hCaptcha 재시도 {attempt}/{max_attempts}회 — 재인증 중...",
                                attempt=attempt, max_attempts=max_attempts,
                            )
                        # Re-auth before EVERY retry (fresh session each time)
                        self._ensure_auth()
                        # Backoff gives hCaptcha time to load: 3s,4.5s,6s...12s
                        delay = min(3 + (attempt - 2) * 1.5, 12)
                        _t.sleep(delay)
                    else:
                        if progress_callback:
                            progress_callback(
                                f"🎵 Suno 생성 시도 중... (hCaptcha 자동 해결)",
                                attempt=1, max_attempts=max_attempts,
                            )
                    proc = _run_suno_raw(cmd, timeout=_GENERATE_TIMEOUT, suno_bin=self._bin)
                    break  # success
                except ProviderError as e:
                    last_err = e
                    # Only retry on CAPTCHA failures; re-raise others immediately
                    if e.status == "captcha_required" and attempt < max_attempts:
                        logger.warning(
                            "CAPTCHA failed (attempt %d/%d), retrying in a moment...",
                            attempt, max_attempts,
                        )
                        if progress_callback:
                            progress_callback(
                                f"⚠️ hCaptcha 로딩 실패 ({attempt}/{max_attempts}회) — 잠시 후 재시도",
                                attempt=attempt, max_attempts=max_attempts, failed=True,
                            )
                        continue
                    raise
        finally:
            lyrics_file.unlink(missing_ok=True)

        if proc is None and last_err is not None:
            raise last_err

        # ── Resolve clip IDs (no download) ────────────────────────────────
        # `suno generate --wait` completes generation but we never pass
        # --download, so no local files exist to parse IDs from. Resolve
        # the clip IDs by querying `suno list` and matching on title —
        # this is the same documented workflow as the manual CLI usage
        # (see docs/v0.4_suno_cli_provider.md: "suno generate --wait →
        # generates song, returns clip IDs"). No files are fetched here.
        clip_ids: list[str] = []
        try:
            list_data = _run_suno_json(["list"], timeout=30, suno_bin=self._bin)
            clips = list_data.get("data", [])
            if isinstance(clips, dict):
                clips = clips.get("clips", clips.get("songs", []))
            matching = [c for c in clips if c.get("title", "") == title]
            if matching:
                clip_ids = [c.get("id", "")[:8] for c in matching[:2] if c.get("id")]
        except Exception as e:
            logger.warning("suno list lookup failed: %s", type(e).__name__)

        if not clip_ids:
            clip_ids = ["generated"]  # at least mark as attempted

        task_id = ",".join(clip_ids)
        self._last_clip_ids = clip_ids
        logger.info("suno generate done: task_id=%s (download skipped by design)", task_id)
        return task_id

    # ─── get_status ──────────────────────────────────────────────────────

    def get_status(self, task_id: str) -> dict:
        ids = task_id.split(",")
        data = _run_suno_json(["status"] + ids, suno_bin=self._bin)

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
        """
        Explicit, opt-in MP3 download for a given task_id. NOT called
        automatically by create_song() — callers invoke this on demand
        (e.g. workflows/suno_one_song_dry_run.py).
        """
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

    # ─── clip management (v1.0.0-alpha.49) ───────────────────────────────

    def get_clip_info(self, clip_id: str) -> dict:
        """
        Full details for one clip (`suno info <id>`). Accepts an 8-char id
        prefix (the same form our task_ids store) — the CLI resolves it.

        v1.0.0-alpha.52: if `info` returns nothing for the prefix (some
        suno-cli builds only resolve `info` by the FULL clip id, unlike
        `status`), fall back to `suno list` and match by prefix — the same
        resolution approach create_song() already relies on after
        generation. This makes clip lookups resilient regardless of
        which form the installed CLI version accepts.
        Returns the clip data dict ({} if truly not found).
        """
        try:
            data = _run_suno_json(["info", clip_id], timeout=30, suno_bin=self._bin)
            d = data.get("data", {})
            if isinstance(d, list):
                d = d[0] if d else {}
            if d:
                return d
        except ProviderError:
            pass

        # Fallback: resolve via `suno list` and match on id prefix.
        try:
            list_data = _run_suno_json(["list"], timeout=30,
                                       suno_bin=self._bin)
            clips = list_data.get("data", [])
            if isinstance(clips, dict):
                clips = clips.get("clips", clips.get("songs", []))
            for c in clips:
                cid = c.get("id", "")
                if cid and cid.startswith(clip_id):
                    return c
        except Exception:
            pass
        return {}

    def delete_clips(self, clip_ids: list[str]) -> dict:
        """
        Delete/trash clips on Suno (`suno delete <ids>`). Destructive —
        callers must confirm with the user first. Returns
        {"ok": bool, "deleted": [...], "error": str|None}.
        """
        ids = [c for c in (clip_ids or []) if c]
        if not ids:
            return {"ok": False, "deleted": [], "error": "no clip ids"}
        try:
            _run_suno_json(["delete"] + ids, timeout=60, suno_bin=self._bin)
            return {"ok": True, "deleted": ids, "error": None}
        except ProviderError as e:
            return {"ok": False, "deleted": [], "error": f"{e.status}: {e}"}
