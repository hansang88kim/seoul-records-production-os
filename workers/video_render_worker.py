"""
workers/video_render_worker.py — Background video render worker (v0.7.3).

Runs the full FFmpeg render as a separate process so the Streamlit UI never
blocks on a 60-70 min encode. Parses FFmpeg `-progress pipe:1` output and
writes progress to the render job store (render_state.json + ffmpeg_progress.jsonl).

Usage: python -m workers.video_render_worker <render_job_id>
The command is read from the job's command_sanitized.txt (the full arg list is
also stored as command.json next to it by the launcher).
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _parse_progress_block(lines: list[str]) -> dict:
    """Parse a block of FFmpeg -progress key=value lines into a dict."""
    d = {}
    for ln in lines:
        if "=" in ln:
            k, _, v = ln.partition("=")
            d[k.strip()] = v.strip()
    return d


def run_render_job(render_job_id: str):
    import subprocess
    from services.video.render_job_store import (
        load_render_state, update_render_state, append_log, append_progress, _job_path,
    )

    state = load_render_state(render_job_id)
    if not state:
        print(f"No render job {render_job_id}")
        return

    jd = _job_path(render_job_id)
    cmd_json = jd / "command.json"
    if cmd_json.exists():
        command = json.loads(cmd_json.read_text(encoding="utf-8"))
    else:
        # Fallback: split the sanitized command (less robust)
        command = (jd / "command_sanitized.txt").read_text(encoding="utf-8").split()

    total = state.get("total_seconds", 0) or 0
    output_path = state.get("output_path", "")

    update_render_state(render_job_id, status="running",
                        started_at=datetime.now(timezone.utc).isoformat(),
                        last_message="렌더링 시작")
    append_log(render_job_id, f"FFmpeg 렌더 시작 — 목표 {int(total)}초")

    start = time.time()
    try:
        proc = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        update_render_state(render_job_id, pid=proc.pid)

        block: list[str] = []
        for line in proc.stdout:
            line = line.rstrip("\n")
            block.append(line)
            # FFmpeg -progress emits 'progress=continue' / 'progress=end' at block end
            if line.startswith("progress="):
                rec = _parse_progress_block(block)
                block = []
                append_progress(render_job_id, rec)

                # out_time_ms / out_time_us → seconds
                cur = 0.0
                if "out_time_ms" in rec:
                    try:
                        cur = float(rec["out_time_ms"]) / 1_000_000.0
                    except Exception:
                        cur = 0.0
                elif "out_time_us" in rec:
                    try:
                        cur = float(rec["out_time_us"]) / 1_000_000.0
                    except Exception:
                        cur = 0.0

                elapsed = time.time() - start
                pct = min(100.0, (cur / total * 100.0)) if total else 0.0
                speed = rec.get("speed", "")
                # ETA from speed
                eta = None
                try:
                    spd = float(speed.rstrip("x")) if speed.endswith("x") else None
                    if spd and spd > 0 and total:
                        remaining_render_secs = (total - cur) / spd
                        eta = max(0.0, remaining_render_secs)
                except Exception:
                    eta = None

                update_render_state(
                    render_job_id,
                    progress_percent=round(pct, 1),
                    current_time_sec=round(cur, 1),
                    elapsed_sec=round(elapsed, 1),
                    speed=speed,
                    eta_sec=round(eta, 1) if eta is not None else None,
                    last_message=f"렌더링 중 {pct:.0f}%",
                )

        proc.wait()
        if proc.returncode == 0 and Path(output_path).exists():
            update_render_state(
                render_job_id, status="completed", progress_percent=100.0,
                finished_at=datetime.now(timezone.utc).isoformat(),
                last_message="렌더링 완료",
            )
            append_log(render_job_id, f"완료 → {output_path}")
        else:
            update_render_state(
                render_job_id, status="failed",
                finished_at=datetime.now(timezone.utc).isoformat(),
                last_message=f"렌더 실패 (exit {proc.returncode})",
            )
            append_log(render_job_id, f"실패: exit code {proc.returncode}", "error")

    except Exception as e:
        update_render_state(
            render_job_id, status="failed",
            finished_at=datetime.now(timezone.utc).isoformat(),
            last_message=f"오류: {e}",
        )
        append_log(render_job_id, f"예외: {e}", "error")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m workers.video_render_worker <render_job_id>")
        sys.exit(1)
    run_render_job(sys.argv[1])
