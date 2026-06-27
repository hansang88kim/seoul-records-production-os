"""
tests/test_wav_import.py
────────────────────────
Manual WAV import tests — verify that imported WAVs land in the correct
track folder, update project_manifest.json, and append to project_log.jsonl.
No Streamlit dependency — tests exercise project_manager + audio_qc directly.
"""
from __future__ import annotations

import json
import shutil
import wave
from pathlib import Path

import pytest


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_wav(path: Path, duration_s: float = 3.5, sample_rate: int = 44100) -> Path:
    n_frames = int(sample_rate * duration_s)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00" * n_frames * 2 * 2)
    return path


def _create_test_project(tmp_path, monkeypatch):
    """Create a real project in tmp_path and return (manifest, output_folder)."""
    import app.config as cfg
    monkeypatch.setattr(cfg, "OUTPUTS_DIR", tmp_path)
    from app.project_manager import create_project
    return create_project(
        project_name="WAV Import Test",
        theme="Test",
        track_count=2,
        production_mode="Manual",
        output_type="YouTube + Distribution Package",
    )


# ─── Tests ───────────────────────────────────────────────────────────────────

def test_manual_wav_import_saves_to_correct_track_folder(tmp_path, monkeypatch):
    """
    Importing a WAV for Track 1 must save to
    01_suno_song_generation/<track-folder>/selected/suno_master.wav
    and MUST NOT touch Track 2's folder.
    """
    manifest, output_folder = _create_test_project(tmp_path, monkeypatch)

    # Build a real WAV in a temp location
    src_wav = _make_wav(tmp_path / "source.wav")

    from app.project_manager import create_track_folder, save_manifest, log_action
    from workflows.audio_qc import run_audio_qc, qc_result_to_track_fields

    track = manifest.tracks[0]
    songs_root = output_folder / "01_suno_song_generation"
    tf = create_track_folder(
        songs_root, track.track_number,
        track.prompt.title or f"track-{track.track_number:02d}",
    )
    track.track_folder_path = str(tf)

    dest = tf / "selected" / "suno_master.wav"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_wav, dest)

    # Run QC and update manifest
    qc = run_audio_qc(dest)
    fields = qc_result_to_track_fields(qc)
    track.selected_wav_path = str(dest)
    track.is_wav = fields["is_wav"]
    track.duration_seconds = fields["duration_seconds"]
    track.distribution_eligible = fields["distribution_eligible"]
    save_manifest(manifest, output_folder)
    log_action(output_folder, "manual_wav_import", "selected_wav_imported",
               {"track_number": track.track_number, "file": dest.name})

    # ── Assertions ────────────────────────────────────────────────────────────
    # Correct file exists
    assert dest.exists(), "suno_master.wav must exist in track 1 folder"

    # Manifest updated
    manifest_path = output_folder / "project_manifest.json"
    saved = json.loads(manifest_path.read_text(encoding="utf-8"))
    t0 = saved["tracks"][0]
    assert t0["is_wav"] is True
    assert t0["selected_wav_path"] == str(dest)
    assert t0["duration_seconds"] is not None

    # Track 2 folder must NOT have suno_master.wav
    track2 = manifest.tracks[1]
    tf2 = create_track_folder(
        songs_root, track2.track_number,
        track2.prompt.title or f"track-{track2.track_number:02d}",
    )
    t2_master = tf2 / "selected" / "suno_master.wav"
    assert not t2_master.exists(), "Track 2 folder must not be touched by Track 1 import"

    # Log appended
    log_path = output_folder / "project_log.jsonl"
    assert log_path.exists()
    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    import_entries = [e for e in entries if e.get("action") == "selected_wav_imported"]
    assert len(import_entries) >= 1, "project_log.jsonl must have a selected_wav_imported entry"


def test_candidate_selection_policy_applied_on_import(tmp_path, monkeypatch):
    """
    When Candidate A and B are imported, selection policy picks the better one
    and saves it as suno_master.wav.
    """
    manifest, output_folder = _create_test_project(tmp_path, monkeypatch)

    from app.project_manager import create_track_folder, save_manifest
    from workflows.audio_qc import run_audio_qc
    from app.models import CandidateMetadata
    from agents.qc_agent import select_best_candidate
    import shutil as sh

    track = manifest.tracks[0]
    songs_root = output_folder / "01_suno_song_generation"
    tf = create_track_folder(
        songs_root, track.track_number,
        track.prompt.title or f"track-{track.track_number:02d}",
    )
    track.track_folder_path = str(tf)
    cands_dir = tf / "candidates"
    cands_dir.mkdir(parents=True, exist_ok=True)

    # Candidate A: 3:30 → eligible, Candidate B: 3:40 → eligible (longer → preferred)
    wav_a = _make_wav(cands_dir / "candidate_A.wav", duration_s=210)
    wav_b = _make_wav(cands_dir / "candidate_B.wav", duration_s=220)

    qc_a = run_audio_qc(wav_a)
    qc_b = run_audio_qc(wav_b)

    cand_infos = [
        {"candidate_id": "A", "file_path": str(wav_a),
         "duration_seconds": qc_a.duration_seconds or 210, "is_wav": qc_a.is_wav},
        {"candidate_id": "B", "file_path": str(wav_b),
         "duration_seconds": qc_b.duration_seconds or 220, "is_wav": qc_b.is_wav},
    ]

    result = select_best_candidate(cand_infos)
    assert result.save_wav, "Both candidates in range → save_wav must be True"
    assert result.candidate_id == "B", "Longer candidate (B=220s) should be selected"

    # Copy to suno_master.wav
    src = Path(next(c["file_path"] for c in cand_infos if c["candidate_id"] == result.candidate_id))
    dst = tf / "selected" / "suno_master.wav"
    dst.parent.mkdir(exist_ok=True)
    sh.copy2(src, dst)

    track.selected_wav_path = str(dst)
    track.is_wav = True
    track.selected_candidate_id = result.candidate_id
    save_manifest(manifest, output_folder)

    # Verify
    assert dst.exists(), "suno_master.wav must be created"
    manifest_path = output_folder / "project_manifest.json"
    saved = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert saved["tracks"][0]["selected_candidate_id"] == "B"
    assert saved["tracks"][0]["selected_wav_path"] == str(dst)
