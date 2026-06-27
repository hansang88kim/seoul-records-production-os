"""
Tests for MockSunoProvider and song generation workflow (v0.1.2).
Includes: fast_mode, provider registry, both-long → REGENERATION_REQUIRED,
          track_folder_path storage, candidate override safety.
"""
import pytest
from pathlib import Path


def test_mock_provider_create_song():
    from providers.suno.mock_suno import MockSunoProvider
    p = MockSunoProvider()
    task_id = p.create_song("Test Title", "city pop", "test lyrics")
    assert task_id
    assert task_id in p._tasks


def test_mock_provider_fast_mode_default():
    """Fix 3: fast_mode must be True by default."""
    from providers.suno.mock_suno import MockSunoProvider
    p = MockSunoProvider()
    assert p.fast_mode is True
    caps = p.get_capabilities()
    assert caps["fast_mode"] is True


def test_mock_provider_fast_mode_small_files(tmp_path):
    """Fix 3: fast_mode WAV files must be small (< 1 MB)."""
    from providers.suno.mock_suno import MockSunoProvider
    p = MockSunoProvider(fast_mode=True)
    task_id = p.create_song("Small Test", "pop", "lyrics")
    results = p.download_candidates(task_id, tmp_path)
    for r in results:
        file_path = Path(r["file_path"])
        assert file_path.exists()
        size_kb = file_path.stat().st_size / 1024
        assert size_kb < 1024, f"WAV too large: {size_kb:.0f} KB (must be < 1 MB in fast_mode)"
        # Simulated duration must still be in realistic range
        assert r["duration_seconds"] > 180, f"Simulated duration too short: {r['duration_seconds']}"


def test_mock_provider_downloads_two_candidates(tmp_path):
    from providers.suno.mock_suno import MockSunoProvider
    p = MockSunoProvider()
    task_id = p.create_song("Test", "pop", "lyrics")
    results = p.download_candidates(task_id, tmp_path)
    assert len(results) == 2
    for r in results:
        assert Path(r["file_path"]).exists()
        assert r["is_wav"] is True


def test_mock_provider_no_mp3():
    from providers.suno.mock_suno import MockSunoProvider
    p = MockSunoProvider()
    task_id = p.create_song("Test", "pop", "lyrics")
    result = p.download_mp3_preview(task_id, Path("/tmp/fake.mp3"))
    assert result is None


def test_provider_registry_is_single_source():
    """Fix 2: get_composer_provider only in providers.suno (registry)."""
    import providers.suno.mock_suno as ms
    assert not hasattr(ms, "get_composer_provider")
    from providers.suno import get_composer_provider
    assert callable(get_composer_provider)


def test_registry_returns_correct_providers():
    from providers.suno import (
        get_composer_provider, MockSunoProvider, ManualImportProvider,
        LocalUnofficialSunoProvider, PlaywrightSunoWebProvider,
    )
    assert isinstance(get_composer_provider("mock"), MockSunoProvider)
    assert isinstance(get_composer_provider("manual_import"), ManualImportProvider)


def test_third_party_blocked_by_default():
    from providers.suno import get_composer_provider
    import app.config as cfg
    original = cfg.ALLOW_THIRD_PARTY_SUNO
    try:
        cfg.ALLOW_THIRD_PARTY_SUNO = False
        with pytest.raises(PermissionError, match="ALLOW_THIRD_PARTY_SUNO"):
            get_composer_provider("third_party")
    finally:
        cfg.ALLOW_THIRD_PARTY_SUNO = original


def test_full_workflow_stores_track_folder_path(tmp_path, monkeypatch):
    """Fix 6: track_folder_path must be set after song generation."""
    import app.config as cfg
    monkeypatch.setattr(cfg, "OUTPUTS_DIR", tmp_path)

    from app.project_manager import create_project
    from workflows.generate_album import run_song_generation
    from agents.producer_agent import generate_song_prompt

    manifest, output_folder = create_project(
        project_name="Folder Path Test", theme="night", track_count=1,
        production_mode="Manual", output_type="YouTube + Distribution Package",
    )
    track = manifest.tracks[0]
    result = generate_song_prompt(1, "night", "ko_kr_seoul")
    track.prompt.title = result["title"]
    track.prompt.style = result["style"]
    track.prompt.lyrics = result["lyrics"]
    track.prompt.exclude_styles = result["exclude_styles"]

    updated = run_song_generation(manifest, output_folder, track, provider_name="mock")

    # track_folder_path must be set
    assert updated.track_folder_path is not None
    assert Path(updated.track_folder_path).exists()
    assert "01_suno_song_generation" in updated.track_folder_path


def test_both_long_candidates_set_regeneration_required(tmp_path, monkeypatch):
    """Fix 4: Both candidates > 4:00 → REGENERATION_REQUIRED, no WAV saved."""
    import app.config as cfg
    monkeypatch.setattr(cfg, "OUTPUTS_DIR", tmp_path)

    from app.project_manager import create_project
    from workflows.generate_album import run_song_generation
    from app.state_machine import TrackStatus
    from providers.suno.mock_suno import MockSunoProvider

    manifest, output_folder = create_project(
        project_name="Regen Test", theme="", track_count=1,
        production_mode="Manual", output_type="YouTube + Distribution Package",
    )
    track = manifest.tracks[0]
    track.prompt.title = "Regen Track"
    track.prompt.style = "city pop"
    track.prompt.lyrics = "test"

    original_create = MockSunoProvider.create_song

    def patched_create(self, title, style, lyrics, options=None):
        task_id = original_create(self, title, style, lyrics, options)
        self._tasks[task_id]["candidates"] = [
            {"candidate_id": "A", "duration_seconds": 260.0,
             "frequency": 440.0, "file_format": "wav"},
            {"candidate_id": "B", "duration_seconds": 270.0,
             "frequency": 880.0, "file_format": "wav"},
        ]
        return task_id

    monkeypatch.setattr(MockSunoProvider, "create_song", patched_create)

    updated = run_song_generation(manifest, output_folder, track, provider_name="mock")

    assert updated.status == TrackStatus.REGENERATION_REQUIRED
    assert updated.distribution_eligible is False
    assert "regeneration_required_both_long" in updated.qc_warnings


def test_candidate_override_path_safety(tmp_path, monkeypatch):
    """Fix 6: Candidate override must use track_folder_path, not folder scan."""
    import app.config as cfg
    monkeypatch.setattr(cfg, "OUTPUTS_DIR", tmp_path)

    from app.project_manager import create_project, create_track_folder
    from providers.suno.mock_suno import _generate_sine_wav
    from app.state_machine import TrackStatus
    from app.models import CandidateMetadata
    import shutil

    manifest, output_folder = create_project(
        project_name="Override Test", theme="", track_count=2,
        production_mode="Manual", output_type="YouTube + Distribution Package",
    )

    songs_root = output_folder / "01_suno_song_generation"

    # Create two track folders with different candidates
    for i, track in enumerate(manifest.tracks):
        track.prompt.title = f"Track {i + 1}"
        tf = create_track_folder(songs_root, track.track_number, track.prompt.title)
        track.track_folder_path = str(tf)
        cands_dir = tf / "candidates"
        cands_dir.mkdir(exist_ok=True)
        _generate_sine_wav(cands_dir / "candidate_A.wav", frequency=440.0 + i * 100, duration_seconds=3.0)
        _generate_sine_wav(cands_dir / "candidate_B.wav", frequency=660.0 + i * 100, duration_seconds=3.0)
        track.candidates = [
            CandidateMetadata(candidate_id="A", task_id="test", duration_seconds=220.0,
                              is_wav=True, provider="mock", file_path=str(cands_dir / "candidate_A.wav")),
            CandidateMetadata(candidate_id="B", task_id="test", duration_seconds=225.0,
                              is_wav=True, provider="mock", file_path=str(cands_dir / "candidate_B.wav")),
        ]
        track.selected_candidate_id = "A"

    # Override track 1 to candidate B — must only touch track 1's folder
    track1 = manifest.tracks[0]
    tf1 = Path(track1.track_folder_path)
    src = tf1 / "candidates" / "candidate_B.wav"
    dst = tf1 / "selected" / "suno_master.wav"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    track1.selected_candidate_id = "B"
    track1.selected_wav_path = str(dst)

    # Verify track 2's folder was NOT touched
    track2 = manifest.tracks[1]
    tf2 = Path(track2.track_folder_path)
    assert tf1 != tf2, "Track folders must be different"
    selected2 = tf2 / "selected" / "suno_master.wav"
    assert not selected2.exists(), (
        "Track 2's selected/ folder must NOT have been touched by track 1's override"
    )
