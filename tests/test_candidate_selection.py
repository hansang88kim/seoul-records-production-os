"""
Tests for candidate selection policy (v0.1.1).
Covers all 5 policy cases including regeneration_required for both-long.
"""
import pytest
from agents.qc_agent import select_best_candidate, CandidateSelectionResult

# Target: 3:30 (210s) – 4:00 (240s)


def make_cand(cid: str, duration: float) -> dict:
    return {"candidate_id": cid, "duration_seconds": duration}


def test_both_in_range_select_longer():
    """Case 1: both in range → longer one selected, no warnings, save_wav True."""
    result = select_best_candidate([make_cand("A", 220), make_cand("B", 235)])
    assert result.candidate_id == "B"
    assert not result.qc_warnings
    assert result.save_wav is True
    assert result.regeneration_required is False


def test_one_in_range_select_it():
    """Case 2: one in range → select that one regardless of the other."""
    result = select_best_candidate([make_cand("A", 200), make_cand("B", 225)])
    assert result.candidate_id == "B"
    assert not result.qc_warnings
    assert result.save_wav is True


def test_both_short_select_longer_with_warning():
    """Case 3: both short → select longer, add qc_warning_both_short, still save."""
    result = select_best_candidate([make_cand("A", 180), make_cand("B", 195)])
    assert result.candidate_id == "B"
    assert "qc_warning_both_short" in result.qc_warnings
    assert result.save_wav is True
    assert result.regeneration_required is False


def test_both_long_strict_sets_regeneration_required():
    """Case 4 (strict=True): both exceed 4:00 → REGENERATION_REQUIRED, do NOT save WAV."""
    result = select_best_candidate(
        [make_cand("A", 250), make_cand("B", 260)],
        strict_duration=True,
    )
    assert result.regeneration_required is True
    assert result.save_wav is False
    assert "regeneration_required_both_long" in result.qc_warnings


def test_both_long_strict_false_saves_wav():
    """Case 4 (strict=False): both exceed 4:00 but strict disabled → warn and save."""
    result = select_best_candidate(
        [make_cand("A", 250), make_cand("B", 260)],
        strict_duration=False,
    )
    assert result.regeneration_required is False
    assert result.save_wav is True
    assert "qc_warning_both_long_strict_disabled" in result.qc_warnings


def test_boundary_values_included_in_range():
    """Boundary: exactly 210 s and 240 s are in range."""
    result = select_best_candidate([make_cand("A", 210), make_cand("B", 240)])
    assert result.candidate_id == "B"
    assert not result.qc_warnings
    assert result.save_wav is True


def test_mixed_short_and_long():
    """Case 5: one short, one long → select longer, warn."""
    result = select_best_candidate([make_cand("A", 180), make_cand("B", 260)])
    assert result.candidate_id == "B"
    assert "qc_warning_duration_out_of_range" in result.qc_warnings
    assert result.save_wav is True


def test_returns_candidate_selection_result():
    """Return type must be CandidateSelectionResult."""
    result = select_best_candidate([make_cand("A", 220), make_cand("B", 225)])
    assert isinstance(result, CandidateSelectionResult)
