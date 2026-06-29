"""
tests/test_home_navigation_v081.py — Home Navigation UX tests (v0.8.1).

Verifies that Video Renderer and YouTube Package are exposed on the home
screen (no project required) and that their output scanners work without an
open project. Existing tab logic is untouched.

We assert on the dashboard source + the render functions' wiring rather than
spinning up Streamlit, plus exercise the scanners directly.
"""
from __future__ import annotations
import inspect
import pytest
from pathlib import Path


def _dashboard_src() -> str:
    return Path("app/dashboard.py").read_text(encoding="utf-8")


def _home_tabs_src() -> str:
    """Extract just the render_home_tabs function source."""
    import app.dashboard as dash
    return inspect.getsource(dash.render_home_tabs)


# ─── Home tabs include the new tabs ──────────────────────────────────────────

def test_home_tabs_include_video_renderer():
    src = _home_tabs_src()
    assert "render_video_renderer" in src
    assert "Video Renderer" in src


def test_home_tabs_include_youtube_package():
    src = _home_tabs_src()
    assert "render_youtube_package" in src
    assert "YouTube Package" in src


def test_home_navigation_does_not_break_song_lab():
    src = _home_tabs_src()
    # Song Lab still wired in the home tabs
    assert "render_song_lab" in src
    assert "Song Lab" in src


def test_home_navigation_does_not_break_thumbnail_studio():
    src = _home_tabs_src()
    assert "render_thumbnail_studio" in src
    assert "Thumbnail Studio" in src


def test_home_tabs_keep_project_management():
    src = _home_tabs_src()
    assert "render_project_screen" in src
    assert "프로젝트 관리" in src


# ─── Production tabs still include them ───────────────────────────────────────

def test_project_open_tabs_still_include_video_renderer():
    import app.dashboard as dash
    src = inspect.getsource(dash.render_production_tabs)
    assert "render_video_renderer" in src


def test_project_open_tabs_still_include_youtube_package():
    import app.dashboard as dash
    src = inspect.getsource(dash.render_production_tabs)
    assert "render_youtube_package" in src


# ─── Render functions are importable (accessible) without a project ──────────

def test_video_renderer_accessible_without_project():
    # The function imports cleanly and is callable — no project state required
    from app.tabs.video_renderer import render_video_renderer
    assert callable(render_video_renderer)
    # It must not reference current_project / current_output_folder at module
    # level in a way that requires a project
    src = Path("app/tabs/video_renderer.py").read_text(encoding="utf-8")
    assert "current_output_folder" not in src
    assert "current_project" not in src


def test_youtube_package_accessible_without_project():
    from app.tabs.youtube_package import render_youtube_package
    assert callable(render_youtube_package)
    src = Path("app/tabs/youtube_package.py").read_text(encoding="utf-8")
    assert "current_output_folder" not in src
    assert "current_project" not in src


# ─── Scanners work without a project (global outputs/ scan) ──────────────────

def test_video_renderer_can_scan_outputs_without_project(monkeypatch, tmp_path):
    """scan_mp3_files works against outputs/ with no project open."""
    import services.video.playlist_builder as pb
    outputs = tmp_path / "outputs"
    (outputs / "song_projects" / "p" / "songs").mkdir(parents=True)
    (outputs / "song_projects" / "p" / "songs" / "밤이_지나면.mp3").write_bytes(
        b"\xff\xfb\x90\x00" + b"\x00" * 4000)
    monkeypatch.setattr(pb, "_outputs_root", lambda: outputs)
    monkeypatch.setattr(pb, "_mp3_duration", lambda p: 210.0)

    tracks = pb.scan_mp3_files()
    assert len(tracks) >= 1
    assert tracks[0]["name"] == "밤이_지나면.mp3"


def test_youtube_package_can_scan_outputs_without_project(monkeypatch, tmp_path):
    """YouTube asset scanners find final_video.mp4 / thumbnail / chapters
    purely from outputs/, no project required."""
    import services.youtube.asset_scanner as scn
    outputs = tmp_path / "outputs"
    # final_video.mp4 under video_renderer
    vdir = outputs / "video_renderer" / "render_3600s"
    vdir.mkdir(parents=True)
    (vdir / "final_video.mp4").write_bytes(b"\x00" * 5000)
    (vdir / "chapters.txt").write_text("00:00 밤이 지나면", encoding="utf-8")
    # thumbnail under thumbnail_studio exports
    tdir = outputs / "thumbnail_studio" / "sess1" / "exports"
    tdir.mkdir(parents=True)
    try:
        from PIL import Image
        Image.new("RGB", (1920, 1080), (30, 30, 60)).save(tdir / "youtube_thumbnail_16x9.png")
    except ImportError:
        (tdir / "youtube_thumbnail_16x9.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    monkeypatch.setattr(scn, "_outputs_root", lambda: outputs)

    videos = scn.scan_final_videos()
    thumbs = scn.scan_youtube_thumbnails()
    chapters = scn.scan_chapters()
    assert any(v["path"].endswith("final_video.mp4") for v in videos)
    assert any(t["path"].endswith(("youtube_thumbnail_16x9.png", ".jpg", ".jpeg")) for t in thumbs)
    assert any(c["path"].endswith("chapters.txt") for c in chapters)


# ─── Existing features unaffected ────────────────────────────────────────────

def test_existing_music_generation_unaffected_v081():
    from providers.ai.base import MOCK_SONGS
    assert len(MOCK_SONGS) >= 2


def test_existing_thumbnail_studio_unaffected_v081():
    from services.thumbnail.prompt_generator import generate_flow_prompt
    assert generate_flow_prompt("korea", "n", 0)["main_prompt"]


def test_existing_video_renderer_unaffected_v081():
    from services.video.render_plan import build_full_render_command
    assert callable(build_full_render_command)


def test_existing_youtube_package_unaffected_v081():
    from services.youtube.youtube_package_service import create_package
    assert callable(create_package)
