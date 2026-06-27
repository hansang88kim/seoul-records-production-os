"""
Seoul Records Production OS — QC Agent
Validates tracks, visuals, video, and distribution packages.
"""
from __future__ import annotations
from pathlib import Path
from app.models import TrackManifest, VisualManifest, VideoManifest, DistributionManifest
from app.config import TARGET_DURATION_MIN_SECONDS, TARGET_DURATION_MAX_SECONDS


# ─── Creative QC ──────────────────────────────────────────────────────────────

def qc_track_creative(track: TrackManifest) -> list[str]:
    """Check that all prompt fields are populated."""
    warnings = []
    p = track.prompt
    if not p.title:
        warnings.append("title_missing")
    if not p.style:
        warnings.append("style_missing")
    if not p.lyrics:
        warnings.append("lyrics_missing")
    if not p.vocal_gender:
        warnings.append("vocal_gender_missing")
    if not p.exclude_styles:
        warnings.append("exclude_styles_missing")
    return warnings


# ─── Audio QC ─────────────────────────────────────────────────────────────────

def qc_track_audio(track: TrackManifest) -> list[str]:
    """Check WAV integrity and distribution eligibility."""
    warnings = []
    if not track.selected_wav_path:
        warnings.append("wav_path_missing")
        return warnings
    wav_path = Path(track.selected_wav_path)
    if not wav_path.exists():
        warnings.append("wav_file_not_found")
        return warnings
    if not track.is_wav:
        warnings.append("not_wav_format")
    dur = track.duration_seconds
    if dur is None:
        warnings.append("duration_unknown")
    elif dur < TARGET_DURATION_MIN_SECONDS:
        warnings.append(f"duration_too_short_{dur:.0f}s")
    elif dur > TARGET_DURATION_MAX_SECONDS:
        warnings.append(f"duration_too_long_{dur:.0f}s")
    return warnings


# ─── Candidate Selection ──────────────────────────────────────────────────────

class CandidateSelectionResult:
    """
    Structured result from select_best_candidate().

    Attributes:
        candidate_id    — "A" or "B" (the selected candidate)
        qc_warnings     — list of warning strings
        regeneration_required — True when BOTH candidates exceed 4:00 (strict policy)
        save_wav        — False when regeneration_required; caller must NOT save WAV
    """
    __slots__ = ("candidate_id", "qc_warnings", "regeneration_required", "save_wav")

    def __init__(
        self,
        candidate_id: str,
        qc_warnings: list[str],
        regeneration_required: bool,
        save_wav: bool,
    ) -> None:
        self.candidate_id = candidate_id
        self.qc_warnings = qc_warnings
        self.regeneration_required = regeneration_required
        self.save_wav = save_wav


def select_best_candidate(
    candidates: list[dict],
    strict_duration: bool = True,
) -> CandidateSelectionResult:
    """
    Apply Seoul Records candidate selection policy.

    Target range: 3:30 (210 s) – 4:00 (240 s).

    Policy:
      1. Both in range             → select longer, save WAV ✅
      2. One in range              → select that one, save WAV ✅
      3. Both shorter than 3:30    → select longer, warn, save WAV ⚠️
      4. Both exceed 4:00          → if strict_duration=True:
                                       set regeneration_required, DO NOT save WAV ❌
                                     if strict_duration=False:
                                       select longer, warn, save WAV ⚠️
      5. Mixed (one short, one long) → select longer, warn, save WAV ⚠️

    Returns CandidateSelectionResult with save_wav=False on case 4 (strict).
    """
    low = TARGET_DURATION_MIN_SECONDS    # 210
    high = TARGET_DURATION_MAX_SECONDS   # 240

    def dur(c: dict) -> float:
        return c.get("duration_seconds") or 0.0

    in_range = [c for c in candidates if low <= dur(c) <= high]
    short    = [c for c in candidates if dur(c) < low]
    long_    = [c for c in candidates if dur(c) > high]

    warnings: list[str] = []
    regen = False
    save = True

    if len(in_range) >= 2:
        # Case 1 — both in range, pick longer
        best = max(in_range, key=dur)

    elif len(in_range) == 1:
        # Case 2 — one in range
        best = in_range[0]

    elif short and not long_:
        # Case 3 — both short
        best = max(short, key=dur)
        warnings.append("qc_warning_both_short")

    elif long_ and not short:
        # Case 4 — both long
        best = max(long_, key=dur)
        if strict_duration:
            warnings.append("regeneration_required_both_long")
            regen = True
            save = False
        else:
            warnings.append("qc_warning_both_long_strict_disabled")

    else:
        # Case 5 — mixed (short + long)
        best = max(candidates, key=dur)
        warnings.append("qc_warning_duration_out_of_range")

    return CandidateSelectionResult(
        candidate_id=best["candidate_id"],
        qc_warnings=warnings,
        regeneration_required=regen,
        save_wav=save,
    )


# ─── Visual QC ────────────────────────────────────────────────────────────────

def qc_visual(visual: VisualManifest) -> list[str]:
    warnings = []
    if not visual.youtube_thumbnail_path:
        warnings.append("youtube_thumbnail_missing")
    elif not Path(visual.youtube_thumbnail_path).exists():
        warnings.append("youtube_thumbnail_file_not_found")
    if not visual.dsp_cover_path:
        warnings.append("dsp_cover_missing")
    elif not Path(visual.dsp_cover_path).exists():
        warnings.append("dsp_cover_file_not_found")
    if not visual.youtube_thumbnail_16x9:
        warnings.append("thumbnail_not_16x9")
    if not visual.dsp_cover_1x1:
        warnings.append("cover_not_1x1")
    return warnings


# ─── Distribution QC ─────────────────────────────────────────────────────────

def qc_distribution(dist: DistributionManifest, tracks: list[TrackManifest]) -> list[str]:
    warnings = []
    eligible = [t for t in tracks if t.is_wav and t.selected_wav_path]
    if not eligible:
        warnings.append("no_wav_masters_found")
    mp3_only = [t for t in tracks if not t.is_wav and t.selected_wav_path]
    if mp3_only:
        warnings.append(f"mp3_only_tracks_count_{len(mp3_only)}_distribution_blocked")
    if not dist.cover_ready:
        warnings.append("cover_not_ready")
    if not dist.metadata_ready:
        warnings.append("metadata_not_ready")
    if not dist.rights_statements_ready:
        warnings.append("rights_statements_missing")
    return warnings
