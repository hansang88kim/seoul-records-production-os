#!/usr/bin/env python3
"""
workflows/suno_one_song_dry_run.py (v0.3.2)
─────────────────────────────────────────────
Single-song dry-run test for LocalUnofficialSunoProvider.

Usage:
  # Mock mode (no real Suno server — for CI/testing)
  python workflows/suno_one_song_dry_run.py --mock

  # Real mode (requires gcui-art/suno-api running + SUNO_COOKIE set)
  python workflows/suno_one_song_dry_run.py

Output:
  outputs/dry_runs/YYYY-MM-DD_suno_one_song/
  ├─ dry_run_report.json
  ├─ dry_run_log.txt
  ├─ candidates/
  │  ├─ candidate_A.wav (or candidate_A_preview.mp3)
  │  └─ candidate_B.wav (or candidate_B_preview.mp3)
  └─ manual_import_required.txt   (if WAV unavailable)

Policy:
  - Never logs cookies/tokens/credentials
  - Stops on CAPTCHA / 2FA
  - 1 song only — no batch generation
"""
from __future__ import annotations

import json
import sys
import time
import wave
import struct
from datetime import datetime, timezone
from pathlib import Path

# ─── Seoul Records test prompt ──────────────────────────────────────────────

TEST_TITLE = "밤이 지나면"

TEST_STYLE = (
    "Key: A minor. Japanese nostalgic citypop with a late-1990s Seoul night mood, "
    "smooth CP-70 electric piano, DX7 glassy keys, chorus guitar, warm bass, "
    "soft synth layers, restrained drums entering after a 4-bar instrumental intro, "
    "low thick Korean female vocal, intimate and calm. "
    "No sax lead, no drum fill-ins, no tom fills, no snare rolls, "
    "no trot, no enka, no EDM, no bleepy sounds, no toy percussion."
)

TEST_LYRICS = """[Intro]
(4마디 음원 (instrumental only))

[Verse 1]
불 꺼진 사무실 창에
내 얼굴이 잠깐 비쳐
늦은 답장 하나 못 하고
밤은 먼저 흘러가

[Pre-Chorus]
괜찮은 척 웃어봐도
마음은 조금 늦게 와

[Chorus]
밤이 지나면
우리도 흐려질까
아무 말 없이
서로를 놓친 걸까

[Verse 2]
택시 불빛 지나가고
젖은 길은 조용해져
못다 한 말 주머니 속에
접힌 채로 남았어

[Pre-Chorus]
돌아보면 별일 아닌데
왜 이렇게 오래 남아

[Chorus]
밤이 지나면
우리도 흐려질까
아무 말 없이
서로를 놓친 걸까

[Bridge]
조금만 더 솔직했다면
다른 아침이 왔을까

[Outro]
(4마디 음원 (instrumental only))"""

TEST_OPTIONS = {
    "vocal_gender": "Female",
    "exclude_styles": [
        "sax lead", "strong sax", "drum fill-in", "tom fill",
        "snare roll", "trot", "enka", "EDM", "bleepy sounds", "toy percussion",
    ],
    "model": "chirp-v4",
    "instrumental": False,
    "weirdness": 35,
    "style_influence": 70,
}


# ─── Mock provider for CI ───────────────────────────────────────────────────

class MockLocalProvider:
    """Simulates LocalUnofficialSunoProvider for CI dry-run."""

    PROVIDER_NAME = "mock_local_dry_run"

    def create_song(self, title, style, lyrics, options=None):
        return "mock-task-001"

    def get_status(self, task_id):
        return {
            "status": "completed",
            "candidates": [
                {
                    "candidate_id": "A",
                    "suno_clip_id": "mock-clip-aaa",
                    "audio_url": None,
                    "wav_url": None,
                    "duration_seconds": 218.5,
                    "status": "completed",
                    "metadata": {"title": TEST_TITLE, "tags": TEST_STYLE[:60]},
                },
                {
                    "candidate_id": "B",
                    "suno_clip_id": "mock-clip-bbb",
                    "audio_url": None,
                    "wav_url": None,
                    "duration_seconds": 215.2,
                    "status": "completed",
                    "metadata": {"title": TEST_TITLE, "tags": TEST_STYLE[:60]},
                },
            ],
            "progress": 1.0,
            "error": None,
        }

    def download_wav(self, task_id, output_path):
        """Generate a mock WAV file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sr, dur, ch = 44100, 3.5, 2
        n = int(sr * dur)
        with wave.open(str(output_path), "wb") as wf:
            wf.setnchannels(ch)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(b"\x00" * n * ch * 2)
        return output_path

    def download_mp3_preview(self, task_id, output_path):
        return None


# ─── Dry-run runner ─────────────────────────────────────────────────────────

def run_dry_run(mock: bool = False) -> dict:
    """Run 1-song dry-run. Returns report dict."""
    ts = datetime.now(timezone.utc)
    date_str = ts.strftime("%Y-%m-%d")

    # Output folder
    base = Path(__file__).resolve().parent.parent / "outputs" / "dry_runs"
    out = base / f"{date_str}_suno_one_song"
    out.mkdir(parents=True, exist_ok=True)
    cands_dir = out / "candidates"
    cands_dir.mkdir(exist_ok=True)

    log_lines: list[str] = []

    def log(msg: str):
        entry = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
        log_lines.append(entry)
        print(entry)

    report = {
        "mode": "mock" if mock else "real",
        "started_at": ts.isoformat(),
        "title": TEST_TITLE,
        "style_excerpt": TEST_STYLE[:100] + "...",
        "lyrics_word_count": len(TEST_LYRICS.split()),
        "provider": "",
        "task_id": "",
        "status": "",
        "get_limit_result": None,
        "candidates": [],
        "wav_downloaded": False,
        "mp3_preview_downloaded": False,
        "manual_import_required": False,
        "errors": [],
        "fallback_recommendation": "",
        "completed_at": "",
    }

    # ── Select provider ─────────────────────────────────────────────────
    if mock:
        provider = MockLocalProvider()
        log("Mode: MOCK (no real Suno server)")
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from dotenv import load_dotenv
        load_dotenv()
        import os
        composer = os.getenv("COMPOSER_PROVIDER", "suno_cli").strip().lower()
        if composer in ("suno_cli", "cli"):
            from providers.suno.suno_cli_provider import SunoCliProvider
            provider = SunoCliProvider()
            log("Mode: REAL (SunoCliProvider — paperfoot/suno-cli)")
        elif composer in ("local", "local_unofficial"):
            from providers.suno.local_unofficial_suno import LocalUnofficialSunoProvider
            provider = LocalUnofficialSunoProvider()
            log("Mode: REAL (LocalUnofficialSunoProvider — gcui-art/suno-api)")
        else:
            from providers.suno.local_unofficial_suno import LocalUnofficialSunoProvider
            provider = LocalUnofficialSunoProvider()
            log(f"Mode: REAL (fallback to LocalUnofficialSunoProvider, COMPOSER_PROVIDER={composer})")

    report["provider"] = provider.PROVIDER_NAME

    # ── Step 0: Credit check (real mode only) ───────────────────────────
    if not mock and hasattr(provider, '_request'):
        try:
            limit = provider._request("GET", "/api/get_limit")
            report["get_limit_result"] = limit
            credits = limit.get("credits_left", "?")
            log(f"Credit check: {credits} credits remaining")
        except Exception as e:
            report["get_limit_result"] = {"error": str(e)}
            log(f"Credit check failed: {e}")
    elif mock:
        report["get_limit_result"] = {"credits_left": 9999, "mock": True}

    # ── Step 1: Submit ──────────────────────────────────────────────────
    log(f"Submitting: {TEST_TITLE}")
    try:
        task_id = provider.create_song(TEST_TITLE, TEST_STYLE, TEST_LYRICS, TEST_OPTIONS)
        report["task_id"] = task_id
        log(f"Task ID: {task_id}")
    except Exception as e:
        err_status = getattr(e, "status", "generation_failed")
        report["errors"].append(f"create_song: [{err_status}] {e}")
        report["status"] = err_status
        report["manual_import_required"] = err_status in (
            "captcha_required", "manual_import_required",
            "auth_required", "provider_unavailable",
        )
        if report["manual_import_required"]:
            report["fallback_recommendation"] = (
                "Download WAV manually from suno.com, "
                "then import via Song Generation tab → Manual WAV Import."
            )
            (out / "manual_import_required.txt").write_text(
                f"Generation failed: {err_status}\n"
                f"{report['fallback_recommendation']}\n",
                encoding="utf-8",
            )
        log(f"ERROR create_song: [{err_status}] {e}")
        _save_report(report, log_lines, out)
        return report

    # ── Step 2: Poll ────────────────────────────────────────────────────
    log("Polling status...")
    max_polls = 3 if mock else 60
    poll_interval = 0 if mock else 5

    for attempt in range(max_polls):
        try:
            status = provider.get_status(task_id)
            s = status.get("status", "unknown")
            progress = status.get("progress", 0)
            log(f"  Poll {attempt+1}: status={s} progress={progress:.0%}")

            if s == "completed":
                report["candidates"] = status.get("candidates", [])
                break
            if s == "failed":
                report["errors"].append("generation_failed")
                report["status"] = "generation_failed"
                log("ERROR: Generation failed")
                _save_report(report, log_lines, out)
                return report

            time.sleep(poll_interval)
        except Exception as e:
            report["errors"].append(f"polling: {type(e).__name__}: {e}")
            report["status"] = getattr(e, "status", "polling_timeout")
            log(f"ERROR polling: {e}")
            _save_report(report, log_lines, out)
            return report

    # ── Step 3: Download candidates ─────────────────────────────────────
    for cand in report["candidates"]:
        cid = cand.get("candidate_id", "X")
        clip_id = cand.get("suno_clip_id", task_id)
        log(f"Candidate {cid}: duration={cand.get('duration_seconds', '?')}s status={cand.get('status')}")

        # Try WAV
        wav_path = cands_dir / f"candidate_{cid}.wav"
        try:
            provider.download_wav(clip_id, wav_path)
            if wav_path.exists() and wav_path.stat().st_size > 100:
                report["wav_downloaded"] = True
                log(f"  WAV downloaded: {wav_path.name} ({wav_path.stat().st_size // 1024}KB)")
                continue
        except Exception as e:
            log(f"  WAV unavailable: {type(e).__name__}")

        # Try MP3 preview
        mp3_path = cands_dir / f"candidate_{cid}_preview.mp3"
        try:
            result = provider.download_mp3_preview(clip_id, mp3_path)
            if result and mp3_path.exists():
                report["mp3_preview_downloaded"] = True
                log(f"  MP3 preview: {mp3_path.name}")
            else:
                log(f"  MP3 preview also unavailable")
        except Exception:
            log(f"  MP3 preview also unavailable")

    # ── Step 4: Determine final status ──────────────────────────────────
    if report["wav_downloaded"]:
        report["status"] = "completed"
        report["fallback_recommendation"] = ""
        log("✅ Dry-run completed: WAV downloaded")
    elif report["mp3_preview_downloaded"]:
        report["status"] = "mp3_only_preview"
        report["manual_import_required"] = True
        log("⚠️ Dry-run completed: MP3 preview only — manual WAV import required")
        (out / "manual_import_required.txt").write_text(
            "WAV download was unavailable.\n"
            "Download WAV manually from suno.com and import via Song Generation tab.\n",
            encoding="utf-8",
        )
    else:
        report["status"] = "wav_download_unavailable"
        report["manual_import_required"] = True
        log("⚠️ Dry-run completed: no audio downloaded — manual import required")
        (out / "manual_import_required.txt").write_text(
            "Neither WAV nor MP3 was available for download.\n"
            "Download WAV manually from suno.com and import via Song Generation tab.\n",
            encoding="utf-8",
        )

    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    _save_report(report, log_lines, out)
    return report


def _save_report(report: dict, log_lines: list[str], out: Path):
    """Save report JSON and log text."""
    (out / "dry_run_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    (out / "dry_run_log.txt").write_text(
        "\n".join(log_lines), encoding="utf-8",
    )


# ─── CLI ────────────────────────────────────────────────────────────────────

def main():
    mock = "--mock" in sys.argv
    report = run_dry_run(mock=mock)
    print(f"\nReport: outputs/dry_runs/*/dry_run_report.json")
    print(f"Status: {report['status']}")
    sys.exit(0 if report["status"] in ("completed", "mp3_only_preview") else 1)


if __name__ == "__main__":
    main()
