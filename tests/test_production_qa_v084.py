"""
tests/test_production_qa_v084.py — Pilot Production QA Mode tests.

No real external API calls. No long FFmpeg. Scanner/checklist exercised
against a temp outputs/ tree.
"""
from __future__ import annotations
import json
import inspect
import pytest
from pathlib import Path


@pytest.fixture
def outputs_tree(monkeypatch, tmp_path):
    """Build a partial production outputs/ tree and point the scanner at it."""
    import services.production.production_scanner as scn
    import services.production.production_checklist as cl

    outputs = tmp_path / "outputs"

    # Songs
    (outputs / "song_projects" / "p" / "songs").mkdir(parents=True)
    (outputs / "song_projects" / "p" / "songs" / "track1.mp3").write_bytes(
        b"\xff\xfb\x90\x00" + b"\x00" * 4000)
    (outputs / "song_projects" / "p" / "songs" / "track2.mp3").write_bytes(
        b"\xff\xfb\x90\x00" + b"\x00" * 4000)

    # Thumbnails
    texp = outputs / "thumbnail_studio" / "s1" / "exports"
    texp.mkdir(parents=True)
    (texp / "youtube_thumbnail_16x9.png").write_bytes(b"\x89PNG" + b"\x00" * 50)
    (texp / "video_playback_background_16x9.png").write_bytes(b"\x89PNG" + b"\x00" * 50)
    (texp / "streaming_cover_1x1.png").write_bytes(b"\x89PNG" + b"\x00" * 50)
    (texp / "asset_manifest.json").write_text("{}", encoding="utf-8")

    # Video render
    vdir = outputs / "video_renderer" / "render_3600s"
    vdir.mkdir(parents=True)
    (vdir / "final_video.mp4").write_bytes(b"\x00" * 5000)
    (vdir / "preview_30s.mp4").write_bytes(b"\x00" * 1000)
    (vdir / "chapters.txt").write_text("00:00 track1", encoding="utf-8")
    (vdir / "playlist_plan.json").write_text("{}", encoding="utf-8")
    (vdir / "render_plan.json").write_text("{}", encoding="utf-8")
    (vdir / "overlay_plan.json").write_text("{}", encoding="utf-8")

    # YouTube package
    pdir = outputs / "youtube_package" / "pkg1"
    pdir.mkdir(parents=True)
    for f in ["title.txt", "description.txt", "tags.txt", "hashtags.txt",
              "pinned_comment.txt"]:
        (pdir / f).write_text("x", encoding="utf-8")
    (pdir / "package_manifest.json").write_text("{}", encoding="utf-8")
    (pdir / "youtube_upload_payload.json").write_text("{}", encoding="utf-8")
    (pdir / "thumbnail_upload_ready.jpg").write_bytes(b"\xff\xd8" + b"\x00" * 50)

    monkeypatch.setattr(scn, "_outputs_root", lambda: outputs)
    monkeypatch.setattr(scn, "_mp3_duration", lambda p: 210.0)
    monkeypatch.setattr(cl.scanner, "_outputs_root", lambda: outputs)
    return outputs


# ─── Tab + nav exist ─────────────────────────────────────────────────────────

def test_production_qa_tab_exists():
    from app.tabs.production_qa_tab import render_production_qa
    assert callable(render_production_qa)


def test_home_tabs_include_production_qa():
    # v1.0.0-alpha.31: unified sidebar-nav router (render_dashboard)
    import app.dashboard as dash
    src = inspect.getsource(dash.render_dashboard)
    assert "render_production_qa" in src
    assert "Production QA" in src


def test_production_tabs_include_production_qa():
    import app.dashboard as dash
    src = inspect.getsource(dash.render_dashboard)
    assert "render_production_qa" in src


# ─── Scanner ─────────────────────────────────────────────────────────────────

def test_production_scanner_finds_mp3_files(outputs_tree):
    from services.production.production_scanner import scan_song_assets
    songs = scan_song_assets()
    assert songs["mp3_count"] == 2
    assert songs["total_duration_sec"] > 0


def test_production_scanner_finds_youtube_thumbnail(outputs_tree):
    from services.production.production_scanner import scan_thumbnail_assets
    t = scan_thumbnail_assets()
    assert t["youtube_thumbnail"] is not None
    assert t["youtube_thumbnail"].endswith("youtube_thumbnail_16x9.png")


def test_production_scanner_finds_video_background(outputs_tree):
    from services.production.production_scanner import scan_thumbnail_assets
    t = scan_thumbnail_assets()
    assert t["video_playback_background"] is not None


def test_production_scanner_finds_streaming_cover(outputs_tree):
    from services.production.production_scanner import scan_thumbnail_assets
    t = scan_thumbnail_assets()
    assert t["streaming_cover"] is not None


def test_production_scanner_finds_final_video(outputs_tree):
    from services.production.production_scanner import scan_video_render
    v = scan_video_render()
    assert v["final_video"] is not None
    assert v["final_video"].endswith("final_video.mp4")


def test_production_scanner_finds_youtube_package(outputs_tree):
    from services.production.production_scanner import scan_youtube_package
    p = scan_youtube_package()
    assert p["package_manifest"] is not None
    assert p["title"] is not None


# ─── Checklist statuses ──────────────────────────────────────────────────────

def test_checklist_marks_missing_thumbnail(monkeypatch, tmp_path):
    """With no thumbnail, the youtube_thumbnail item is Missing."""
    import services.production.production_scanner as scn
    import services.production.production_checklist as cl
    outputs = tmp_path / "outputs"
    (outputs / "song_projects" / "p").mkdir(parents=True)
    (outputs / "song_projects" / "p" / "a.mp3").write_bytes(b"\xff\xfb" + b"\x00" * 4000)
    monkeypatch.setattr(scn, "_outputs_root", lambda: outputs)
    monkeypatch.setattr(scn, "_mp3_duration", lambda p: 210.0)
    monkeypatch.setattr(cl.scanner, "_outputs_root", lambda: outputs)

    checklist = cl.build_checklist()
    thumb_items = {it["key"]: it for it in checklist["groups"]["Thumbnail assets"]}
    assert thumb_items["youtube_thumbnail"]["status"] == "Missing"


def test_checklist_marks_missing_video_background_warning(monkeypatch, tmp_path):
    """No playback background → a warning (with thumbnail present)."""
    import services.production.production_scanner as scn
    import services.production.production_checklist as cl
    outputs = tmp_path / "outputs"
    texp = outputs / "thumbnail_studio" / "s" / "exports"
    texp.mkdir(parents=True)
    (texp / "youtube_thumbnail_16x9.png").write_bytes(b"\x89PNG" + b"\x00" * 50)
    (outputs / "song_projects" / "p").mkdir(parents=True)
    (outputs / "song_projects" / "p" / "a.mp3").write_bytes(b"\xff\xfb" + b"\x00" * 4000)
    monkeypatch.setattr(scn, "_outputs_root", lambda: outputs)
    monkeypatch.setattr(scn, "_mp3_duration", lambda p: 210.0)
    monkeypatch.setattr(cl.scanner, "_outputs_root", lambda: outputs)

    checklist = cl.build_checklist()
    msgs = " ".join(w["message"] for w in checklist["warnings"])
    assert "Video Playback Background" in msgs


def test_checklist_marks_final_video_ready(outputs_tree):
    from services.production.production_checklist import build_checklist
    checklist = build_checklist()
    video_items = {it["key"]: it for it in checklist["groups"]["Video render"]}
    assert video_items["final_video"]["status"] in ("Ready", "Completed")


def test_checklist_marks_youtube_package_ready(outputs_tree):
    from services.production.production_checklist import build_checklist
    checklist = build_checklist()
    pkg_items = {it["key"]: it for it in checklist["groups"]["YouTube package"]}
    assert pkg_items["title"]["status"] == "Ready"
    assert pkg_items["description"]["status"] == "Ready"


# ─── Next action ─────────────────────────────────────────────────────────────

def test_next_action_recommends_thumbnail_when_missing(monkeypatch, tmp_path):
    import services.production.production_scanner as scn
    import services.production.production_checklist as cl
    outputs = tmp_path / "outputs"
    (outputs / "song_projects" / "p").mkdir(parents=True)
    (outputs / "song_projects" / "p" / "a.mp3").write_bytes(b"\xff\xfb" + b"\x00" * 4000)
    monkeypatch.setattr(scn, "_outputs_root", lambda: outputs)
    monkeypatch.setattr(scn, "_mp3_duration", lambda p: 210.0)
    monkeypatch.setattr(cl.scanner, "_outputs_root", lambda: outputs)

    action = cl.recommend_next_action(scn.scan_all())
    assert "썸네일" in action


def test_next_action_recommends_preview_before_full_render(monkeypatch, tmp_path):
    """MP3 + thumbnail + background present, but no preview/final → recommend preview."""
    import services.production.production_scanner as scn
    import services.production.production_checklist as cl
    outputs = tmp_path / "outputs"
    texp = outputs / "thumbnail_studio" / "s" / "exports"
    texp.mkdir(parents=True)
    (texp / "youtube_thumbnail_16x9.png").write_bytes(b"\x89PNG" + b"\x00" * 50)
    (texp / "video_playback_background_16x9.png").write_bytes(b"\x89PNG" + b"\x00" * 50)
    (outputs / "song_projects" / "p").mkdir(parents=True)
    (outputs / "song_projects" / "p" / "a.mp3").write_bytes(b"\xff\xfb" + b"\x00" * 4000)
    monkeypatch.setattr(scn, "_outputs_root", lambda: outputs)
    monkeypatch.setattr(scn, "_mp3_duration", lambda p: 210.0)
    monkeypatch.setattr(cl.scanner, "_outputs_root", lambda: outputs)

    action = cl.recommend_next_action(scn.scan_all())
    assert "preview" in action.lower()


# ─── Warnings ────────────────────────────────────────────────────────────────

def test_warning_when_youtube_thumbnail_used_as_video_background(monkeypatch, tmp_path):
    import services.production.production_scanner as scn
    import services.production.production_checklist as cl
    outputs = tmp_path / "outputs"
    texp = outputs / "thumbnail_studio" / "s" / "exports"
    texp.mkdir(parents=True)
    (texp / "youtube_thumbnail_16x9.png").write_bytes(b"\x89PNG" + b"\x00" * 50)
    # NO video_playback_background
    monkeypatch.setattr(scn, "_outputs_root", lambda: outputs)
    monkeypatch.setattr(cl.scanner, "_outputs_root", lambda: outputs)

    warnings = cl.build_warnings(scn.scan_all())
    msgs = [w["message"] for w in warnings]
    assert any("중앙 타이틀이 겹칠" in m for m in msgs)


def test_missing_cta_is_optional_warning(outputs_tree, monkeypatch, tmp_path):
    """Missing CTA sticker is an optional-level warning, not a blocker."""
    import services.production.production_scanner as scn
    import services.production.production_checklist as cl
    # Use a tree WITHOUT a CTA sticker (outputs_tree has none)
    warnings = cl.build_warnings(scn.scan_all())
    cta = [w for w in warnings if "CTA" in w["message"]]
    assert cta, "expected a CTA warning"
    assert cta[0]["level"] == "optional"


def test_missing_final_video_is_blocker_for_package(monkeypatch, tmp_path):
    import services.production.production_scanner as scn
    import services.production.production_checklist as cl
    outputs = tmp_path / "outputs"
    # YouTube package present but NO final_video
    pdir = outputs / "youtube_package" / "pkg"
    pdir.mkdir(parents=True)
    (pdir / "title.txt").write_text("x", encoding="utf-8")
    (pdir / "package_manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(scn, "_outputs_root", lambda: outputs)
    monkeypatch.setattr(cl.scanner, "_outputs_root", lambda: outputs)

    warnings = cl.build_warnings(scn.scan_all())
    blockers = [w for w in warnings if w["level"] == "blocker"]
    assert any("final_video" in w["message"] for w in blockers)


# ─── Report export ───────────────────────────────────────────────────────────

def test_production_report_created(outputs_tree, monkeypatch, tmp_path):
    import services.production.production_checklist as cl
    monkeypatch.setattr(cl, "_reports_root", lambda: tmp_path / "production_qa")
    result = cl.export_report()
    for key in ["production_status", "production_checklist", "missing_assets", "next_steps"]:
        assert Path(result["files"][key]).exists()
    # production_status.json is valid JSON with scores
    status = json.loads(Path(result["files"]["production_status"]).read_text(encoding="utf-8"))
    assert "scores" in status
    assert "overall_readiness" in status


def test_production_report_does_not_include_secrets(monkeypatch, tmp_path):
    """The report must never contain tokens/keys/secrets."""
    import services.production.production_scanner as scn
    import services.production.production_checklist as cl
    import services.youtube.token_store as ts

    outputs = tmp_path / "outputs"
    (outputs / "song_projects" / "p").mkdir(parents=True)
    (outputs / "song_projects" / "p" / "a.mp3").write_bytes(b"\xff\xfb" + b"\x00" * 4000)
    # Put a token on disk (must NOT end up in the report)
    monkeypatch.setattr(ts, "_auth_dir", lambda: tmp_path / "youtube_auth")
    ts.save_token({"access_token": "ya29.SECRETTOKEN", "refresh_token": "1//SECRET"})

    monkeypatch.setattr(scn, "_outputs_root", lambda: outputs)
    monkeypatch.setattr(scn, "_mp3_duration", lambda p: 210.0)
    monkeypatch.setattr(cl.scanner, "_outputs_root", lambda: outputs)
    monkeypatch.setattr(cl, "_reports_root", lambda: tmp_path / "production_qa")

    result = cl.export_report()
    blob = ""
    for f in Path(result["report_dir"]).iterdir():
        blob += f.read_text(encoding="utf-8")
    assert "ya29.SECRETTOKEN" not in blob
    assert "1//SECRET" not in blob
    # Generic secret words should not appear as raw values either
    assert "refresh_token" not in blob.lower() or "REDACTED" in blob


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
