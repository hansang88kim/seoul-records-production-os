"""
tests/test_library_selection_v043.py — v1.0.0-alpha.43

Library-driven selection everywhere:
  1. Candidate Gallery can open any session from the image Library
     (Prompt Lab no longer a prerequisite).
  2. Song Lab 프로젝트 관리 can import songs picked from the song Library
     (copy_song_to_project).
  3. Video Renderer defaults the overlay asset source to Mock 자산.
  4. Video Renderer MP3 / thumbnail-session pickers use IDENTICAL
     names + meta descriptions to the sidebar Library, and a project
     folder can be selected to bulk-select all child MP3s.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from services import library_labels as ll


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_song_project(root: Path, name: str, songs: list[dict]) -> Path:
    pdir = root / name
    (pdir / "songs").mkdir(parents=True, exist_ok=True)
    manifest = {"name": name, "slug": name, "songs": songs}
    (pdir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return pdir


def _patch_song_root(monkeypatch, root: Path):
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("app.project_manager._song_projects_root", lambda: root)


# ─── format / label unit tests ───────────────────────────────────────────────

def test_format_duration():
    assert ll.format_duration(191) == "3:11"
    assert ll.format_duration(60) == "1:00"
    assert ll.format_duration(None) == "—"
    assert ll.format_duration(0) == "—"
    assert ll.format_duration("bad") == "—"


def test_clean_track_stem_strips_hex_suffixes():
    assert ll.clean_track_stem("늦은 대답-8df69261") == "늦은 대답"
    assert ll.clean_track_stem("เงาของพระราม-9-b099c8aa") == "เงาของพระราม-9"
    assert ll.clean_track_stem("plain-title") == "plain-title"  # short, non-hex
    assert ll.clean_track_stem("song-abcdef12-deadbeef") == "song"


def test_song_track_label_format():
    t = {"project": "방콕-시티팝-Vol.01", "title": "늦은 대답", "duration_sec": 191}
    assert ll.song_track_label(t) == "방콕-시티팝-Vol.01 · 늦은 대답 (3:11)"
    t2 = {"project": "", "title": "독립곡", "duration_sec": 65, "name": "x.mp3"}
    assert ll.song_track_label(t2) == "독립곡 (1:05)"


def test_song_entry_label_matches_track_label_shape():
    song = {"title": "늦은 대답", "duration": 191}
    assert ll.song_entry_label("방콕-시티팝-Vol.01", song) == \
        "방콕-시티팝-Vol.01 · 늦은 대답 (3:11)"


# ─── Track enrichment (Library ↔ Renderer identical names) ──────────────────

def test_enrich_tracks_maps_manifest_file_path(monkeypatch, tmp_path):
    root = tmp_path / "song_projects"
    mp3 = root / "P1" / "songs" / "밤이 지나면-abc12345.mp3"
    _make_song_project(root, "P1", [
        {"title": "밤이 지나면", "file_path": str(mp3), "duration": 200},
    ])
    mp3.write_bytes(b"x")
    _patch_song_root(monkeypatch, root)

    tracks = [{"path": str(mp3), "name": mp3.name, "duration_sec": 200.0,
               "source": "song_project"}]
    out = ll.enrich_tracks_with_song_library(tracks)
    assert out[0]["project"] == "P1"
    assert out[0]["title"] == "밤이 지나면"
    assert out[0]["library_label"] == "P1 · 밤이 지나면 (3:20)"


def test_enrich_tracks_fallback_infers_from_path_and_title_prefix(monkeypatch, tmp_path):
    root = tmp_path / "song_projects"
    # Manifest lists the song by title but with NO file_path (submitted-on-Suno)
    _make_song_project(root, "방콕-Vol.01", [
        {"title": "เงาของพระราม-9", "file_path": "", "duration": None},
    ])
    mp3 = root / "방콕-Vol.01" / "songs" / "เงาของพระราม-9-4f3a2b1c.mp3"
    mp3.parent.mkdir(parents=True, exist_ok=True)
    mp3.write_bytes(b"x")
    _patch_song_root(monkeypatch, root)

    tracks = [{"path": str(mp3), "name": mp3.name, "duration_sec": 180.0,
               "source": "song_project"}]
    out = ll.enrich_tracks_with_song_library(tracks)
    assert out[0]["project"] == "방콕-Vol.01"
    # Filename stem starts with the manifest title → manifest title wins
    assert out[0]["title"] == "เงาของพระราม-9"


def test_group_track_indices_by_project():
    tracks = [
        {"project": "A"}, {"project": "B"}, {"project": "A"}, {"project": ""},
    ]
    groups = ll.group_track_indices_by_project(tracks)
    assert groups == {"A": [0, 2], "B": [1]}


# ─── Image library labels ────────────────────────────────────────────────────

def test_thumbnail_session_label_and_list(monkeypatch, tmp_path):
    studio = tmp_path / "studio"
    monkeypatch.setattr(
        "services.thumbnail.session_store._studio_root",
        lambda: studio if studio.mkdir(parents=True, exist_ok=True) is None else studio,
    )
    from services.thumbnail import session_store as ss
    sess = ss.create_session("korea", "rainy night drive", "CityPop Playlist")
    sid = sess["session_id"]
    # No candidates yet → 0/0
    label = ll.thumbnail_session_library_label(sess)
    assert label == f"CityPop Playlist (0/0장 생성됨) · korea · {sid}"

    listed = ll.list_image_library_sessions(limit=5)
    assert listed and listed[0]["session_id"] == sid
    assert listed[0]["library_label"] == label


def test_library_page_uses_shared_labels_source():
    src = Path("app/dashboard.py").read_text(encoding="utf-8")
    assert "list_image_library_sessions" in src
    assert "sess['library_label']" in src


# ─── copy_song_to_project ────────────────────────────────────────────────────

def test_copy_song_to_project_copies_file_and_manifest(monkeypatch, tmp_path):
    root = tmp_path / "song_projects"
    src_mp3 = root / "SRC" / "songs" / "여름이 가도-aa11bb22.mp3"
    _make_song_project(root, "SRC", [
        {"title": "여름이 가도", "file_path": str(src_mp3), "project": "SRC"},
    ])
    src_mp3.write_bytes(b"audio")
    _make_song_project(root, "DST", [])
    _patch_song_root(monkeypatch, root)

    from app.project_manager import copy_song_to_project, get_song_project_songs
    song = get_song_project_songs("SRC")[0]
    entry = copy_song_to_project("DST", song)
    assert entry is not None
    dest = root / "DST" / "songs" / src_mp3.name
    assert dest.exists() and dest.read_bytes() == b"audio"
    dst_songs = get_song_project_songs("DST")
    assert dst_songs[0]["title"] == "여름이 가도"
    assert dst_songs[0]["imported_from_project"] == "SRC"
    assert dst_songs[0]["file_path"] == str(dest)

    # Duplicate copy is skipped
    assert copy_song_to_project("DST", song) is None


def test_copy_song_metadata_only_when_no_file(monkeypatch, tmp_path):
    root = tmp_path / "song_projects"
    _make_song_project(root, "SRC", [
        {"title": "늦은 대답", "file_path": "", "project": "SRC"},
    ])
    _make_song_project(root, "DST", [])
    _patch_song_root(monkeypatch, root)

    from app.project_manager import copy_song_to_project, get_song_project_songs
    song = get_song_project_songs("SRC")[0]
    assert copy_song_to_project("DST", song) is not None
    assert get_song_project_songs("DST")[0]["title"] == "늦은 대답"
    # Same-title duplicate skipped
    assert copy_song_to_project("DST", song) is None


def test_copy_song_missing_file_returns_none(monkeypatch, tmp_path):
    root = tmp_path / "song_projects"
    _make_song_project(root, "SRC", [])
    _make_song_project(root, "DST", [])
    _patch_song_root(monkeypatch, root)
    from app.project_manager import copy_song_to_project
    song = {"title": "유령곡", "file_path": str(tmp_path / "nope.mp3")}
    assert copy_song_to_project("DST", song) is None


# ─── Source wiring checks ─────────────────────────────────────────────────────

def test_video_renderer_mock_assets_default():
    src = Path("app/tabs/video_renderer.py").read_text(encoding="utf-8")
    radio_block = src.split('"오버레이 자산 소스"')[1][:400]
    assert "index=1" in radio_block, "Mock 자산 must be the default asset source"


def test_video_renderer_uses_library_labels_and_project_bulk_select():
    src = Path("app/tabs/video_renderer.py").read_text(encoding="utf-8")
    assert "enrich_tracks_with_song_library" in src
    assert "group_track_indices_by_project" in src
    assert "thumbnail_session_library_label" in src
    assert "프로젝트 폴더 선택" in src
    assert 'key="vr_mp3_sel"' in src


def test_candidate_gallery_offers_library_sessions():
    src = Path("app/tabs/thumbnail_studio.py").read_text(encoding="utf-8")
    gallery = src.split("def _render_candidate_gallery")[1]
    gallery = gallery.split("def _render_brand_thumbnail")[0]
    assert "list_image_library_sessions" in gallery
    assert "이미지 라이브러리" in gallery
    # The hard Prompt Lab prerequisite message is gone from the gallery
    assert "먼저 Prompt Lab에서 프롬프트를 생성하세요" not in gallery


def test_song_lab_project_mode_offers_library_import():
    src = Path("app/tabs/song_lab.py").read_text(encoding="utf-8")
    assert "Song Library에서 곡 가져오기" in src
    assert "copy_song_to_project" in src
    assert "song_entry_label" in src


# ─── AppTest smoke (pages still render) ──────────────────────────────────────

try:
    from streamlit.testing.v1 import AppTest
    _HAS_APPTEST = True
except Exception:
    _HAS_APPTEST = False


@pytest.mark.skipif(not _HAS_APPTEST, reason="streamlit.testing.v1 not available")
def test_video_renderer_page_renders_without_exception():
    at = AppTest.from_file("app/main.py")
    at.session_state["nav_page"] = "video"
    at.run(timeout=30)
    assert not at.exception


@pytest.mark.skipif(not _HAS_APPTEST, reason="streamlit.testing.v1 not available")
def test_thumbnail_studio_page_renders_without_exception():
    at = AppTest.from_file("app/main.py")
    at.session_state["nav_page"] = "thumbnail"
    at.run(timeout=30)
    assert not at.exception


@pytest.mark.skipif(not _HAS_APPTEST, reason="streamlit.testing.v1 not available")
def test_song_lab_page_renders_without_exception():
    at = AppTest.from_file("app/main.py")
    at.session_state["nav_page"] = "song_lab"
    at.run(timeout=30)
    assert not at.exception


@pytest.mark.skipif(not _HAS_APPTEST, reason="streamlit.testing.v1 not available")
def test_library_page_still_renders_with_shared_labels(monkeypatch, tmp_path):
    monkeypatch.setattr("services.thumbnail.session_store._studio_root",
                        lambda: tmp_path / "studio")
    at = AppTest.from_file("app/main.py")
    at.session_state["nav_page"] = "library"
    at.run(timeout=30)
    assert not at.exception
