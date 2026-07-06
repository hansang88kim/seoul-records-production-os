"""
tests/test_project_scoped_exports_v068.py — v1.0.0-alpha.68.

Project-scoped output filenames:
  - services/thumbnail/asset_exporter.export_filename() appends the linked
    project's folder-slug before the extension (standalone sessions keep
    the bare name — backward compatible).
  - services/youtube/asset_scanner.py's rglob patterns are wildcarded so
    both bare and project-suffixed filenames are still found.
  - services/production/production_scanner.py's thumbnail globs likewise.
"""
from __future__ import annotations

import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def studio_tmp(monkeypatch, tmp_path):
    import services.thumbnail.session_store as ss
    monkeypatch.setattr(ss, "_studio_root", lambda: tmp_path / "thumbnail_studio")
    yield


def _bg(tmp_path):
    from PIL import Image
    bg = tmp_path / "bg.png"
    Image.new("RGB", (1600, 900), (40, 50, 80)).save(bg)
    return str(bg)


# ─── export_filename() ───────────────────────────────────────────────────────

def test_export_filename_bare_for_standalone_session(tmp_path):
    from services.thumbnail import session_store as ss, asset_types as AT
    from services.thumbnail.asset_exporter import export_filename

    sess = ss.create_session("korea", "night", "Standalone Vol.1")
    sid = sess["session_id"]
    assert export_filename(sid, AT.YOUTUBE_THUMBNAIL_16X9) == "youtube_thumbnail_16x9.png"


def test_export_filename_appends_project_slug(tmp_path):
    from services.thumbnail import session_store as ss, asset_types as AT
    from services.thumbnail.asset_exporter import export_filename

    sess = ss.create_session("korea", "night", "Linked Vol.1",
                             project_folder=str(tmp_path / "song_projects" / "서울-시티팝-Vol.01"))
    sid = sess["session_id"]
    assert export_filename(sid, AT.YOUTUBE_THUMBNAIL_16X9) == \
        "youtube_thumbnail_16x9_서울-시티팝-Vol.01.png"
    assert export_filename(sid, AT.STREAMING_COVER_1X1) == \
        "streaming_cover_1x1_서울-시티팝-Vol.01.png"


def test_export_youtube_thumbnail_writes_suffixed_file_when_project_linked(tmp_path):
    from services.thumbnail import session_store as ss, asset_types as AT
    from services.thumbnail import asset_exporter as ae

    sess = ss.create_session("korea", "night", "T",
                             project_folder=str(tmp_path / "song_projects" / "P"))
    sid = sess["session_id"]
    out = ae.export_youtube_thumbnail(sid, _bg(tmp_path), "T", "S", "Seoul Records", "#ff0000")
    assert out is not None
    assert Path(out).name == "youtube_thumbnail_16x9_P.png"
    assert Path(out).exists()


# ─── asset_scanner.py: wildcarded rglob still finds suffixed files ──────────

def test_scan_youtube_thumbnails_finds_project_suffixed_file(monkeypatch, tmp_path):
    import services.youtube.asset_scanner as scanner
    monkeypatch.setattr(scanner, "_outputs_root", lambda: tmp_path)

    d = tmp_path / "thumbnail_studio" / "sess1" / "exports"
    d.mkdir(parents=True)
    (d / "youtube_thumbnail_16x9_서울-시티팝-Vol.01.png").write_bytes(b"x")

    found = scanner.scan_youtube_thumbnails()
    assert len(found) == 1
    assert found[0]["name"] == "youtube_thumbnail_16x9_서울-시티팝-Vol.01.png"


def test_scan_streaming_covers_finds_project_suffixed_file(monkeypatch, tmp_path):
    import services.youtube.asset_scanner as scanner
    monkeypatch.setattr(scanner, "_outputs_root", lambda: tmp_path)

    d = tmp_path / "thumbnail_studio" / "sess1" / "exports"
    d.mkdir(parents=True)
    (d / "streaming_cover_1x1_P.png").write_bytes(b"x")

    found = scanner.scan_streaming_covers()
    assert len(found) == 1
    assert found[0]["name"] == "streaming_cover_1x1_P.png"


def test_scan_final_videos_finds_project_suffixed_file(monkeypatch, tmp_path):
    import services.youtube.asset_scanner as scanner
    monkeypatch.setattr(scanner, "_outputs_root", lambda: tmp_path)

    d = tmp_path / "song_projects" / "P" / "video_renders" / "render_3600s"
    d.mkdir(parents=True)
    (d / "final_video_P.mp4").write_bytes(b"x")
    # Old bare name must still be found too (backward compatible).
    d2 = tmp_path / "video_renders" / "render_3600s"
    d2.mkdir(parents=True)
    (d2 / "final_video.mp4").write_bytes(b"x")

    found = scanner.scan_final_videos()
    names = {f["name"] for f in found}
    assert names == {"final_video_P.mp4", "final_video.mp4"}


# ─── production_scanner.py: wildcarded thumbnail globs ──────────────────────

# ─── infer_project_slug() ────────────────────────────────────────────────────

def test_infer_project_slug_from_path():
    import services.youtube.asset_scanner as scanner
    path = str(Path("outputs") / "song_projects" / "서울-시티팝-Vol.01"
                / "video_renders" / "render_3600s" / "final_video_서울-시티팝-Vol.01.mp4")
    assert scanner.infer_project_slug(path) == "서울-시티팝-Vol.01"


def test_infer_project_slug_from_path_works_for_chapters_txt_too():
    """chapters.txt has no filename suffix — path alone must resolve it."""
    import services.youtube.asset_scanner as scanner
    path = str(Path("outputs") / "song_projects" / "P"
                / "video_renders" / "render_3600s" / "chapters.txt")
    assert scanner.infer_project_slug(path) == "P"


def test_infer_project_slug_from_filename_when_not_under_song_projects():
    import services.youtube.asset_scanner as scanner
    path = str(Path("outputs") / "thumbnail_studio" / "sess1" / "exports"
                / "youtube_thumbnail_16x9_P.png")
    assert scanner.infer_project_slug(path) == "P"


def test_infer_project_slug_empty_for_bare_unclassified_asset():
    import services.youtube.asset_scanner as scanner
    path = str(Path("outputs") / "video_renders" / "render_3600s" / "final_video.mp4")
    assert scanner.infer_project_slug(path) == ""
    path2 = str(Path("outputs") / "thumbnail_studio" / "sess1" / "exports"
                 / "youtube_thumbnail_16x9.png")
    assert scanner.infer_project_slug(path2) == ""


def test_production_scanner_finds_project_suffixed_thumbnail(monkeypatch, tmp_path):
    import services.production.production_scanner as psc
    monkeypatch.setattr(psc, "_outputs_root", lambda: tmp_path)

    d = tmp_path / "thumbnail_studio" / "sess1" / "exports"
    d.mkdir(parents=True)
    (d / "youtube_thumbnail_16x9_P.png").write_bytes(b"x")
    (d / "streaming_cover_1x1_P.jpg").write_bytes(b"x")

    result = psc.scan_thumbnail_assets()
    assert result["youtube_thumbnail"] is not None
    assert Path(result["youtube_thumbnail"]).name == "youtube_thumbnail_16x9_P.png"
    assert result["streaming_cover"] is not None
    assert Path(result["streaming_cover"]).name == "streaming_cover_1x1_P.jpg"


# ─── YouTube Package Studio: project filter (v1.0.0-alpha.68) ──────────────

try:
    from streamlit.testing.v1 import AppTest
    _HAS_APPTEST = True
except Exception:
    _HAS_APPTEST = False


@pytest.mark.skipif(not _HAS_APPTEST, reason="streamlit.testing.v1 not available")
def test_youtube_package_renders_with_multi_project_assets(monkeypatch, tmp_path):
    """
    Two projects' worth of rendered assets on disk (one video-render-scoped
    via path, one thumbnail-scoped via filename suffix) — the new project
    filter multiselect must not crash the page.
    """
    import json
    import services.youtube.asset_scanner as AS

    outputs = tmp_path / "outputs"

    # Project A: a project-scoped video render (path-based identification).
    a_dir = outputs / "song_projects" / "A" / "video_renders" / "render_3600s"
    a_dir.mkdir(parents=True)
    (a_dir / "final_video_A.mp4").write_bytes(b"x")
    (a_dir / "chapters.txt").write_text("00:00 곡", encoding="utf-8")

    # Project A's manifest (so list_song_projects() can label the slug).
    proj_a = outputs / "song_projects" / "A"
    (proj_a / "songs").mkdir(parents=True, exist_ok=True)
    (proj_a / "manifest.json").write_text(
        json.dumps({"name": "A", "songs": []}, ensure_ascii=False), encoding="utf-8")

    # Project B: a thumbnail export (filename-based identification).
    # A real (decodable) PNG — the page calls st.image() on the selected one.
    from PIL import Image
    b_dir = outputs / "thumbnail_studio" / "sess1" / "exports"
    b_dir.mkdir(parents=True)
    Image.new("RGB", (1920, 1080), (40, 50, 80)).save(b_dir / "youtube_thumbnail_16x9_B.png")

    monkeypatch.setattr(AS, "_outputs_root", lambda: outputs)
    monkeypatch.setattr("app.project_manager._song_projects_root",
                        lambda: outputs / "song_projects")

    at = AppTest.from_file("app/main.py")
    at.session_state["nav_page"] = "youtube"
    at.run(timeout=30)
    assert not at.exception
