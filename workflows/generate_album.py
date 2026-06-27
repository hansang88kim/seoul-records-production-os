"""
Seoul Records Production OS — Album Generation Workflow
Handles track generation, candidate download, selection, and saving.
"""
from __future__ import annotations

import csv
import json
import io
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.models import ProjectManifest, TrackManifest, CandidateMetadata
from app.state_machine import TrackStatus, ProjectStatus
from app.project_manager import save_manifest, log_action, create_track_folder
from agents.producer_agent import generate_song_prompt
from agents.qc_agent import select_best_candidate, qc_track_audio
from providers.suno import get_composer_provider   # ← single registry
from app.config import COMPOSER_PROVIDER


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_song_generation(
    manifest: ProjectManifest,
    output_folder: Path,
    track: TrackManifest,
    provider_name: str | None = None,
) -> TrackManifest:
    """
    Execute the full generation flow for a single track.

    Steps:
      1. Write prompt files
      2. Submit to provider
      3. Download both WAV candidates
      4. Run candidate selection policy
      5. If save_wav=True: copy selected WAV, run audio QC, mark SAVED
         If save_wav=False (both-long, strict): mark REGENERATION_REQUIRED
      6. Update manifest + log
    """
    provider_name = provider_name or COMPOSER_PROVIDER
    provider = get_composer_provider(provider_name)
    p = track.prompt
    songs_root = output_folder / "01_suno_song_generation"
    track_folder = create_track_folder(
        songs_root, track.track_number, p.title or f"track-{track.track_number:02d}"
    )
    track.track_folder_path = str(track_folder)

    # Write prompt files
    (track_folder / "title.txt").write_text(p.title, encoding="utf-8")
    (track_folder / "style.txt").write_text(p.style, encoding="utf-8")
    (track_folder / "lyrics.txt").write_text(p.lyrics, encoding="utf-8")
    # exclude_styles is list[str] — join for human-readable text file
    (track_folder / "exclude_styles.txt").write_text(
        ", ".join(p.exclude_styles), encoding="utf-8"
    )

    log_action(
        output_folder, "song_generation", "submitting_to_provider",
        {"track_id": track.track_id, "provider": provider_name, "title": p.title},
        track_id=track.track_id, project_id=manifest.project_id,
    )

    # Submit
    track.update_status(TrackStatus.SUBMITTED_TO_SUNO)
    task_id = provider.create_song(p.title, p.style, p.lyrics, {
        "vocal_gender": p.vocal_gender,
        "weirdness": p.weirdness,
        "style_influence": p.style_influence,
        "instrumental": p.instrumental,
        "model": p.model,
    })
    track.task_id = task_id
    track.update_status(TrackStatus.SUNO_GENERATING)
    save_manifest(manifest, output_folder)

    # Poll (mock: immediate)
    provider.get_status(task_id)
    candidates_folder = track_folder / "candidates"
    candidates_folder.mkdir(exist_ok=True)

    # Download both candidates
    if hasattr(provider, "download_candidates"):
        candidates_info = provider.download_candidates(task_id, candidates_folder)
    else:
        candidates_info = []

    track.candidates = []
    for info in candidates_info:
        cand = CandidateMetadata(
            candidate_id=info["candidate_id"],
            task_id=task_id,
            file_path=info.get("file_path"),
            duration_seconds=info.get("duration_seconds"),
            sample_rate=info.get("sample_rate"),
            channels=info.get("channels"),
            bit_depth=info.get("bit_depth"),
            file_format=info.get("file_format", "wav"),
            is_wav=info.get("is_wav", True),
            provider=provider_name,
        )
        track.candidates.append(cand)

    track.update_status(TrackStatus.CANDIDATES_READY)
    save_manifest(manifest, output_folder)

    if not candidates_info:
        track.update_status(TrackStatus.FAILED)
        log_action(output_folder, "song_generation", "no_candidates",
                   {"track_id": track.track_id}, level="ERROR",
                   track_id=track.track_id)
        save_manifest(manifest, output_folder)
        return track

    # ── Candidate Selection (Fix 4) ───────────────────────────────────────────
    result = select_best_candidate(candidates_info)
    track.selected_candidate_id = result.candidate_id
    track.qc_warnings.extend(result.qc_warnings)
    track.update_status(TrackStatus.CANDIDATE_SELECTED)

    if result.regeneration_required:
        # Both candidates exceed 4:00 and strict_duration=True
        # Do NOT copy WAV, do NOT mark distribution_eligible
        track.update_status(TrackStatus.REGENERATION_REQUIRED)
        track.distribution_eligible = False
        log_action(
            output_folder, "song_generation", "regeneration_required",
            {"track_id": track.track_id, "warnings": result.qc_warnings,
             "candidate_A_dur": next((c["duration_seconds"] for c in candidates_info if c["candidate_id"] == "A"), None),
             "candidate_B_dur": next((c["duration_seconds"] for c in candidates_info if c["candidate_id"] == "B"), None)},
            level="WARNING", track_id=track.track_id, project_id=manifest.project_id,
        )
        save_manifest(manifest, output_folder)
        return track

    # ── Copy selected WAV ─────────────────────────────────────────────────────
    selected_folder = track_folder / "selected"
    selected_folder.mkdir(exist_ok=True)
    src = candidates_folder / f"candidate_{result.candidate_id}.wav"
    dst = selected_folder / "suno_master.wav"

    if src.exists():
        shutil.copy2(src, dst)
        track.selected_wav_path = str(dst)
        track.is_wav = True

        best_info = next(
            (c for c in candidates_info if c["candidate_id"] == result.candidate_id), {}
        )
        track.duration_seconds = best_info.get("duration_seconds")
        track.distribution_eligible = track.is_wav
        track.update_status(TrackStatus.WAV_DOWNLOADED)

        # Audio QC
        audio_warnings = qc_track_audio(track)
        track.qc_warnings.extend(audio_warnings)
        if not audio_warnings:
            track.update_status(TrackStatus.WAV_QC_PASSED)

        # Write track metadata
        meta = {
            "track_number": track.track_number,
            "track_id": track.track_id,
            "title": p.title,
            "style": p.style,
            "exclude_styles": p.exclude_styles,    # stored as list
            "duration_seconds": track.duration_seconds,
            "selected_candidate": result.candidate_id,
            "wav_path": str(dst),
            "is_wav": track.is_wav,
            "qc_warnings": track.qc_warnings,
            "created_at": _now(),
        }
        (selected_folder / "track_metadata.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )
        (track_folder / "track_manifest.json").write_text(
            track.model_dump_json(indent=2), encoding="utf-8"
        )

        track.update_status(TrackStatus.SAVED)
        log_action(
            output_folder, "song_generation", "track_saved",
            {"track_id": track.track_id, "selected": result.candidate_id,
             "duration": track.duration_seconds, "warnings": result.qc_warnings},
            track_id=track.track_id, project_id=manifest.project_id,
        )
    else:
        track.update_status(TrackStatus.FAILED)
        log_action(output_folder, "song_generation", "wav_not_found",
                   {"track_id": track.track_id}, level="ERROR",
                   track_id=track.track_id)

    save_manifest(manifest, output_folder)
    return track


def update_song_list_csv(manifest: ProjectManifest, output_folder: Path) -> None:
    """
    Regenerate song_list.csv from current track states.
    Uses csv module — no manual comma concatenation.
    """
    songs_root = output_folder / "01_suno_song_generation"
    songs_root.mkdir(exist_ok=True)

    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["#", "Title", "Style", "Duration", "Status", "WAV", "QC Warnings"])

    for t in manifest.tracks:
        dur = f"{t.duration_seconds:.1f}s" if t.duration_seconds else ""
        wav = "yes" if t.is_wav else "no"
        warns = "; ".join(t.qc_warnings) if t.qc_warnings else ""
        # exclude_styles is list[str] — join for display
        style_display = t.prompt.style[:40] if t.prompt.style else ""
        writer.writerow([
            t.track_number,
            t.prompt.title or "",
            style_display,
            dur,
            t.status,
            wav,
            warns,
        ])

    (songs_root / "song_list.csv").write_text(buf.getvalue(), encoding="utf-8")
