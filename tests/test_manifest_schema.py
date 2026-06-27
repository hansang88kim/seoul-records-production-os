"""
Tests for manifest schema and Pydantic model correctness (v0.1.1).
Includes: exclude_styles list serialization, status updates, roundtrip.
"""
import json
import pytest
from app.models import ProjectManifest, TrackManifest, TrackPrompt
from app.state_machine import ProjectStatus, TrackStatus


def test_project_manifest_defaults():
    m = ProjectManifest(project_id="test-id", project_name="Test")
    assert m.status == ProjectStatus.PROJECT_CREATED
    assert m.core_style == "Seoul Records City Pop Core"
    assert m.track_count == 5
    from app.config import APP_VERSION
    assert m.app_version == APP_VERSION


def test_track_status_update():
    t = TrackManifest(track_number=1, track_id="t1")
    t.update_status(TrackStatus.PROMPT_READY)
    assert t.status == TrackStatus.PROMPT_READY


def test_project_status_update():
    m = ProjectManifest(project_id="x", project_name="X")
    m.update_status(ProjectStatus.SONG_GENERATION_IN_PROGRESS)
    assert m.status == ProjectStatus.SONG_GENERATION_IN_PROGRESS


def test_exclude_styles_is_list():
    """Fix 3: exclude_styles must be list[str], not str."""
    p = TrackPrompt()
    assert isinstance(p.exclude_styles, list)


def test_exclude_styles_stored_as_list_in_manifest():
    """Fix 3: exclude_styles serializes to JSON array, not string."""
    p = TrackPrompt(exclude_styles=["sax lead", "drum fills", "trot"])
    data = json.loads(p.model_dump_json())
    assert isinstance(data["exclude_styles"], list)
    assert "sax lead" in data["exclude_styles"]
    assert "trot" in data["exclude_styles"]


def test_exclude_styles_roundtrip():
    """Fix 3: list[str] survives full manifest JSON roundtrip."""
    t = TrackManifest(
        track_number=1,
        track_id="t1",
        prompt=TrackPrompt(exclude_styles=["sax lead", "enka", "EDM"]),
    )
    json_str = t.model_dump_json()
    restored = TrackManifest.model_validate_json(json_str)
    assert restored.prompt.exclude_styles == ["sax lead", "enka", "EDM"]


def test_manifest_roundtrip():
    """Full ProjectManifest serialization roundtrip."""
    m = ProjectManifest(
        project_id="roundtrip-id",
        project_name="Roundtrip Test",
        track_count=3,
        tracks=[
            TrackManifest(
                track_number=i, track_id=f"t{i}",
                prompt=TrackPrompt(
                    title=f"Track {i}",
                    exclude_styles=["sax lead", "trot"],
                ),
            )
            for i in range(1, 4)
        ],
    )
    json_str = m.model_dump_json()
    restored = ProjectManifest.model_validate_json(json_str)
    assert restored.project_name == "Roundtrip Test"
    assert len(restored.tracks) == 3
    assert restored.tracks[2].prompt.title == "Track 3"
    assert restored.tracks[0].prompt.exclude_styles == ["sax lead", "trot"]


def test_datetime_fields_are_timezone_aware():
    """Fix 9: All timestamp fields should be timezone-aware ISO strings."""
    m = ProjectManifest(project_id="tz-test", project_name="TZ Test")
    # Timezone-aware ISO strings contain '+' or 'Z' or timezone offset
    assert "+" in m.created_at or "Z" in m.created_at or m.created_at.endswith("+00:00")
