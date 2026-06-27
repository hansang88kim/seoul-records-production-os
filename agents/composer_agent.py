"""
agents/composer_agent.py
─────────────────────────
ComposerAgent — orchestrates the full song generation flow for a single track:
  1. Generate prompt fields (title / style / lyrics)
  2. Submit to provider
  3. Poll status
  4. Download both candidates
  5. Apply candidate selection policy
  6. Save selected WAV as selected/suno_master.wav
  7. Write track_manifest.json + update project manifest
"""

from __future__ import annotations

import csv
import json
import time
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import (
    TARGET_DURATION_MIN_SEC,
    TARGET_DURATION_MAX_SEC,
)
from app.orchestrator import (
    append_log,
    save_manifest,
    update_track_status,
)
from providers.suno.base import ComposerProvider


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wav_duration(path: Path) -> float:
    try:
        with wave.open(str(path), "r") as wf:
            return wf.getnframes() / float(wf.getframerate())
    except Exception:
        return 0.0


# ─── Candidate selection policy ───────────────────────────────────────────────

def select_candidate(
    dur_a: float,
    dur_b: float,
    strict_duration: bool = True,
) -> tuple[str, list[str]]:
    """
    Apply the Seoul Records candidate selection policy.

    Returns:
        (selected: 'A' | 'B', qc_warnings: list[str])
    """
    min_s = TARGET_DURATION_MIN_SEC  # 210 s
    max_s = TARGET_DURATION_MAX_SEC  # 240 s
    warnings: list[str] = []

    a_in = min_s <= dur_a <= max_s
    b_in = min_s <= dur_b <= max_s

    if a_in and b_in:
        # Policy 1: both in range → pick longer
        selected = "A" if dur_a >= dur_b else "B"
    elif a_in:
        # Policy 2: only A in range
        selected = "A"
    elif b_in:
        # Policy 2: only B in range
        selected = "B"
    elif dur_a < min_s and dur_b < min_s:
        # Policy 3: both short → pick longer, add warning
        selected = "A" if dur_a >= dur_b else "B"
        warnings.append(
            f"QC WARNING: both candidates shorter than 3:30 "
            f"(A={dur_a:.1f}s, B={dur_b:.1f}s). Selected longer."
        )
    else:
        # Policy 4: both exceed 4:00
        if strict_duration:
            warnings.append(
                f"QC WARNING: both candidates exceed 4:00 "
                f"(A={dur_a:.1f}s, B={dur_b:.1f}s). Marking regeneration_required."
            )
            selected = "A" if dur_a <= dur_b else "B"  # pick shorter-over
        else:
            selected = "A" if dur_a >= dur_b else "B"
            warnings.append(
                f"INFO: both candidates exceed 4:00 "
                f"(A={dur_a:.1f}s, B={dur_b:.1f}s). strict_duration=False, selected longer."
            )

    return selected, warnings


# ─── ComposerAgent ────────────────────────────────────────────────────────────

class ComposerAgent:

    def __init__(
        self,
        provider: ComposerProvider,
        project_dir: Path,
        manifest: dict[str, Any],
        strict_duration: bool = True,
    ) -> None:
        self.provider = provider
        self.project_dir = project_dir
        self.manifest = manifest
        self.strict_duration = strict_duration
        self._song_base = project_dir / "01_suno_song_generation" / "songs"

    def _track_dir(self, track_index: int, title: str) -> Path:
        safe_title = "".join(c if c.isalnum() or c in "-_ " else "_" for c in title)[:40]
        folder_name = f"{track_index:02d}_{safe_title}"
        return self._song_base / folder_name

    def generate_track(
        self,
        track_index: int,
        title: str,
        style: str,
        lyrics: str,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Full generation pipeline for one track.
        Returns a result dict with paths, durations, selection, and QC warnings.
        """
        track_dir = self._track_dir(track_index, title)
        candidates_dir = track_dir / "candidates"
        selected_dir = track_dir / "selected"
        candidates_dir.mkdir(parents=True, exist_ok=True)
        selected_dir.mkdir(parents=True, exist_ok=True)

        # Save prompt files
        (track_dir / "title.txt").write_text(title, encoding="utf-8")
        (track_dir / "style.txt").write_text(style, encoding="utf-8")
        (track_dir / "lyrics.txt").write_text(lyrics, encoding="utf-8")

        # Update track status → submitted
        self.manifest = update_track_status(
            self.manifest, self.project_dir, track_index, "submitted_to_suno",
            extra={"title": title}
        )

        append_log(self.project_dir, "song_submit", {
            "track_index": track_index, "title": title
        })

        # Submit to provider
        task_id = self.provider.create_song(title, style, lyrics, options)

        self.manifest = update_track_status(
            self.manifest, self.project_dir, track_index, "suno_generating",
            extra={"task_id": task_id}
        )

        # Poll status
        for _ in range(30):
            status = self.provider.get_status(task_id)
            if status["status"] == "completed":
                break
            if status["status"] == "failed":
                self.manifest = update_track_status(
                    self.manifest, self.project_dir, track_index, "failed",
                    extra={"error": status.get("error")}
                )
                raise RuntimeError(f"Provider task failed: {status.get('error')}")
            time.sleep(1)
        else:
            raise TimeoutError(f"Provider task {task_id} timed out.")

        self.manifest = update_track_status(
            self.manifest, self.project_dir, track_index, "candidates_ready"
        )

        # Download candidates
        path_a = candidates_dir / "candidate_A.wav"
        path_b = candidates_dir / "candidate_B.wav"

        self.provider.download_wav(task_id, path_a)
        self.provider.download_wav(task_id, path_b)

        dur_a = _wav_duration(path_a)
        dur_b = _wav_duration(path_b)

        # Save candidate metadata
        meta = self.provider.get_metadata(task_id)
        for label, path, dur in [("A", path_a, dur_a), ("B", path_b, dur_b)]:
            (candidates_dir / f"candidate_{label}_metadata.json").write_text(
                json.dumps({
                    **meta,
                    "candidate": label,
                    "duration_sec": dur,
                    "path": str(path),
                }, indent=2, ensure_ascii=False)
            )

        # Selection
        selected_label, qc_warnings = select_candidate(dur_a, dur_b, self.strict_duration)
        selected_path = path_a if selected_label == "A" else path_b
        selected_dur = dur_a if selected_label == "A" else dur_b

        self.manifest = update_track_status(
            self.manifest, self.project_dir, track_index, "candidate_selected",
            extra={"selected_candidate": selected_label, "qc_warnings": qc_warnings}
        )

        # Copy selected → suno_master.wav
        master_path = selected_dir / "suno_master.wav"
        import shutil
        shutil.copy2(selected_path, master_path)

        # Write track_manifest.json
        needs_regen = any("regeneration_required" in w for w in qc_warnings)
        final_status = "regeneration_required" if needs_regen else "wav_qc_passed"

        track_manifest = {
            "track_index": track_index,
            "title": title,
            "style": style,
            "task_id": task_id,
            "provider": self.provider.get_capabilities()["provider_name"],
            "candidates": {
                "A": {"path": str(path_a), "duration_sec": dur_a},
                "B": {"path": str(path_b), "duration_sec": dur_b},
            },
            "selected_candidate": selected_label,
            "selected_path": str(master_path),
            "selected_duration_sec": selected_dur,
            "qc_warnings": qc_warnings,
            "distribution_eligible": master_path.exists() and selected_dur > 0,
            "mp3_only": False,
            "status": final_status,
            "created_at": _now_iso(),
        }
        (track_dir / "track_manifest.json").write_text(
            json.dumps(track_manifest, indent=2, ensure_ascii=False)
        )

        # Update project manifest track
        self.manifest = update_track_status(
            self.manifest, self.project_dir, track_index, final_status,
            extra={
                "wav_path": str(master_path),
                "duration_sec": selected_dur,
                "qc_warnings": qc_warnings,
                "selected_candidate": selected_label,
            }
        )

        append_log(self.project_dir, "track_completed", {
            "track_index": track_index,
            "title": title,
            "selected": selected_label,
            "duration_sec": selected_dur,
            "qc_warnings": qc_warnings,
        })

        # Update song_list.csv
        self._update_song_list_csv(track_index, title, style, selected_dur, final_status, master_path)

        return track_manifest

    def _update_song_list_csv(
        self,
        track_index: int,
        title: str,
        style: str,
        duration_sec: float,
        status: str,
        wav_path: Path,
    ) -> None:
        csv_path = self.project_dir / "01_suno_song_generation" / "song_list.csv"
        rows: list[dict] = []

        if csv_path.exists():
            with csv_path.open("r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

        # Update or insert
        existing = next((r for r in rows if r.get("track_index") == str(track_index)), None)
        entry = {
            "track_index": track_index,
            "title": title,
            "style": style,
            "duration_sec": f"{duration_sec:.1f}",
            "status": status,
            "wav_path": str(wav_path),
            "updated_at": _now_iso(),
        }
        if existing:
            existing.update(entry)
        else:
            rows.append(entry)

        fieldnames = ["track_index", "title", "style", "duration_sec", "status", "wav_path", "updated_at"]
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
