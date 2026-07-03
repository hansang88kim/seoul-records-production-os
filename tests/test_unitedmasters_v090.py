"""
tests/test_unitedmasters_v090.py — UnitedMasters Distribution Package tests.

No real UnitedMasters API. No browser automation. MP3 stays draft; WAV/FLAC
masters flip distribution_ready. No fake WAV.
"""
from __future__ import annotations
import csv
import json
import inspect
import pytest
from pathlib import Path


def _make_plan(tmp_path, with_wav=False):
    songs = tmp_path / "songs"
    songs.mkdir(exist_ok=True)
    a = songs / "track_a.mp3"; a.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 4000)
    b = songs / "track_b.mp3"; b.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 4000)
    if with_wav:
        (songs / "track_a.wav").write_bytes(b"RIFF" + b"\x00" * 4000)
        (songs / "track_b.wav").write_bytes(b"RIFF" + b"\x00" * 4000)
    plan = {"entries": [
        {"path": str(a), "name": "track_a.mp3", "duration_sec": 210, "repeat_index": 0},
        {"path": str(b), "name": "track_b.mp3", "duration_sec": 200, "repeat_index": 0},
        {"path": str(a), "name": "track_a.mp3", "duration_sec": 210, "repeat_index": 1},
    ]}
    return plan, str(a), str(b)


@pytest.fixture
def cover(tmp_path):
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL not available")
    p = tmp_path / "streaming_cover_1x1.png"
    Image.new("RGB", (3000, 3000), (40, 30, 70)).save(p)
    return str(p)


@pytest.fixture
def pkg_root(monkeypatch, tmp_path):
    import services.unitedmasters.package_service as PS
    monkeypatch.setattr(PS, "_packages_root", lambda: tmp_path / "um")
    return tmp_path / "um"


# ─── Tab + nav ───────────────────────────────────────────────────────────────

def test_unitedmasters_tab_exists():
    from app.tabs.unitedmasters_tab import render_unitedmasters
    assert callable(render_unitedmasters)


def test_home_tabs_include_unitedmasters():
    # v1.0.0-alpha.31: unified sidebar-nav router (render_dashboard)
    import app.dashboard as dash
    src = inspect.getsource(dash.render_dashboard)
    assert "render_unitedmasters" in src
    assert "UnitedMasters" in src


# ─── Package creation + order ────────────────────────────────────────────────

def test_unitedmasters_package_created(tmp_path, cover, pkg_root):
    import services.unitedmasters.package_service as PS
    plan, _, _ = _make_plan(tmp_path)
    m = PS.create_package(plan, cover)
    assert m["package_id"]
    assert Path(m["package_dir"], "package_manifest.json").exists()


def test_unitedmasters_uses_video_renderer_playlist_order(tmp_path, cover, pkg_root):
    from services.unitedmasters.track_builder import build_tracklist
    plan, _, _ = _make_plan(tmp_path)
    tracks = build_tracklist(plan)
    assert [t["track_no"] for t in tracks] == ["01", "02"]
    assert tracks[0]["title"] == "track a"
    assert tracks[1]["title"] == "track b"


def test_track_order_matches_playlist_plan(tmp_path):
    from services.unitedmasters.track_builder import build_tracklist, order_matches_playlist
    plan, _, _ = _make_plan(tmp_path)
    tracks = build_tracklist(plan)
    assert order_matches_playlist(tracks, plan) is True


def test_tracklist_csv_created(tmp_path, cover, pkg_root):
    import services.unitedmasters.package_service as PS
    plan, _, _ = _make_plan(tmp_path)
    m = PS.create_package(plan, cover)
    csv_path = Path(m["package_dir"], "tracklist.csv")
    assert csv_path.exists()
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    assert len(rows) == 2
    assert rows[0]["track_no"] == "01"


def test_tracklist_json_created(tmp_path, cover, pkg_root):
    import services.unitedmasters.package_service as PS
    plan, _, _ = _make_plan(tmp_path)
    m = PS.create_package(plan, cover)
    j = json.loads(Path(m["package_dir"], "tracklist.json").read_text(encoding="utf-8"))
    assert len(j) == 2


# ─── Cover ───────────────────────────────────────────────────────────────────

def test_streaming_cover_1x1_required(tmp_path, pkg_root):
    """A package with no cover still builds but flags a cover warning."""
    import services.unitedmasters.package_service as PS
    plan, _, _ = _make_plan(tmp_path)
    m = PS.create_package(plan, "")  # no cover
    assert any("cover" in w.lower() or "커버" in w for w in m["warnings"]) or \
        m["cover_status"] is not None


def test_cover_validation_accepts_3000_square_png(cover):
    from services.unitedmasters.cover_validator import validate_cover
    r = validate_cover(cover)
    assert r["status"] == "Cover Ready"
    assert r["square"] is True
    assert r["width"] == 3000


def test_cover_validation_warns_non_square(tmp_path):
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL not available")
    from services.unitedmasters.cover_validator import validate_cover
    p = tmp_path / "wide.png"
    Image.new("RGB", (3000, 1500), (10, 10, 10)).save(p)
    r = validate_cover(str(p))
    assert r["status"] == "Cover Warning"
    assert r["square"] is False
    assert any("정사각형" in w for w in r["warnings"])


# ─── MP3 vs WAV/FLAC distribution readiness ──────────────────────────────────

def test_mp3_tracks_included_as_source_audio(tmp_path, cover, pkg_root):
    import services.unitedmasters.package_service as PS
    plan, _, _ = _make_plan(tmp_path)
    m = PS.create_package(plan, cover)
    mp3s = list(Path(m["package_dir"], "audio_mp3_reference").glob("*.mp3"))
    assert len(mp3s) == 2


def test_mp3_only_not_distribution_ready(tmp_path, cover, pkg_root):
    import services.unitedmasters.package_service as PS
    plan, _, _ = _make_plan(tmp_path, with_wav=False)
    m = PS.create_package(plan, cover)
    assert m["distribution_ready"] is False
    assert m["mp3_only"] is True
    assert m["status"] == "MP3-only Warning"


def test_wav_master_marks_track_distribution_ready(tmp_path, cover, pkg_root):
    import services.unitedmasters.package_service as PS
    plan, _, _ = _make_plan(tmp_path, with_wav=True)  # sibling WAVs present
    m = PS.create_package(plan, cover)
    assert m["distribution_ready"] is True
    assert m["status"] == "Distribution Ready"


def test_fake_wav_not_created(tmp_path, cover, pkg_root):
    """MP3-only package must NOT create any WAV/FLAC in the master folder."""
    import services.unitedmasters.package_service as PS
    plan, _, _ = _make_plan(tmp_path, with_wav=False)
    m = PS.create_package(plan, cover)
    master_dir = Path(m["package_dir"], "audio_distribution_master")
    wavs = list(master_dir.glob("*.wav")) + list(master_dir.glob("*.flac"))
    assert wavs == []


def test_attach_wav_flac_master(tmp_path, cover, pkg_root):
    """Attaching a master via override flips that track to distribution-ready."""
    import services.unitedmasters.package_service as PS
    from services.unitedmasters.track_builder import build_tracklist
    plan, a, b = _make_plan(tmp_path, with_wav=False)
    # Provide a real WAV master for both tracks as overrides
    wa = tmp_path / "songs" / "master_a.wav"; wa.write_bytes(b"RIFF" + b"\x00" * 100)
    wb = tmp_path / "songs" / "master_b.wav"; wb.write_bytes(b"RIFF" + b"\x00" * 100)
    overrides = {a: str(wa), b: str(wb)}
    tracks = build_tracklist(plan, overrides)
    assert all(t["distribution_ready"] for t in tracks)
    m = PS.create_package(plan, cover, master_overrides=overrides)
    assert m["distribution_ready"] is True
    masters = list(Path(m["package_dir"], "audio_distribution_master").glob("*.wav"))
    assert len(masters) == 2


# ─── Metadata + checklist + export ───────────────────────────────────────────

def test_release_metadata_json_created(tmp_path, cover, pkg_root):
    import services.unitedmasters.package_service as PS
    plan, _, _ = _make_plan(tmp_path)
    m = PS.create_package(plan, cover)
    rm = json.loads(Path(m["package_dir"], "release_metadata.json").read_text(encoding="utf-8"))
    assert rm["track_count"] == 2
    assert "tracks" in rm


def test_manual_upload_checklist_created(tmp_path, cover, pkg_root):
    import services.unitedmasters.package_service as PS
    plan, _, _ = _make_plan(tmp_path)
    m = PS.create_package(plan, cover)
    cl = Path(m["package_dir"], "metadata", "unitedmasters_manual_upload_checklist.md")
    assert cl.exists()
    assert "UnitedMasters" in cl.read_text(encoding="utf-8")


def test_export_manual_upload_package(tmp_path, cover, pkg_root):
    import services.unitedmasters.package_service as PS
    plan, _, _ = _make_plan(tmp_path)
    m = PS.create_package(plan, cover)
    zip_path = PS.build_manual_upload_zip(m["package_dir"])
    assert zip_path and Path(zip_path).exists()
    assert zip_path.endswith("manual_upload_package.zip")


def test_unitedmasters_package_does_not_delete_source_mp3(tmp_path, cover, pkg_root):
    import services.unitedmasters.package_service as PS
    plan, a, b = _make_plan(tmp_path)
    PS.create_package(plan, cover)
    # Source MP3s still on disk
    assert Path(a).exists()
    assert Path(b).exists()


# ─── Order sync warning ──────────────────────────────────────────────────────

def test_order_sync_warning_on_mismatch(tmp_path):
    from services.unitedmasters.track_builder import order_matches_playlist
    plan, _, _ = _make_plan(tmp_path)
    # A mismatched tracklist (reversed)
    bad = [{"title": "track b"}, {"title": "track a"}]
    assert order_matches_playlist(bad, plan) is False


# ─── Production QA integration ───────────────────────────────────────────────

def test_production_qa_includes_unitedmasters_readiness(tmp_path, cover, monkeypatch):
    import services.unitedmasters.package_service as PS
    import services.production.production_scanner as scn
    import services.production.production_checklist as cl

    outputs = tmp_path / "outputs"
    monkeypatch.setattr(PS, "_packages_root", lambda: outputs / "unitedmasters_package")
    plan, _, _ = _make_plan(tmp_path)
    PS.create_package(plan, cover)

    monkeypatch.setattr(scn, "_outputs_root", lambda: outputs)
    monkeypatch.setattr(cl.scanner, "_outputs_root", lambda: outputs)
    checklist = cl.build_checklist()
    assert "UnitedMasters" in checklist["groups"]
    assert "unitedmasters_readiness" in checklist["scores"]


def test_mp3_only_does_not_count_as_distribution_ready_in_qa(tmp_path, cover, monkeypatch):
    import services.unitedmasters.package_service as PS
    import services.production.production_scanner as scn
    import services.production.production_checklist as cl
    outputs = tmp_path / "outputs"
    monkeypatch.setattr(PS, "_packages_root", lambda: outputs / "unitedmasters_package")
    plan, _, _ = _make_plan(tmp_path, with_wav=False)  # MP3-only
    PS.create_package(plan, cover)
    monkeypatch.setattr(scn, "_outputs_root", lambda: outputs)
    monkeypatch.setattr(cl.scanner, "_outputs_root", lambda: outputs)
    um = scn.scan_unitedmasters()
    assert um["distribution_ready"] is False
    assert um["mp3_only"] is True


# ─── Security / policy ───────────────────────────────────────────────────────

def test_no_unitedmasters_credentials_stored():
    """No password/cookie storage implementation in the UnitedMasters code."""
    bad_patterns = ["save_password", "store_password", "set_cookie",
                    "save_cookie", "store_cookie", "password=", "cookies.save"]
    for f in ["services/unitedmasters/package_service.py",
              "services/unitedmasters/track_builder.py",
              "services/unitedmasters/cover_validator.py",
              "app/tabs/unitedmasters_tab.py"]:
        src = Path(f).read_text(encoding="utf-8").lower()
        for pat in bad_patterns:
            assert pat not in src, f"{pat} found in {f}"


def test_no_captcha_bypass_code():
    """No CAPTCHA-solving / bypass implementation (descriptive comments are OK)."""
    bad_patterns = ["solve_captcha", "captcha_solver", "bypass_captcha",
                    "anticaptcha", "2captcha", "recaptcha_token"]
    for f in ["services/unitedmasters/package_service.py",
              "services/unitedmasters/track_builder.py",
              "services/unitedmasters/cover_validator.py",
              "app/tabs/unitedmasters_tab.py"]:
        src = Path(f).read_text(encoding="utf-8").lower()
        for pat in bad_patterns:
            assert pat not in src, f"{pat} found in {f}"


# ─── Existing features unaffected ────────────────────────────────────────────

def test_existing_music_generation_unaffected():
    from providers.ai.base import MOCK_SONGS
    assert len(MOCK_SONGS) >= 2


def test_existing_thumbnail_studio_unaffected():
    from services.thumbnail.prompt_generator import generate_flow_prompt
    assert generate_flow_prompt("korea", "n", 0)["main_prompt"]


def test_existing_video_renderer_unaffected():
    from services.video.render_plan import build_full_render_command
    assert callable(build_full_render_command)


def test_existing_youtube_package_unaffected():
    from services.youtube.youtube_package_service import create_package
    assert callable(create_package)
