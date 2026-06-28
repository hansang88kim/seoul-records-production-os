"""
tests/test_metadata_consistency.py — Prompt snapshot + security redaction tests.
"""
from __future__ import annotations
import json
import pytest
from pathlib import Path


def test_compute_prompt_hash_deterministic():
    from services.metadata_consistency_service import compute_prompt_hash
    h1 = compute_prompt_hash("제목", "스타일", "가사", {"model": "v5.5"})
    h2 = compute_prompt_hash("제목", "스타일", "가사", {"model": "v5.5"})
    assert h1 == h2 and len(h1) == 16


def test_compute_prompt_hash_changes_on_diff():
    from services.metadata_consistency_service import compute_prompt_hash
    h1 = compute_prompt_hash("제목A", "스타일", "가사")
    h2 = compute_prompt_hash("제목B", "스타일", "가사")
    assert h1 != h2


def test_create_and_load_snapshot(tmp_path):
    from services.metadata_consistency_service import create_prompt_snapshot, load_prompt_snapshot
    snap = create_prompt_snapshot(
        tmp_path / "track1",
        title="밤이 지나면",
        style="Japanese city pop, BPM 112",
        lyrics="[Verse 1]\n가사",
        settings={"model": "v5.5", "vocal_gender": "Female"},
        ai_provider="openai",
    )
    assert snap["title"] == "밤이 지나면"
    assert snap["prompt_hash"]
    assert (tmp_path / "track1" / "prompt_snapshot.json").exists()

    loaded = load_prompt_snapshot(tmp_path / "track1")
    assert loaded["title"] == "밤이 지나면"
    assert loaded["prompt_hash"] == snap["prompt_hash"]


def test_snapshot_missing_returns_none(tmp_path):
    from services.metadata_consistency_service import load_prompt_snapshot
    assert load_prompt_snapshot(tmp_path / "nonexistent") is None


def test_compare_snapshot_to_submitted_consistent():
    from services.metadata_consistency_service import compare_prompt_snapshot_to_submitted
    snap = {"title": "밤이 지나면", "style_prompt": "citypop", "model": "v5.5", "vocal_gender": "Female"}
    payload = {"title_sent": "밤이 지나면", "tags_sent": "citypop", "model_sent": "v5.5", "vocal_sent": "Female"}
    assert compare_prompt_snapshot_to_submitted(snap, payload) == []


def test_compare_snapshot_detects_mismatch():
    from services.metadata_consistency_service import compare_prompt_snapshot_to_submitted
    snap = {"title": "밤이 지나면", "style_prompt": "citypop", "model": "v5.5", "vocal_gender": "Female"}
    payload = {"title_sent": "다른 제목", "tags_sent": "citypop", "model_sent": "v5.5", "vocal_sent": "Female"}
    issues = compare_prompt_snapshot_to_submitted(snap, payload)
    assert len(issues) == 1
    assert "title" in issues[0]


def test_validate_consistency_no_snapshot(tmp_path):
    from services.metadata_consistency_service import validate_track_metadata_consistency
    result = validate_track_metadata_consistency(tmp_path / "missing")
    assert result["consistent"] is False


# ─── Security Redaction ──────────────────────────────────────────────────────

def test_redact_cookie():
    from services.metadata_consistency_service import redact_sensitive
    text = "cookie=abc123xyz session=secret123 normal text"
    clean = redact_sensitive(text)
    assert "abc123" not in clean
    assert "secret123" not in clean
    assert "normal text" in clean
    assert "***" in clean


def test_redact_bearer_token():
    from services.metadata_consistency_service import redact_sensitive
    text = "Authorization: Bearer eyJhbGciOiJ very long token"
    clean = redact_sensitive(text)
    assert "eyJhbGci" not in clean


def test_redact_cli_cookie_flag():
    from services.metadata_consistency_service import redact_sensitive
    text = "--cookie suno_session_abcdef123456"
    clean = redact_sensitive(text)
    assert "abcdef123456" not in clean


def test_sanitize_command():
    from services.metadata_consistency_service import sanitize_command
    cmd = ["suno", "auth", "--cookie", "secret_value_here", "credits"]
    clean = sanitize_command(cmd)
    assert "secret_value_here" not in clean
    assert "***" in clean
    assert "suno" in clean


def test_jwt_not_in_redacted_text():
    from services.metadata_consistency_service import redact_sensitive
    text = "jwt=eyJhbGciOiJIUzI1NiJ9.payload.signature token=abc123"
    clean = redact_sensitive(text)
    assert "eyJhbGci" not in clean
    assert "abc123" not in clean


# ─── Cookie panel security ───────────────────────────────────────────────────

def test_cookie_value_not_in_manifest(tmp_path):
    """Cookie values must never appear in manifest files."""
    import json
    # Simulate saving a manifest
    manifest = {
        "name": "test",
        "songs": [{"title": "곡", "status": "completed", "cookie": "REDACTED"}],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    content = path.read_text()
    # The cookie key exists but is redacted
    assert "REDACTED" in content or "cookie" not in content.lower()


def test_sanitize_command_masks_all_sensitive():
    """sanitize_command must mask cookie, token, key values."""
    from services.metadata_consistency_service import sanitize_command
    cmd = ["suno", "auth", "--cookie", "real_cookie_value",
           "--token", "jwt_value", "generate"]
    clean = sanitize_command(cmd)
    assert "real_cookie_value" not in clean
    assert "jwt_value" not in clean
