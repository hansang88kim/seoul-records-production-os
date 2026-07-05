"""
tests/test_song_playback_v048.py — v1.0.0-alpha.48

프로젝트 관리 song list: inline ▶️ playback + project-aware delete.
  * find_song_file resolves audio even when the manifest has no file_path
    (Suno submitted → manually downloaded '{title}-{id}.mp3' into songs/).
  * remove_song_from_project removes the manifest entry (+ file).
  * render_song_list is project-aware and key-namespaced (multiple project
    expanders on one page no longer collide).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def _patch_song_root(monkeypatch, tmp_path) -> Path:
    root = tmp_path / "song_projects"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("app.project_manager._song_projects_root", lambda: root)
    return root


def _make_project(root: Path, name: str, songs: list[dict]) -> Path:
    pdir = root / name
    (pdir / "songs").mkdir(parents=True, exist_ok=True)
    (pdir / "manifest.json").write_text(
        json.dumps({"name": name, "slug": name, "songs": songs},
                   ensure_ascii=False), encoding="utf-8")
    return pdir


# ─── find_song_file ──────────────────────────────────────────────────────────

def test_find_song_file_prefers_manifest_path(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    mp3 = root / "P" / "songs" / "a.mp3"
    _make_project(root, "P", [])
    mp3.write_bytes(b"x")
    from app.project_manager import find_song_file
    assert find_song_file("P", {"title": "무관", "file_path": str(mp3)}) == str(mp3)


def test_find_song_file_resolves_by_title_prefix(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    _make_project(root, "방콕-Vol.01", [])
    mp3 = root / "방콕-Vol.01" / "songs" / "คืนที่อารีย์-8df69261.mp3"
    mp3.write_bytes(b"x")
    from app.project_manager import find_song_file
    # manifest song has NO file_path (submitted on Suno, downloaded manually)
    song = {"title": "คืนที่อารีย์", "file_path": ""}
    assert find_song_file("방콕-Vol.01", song) == str(mp3)


def test_find_song_file_no_match(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    _make_project(root, "P", [])
    from app.project_manager import find_song_file
    assert find_song_file("P", {"title": "없는 곡", "file_path": ""}) == ""


# ─── remove_song_from_project ────────────────────────────────────────────────

def test_remove_song_deletes_manifest_entry_and_file(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    mp3 = root / "P" / "songs" / "여름이 가도-aa11bb22.mp3"
    _make_project(root, "P", [
        {"title": "여름이 가도", "file_path": "", "created_at": "t1"},
        {"title": "밤이 지나면", "file_path": "", "created_at": "t2"},
    ])
    mp3.write_bytes(b"audio")

    from app.project_manager import remove_song_from_project, get_song_project_songs
    ok = remove_song_from_project("P", {"title": "여름이 가도", "created_at": "t1"})
    assert ok is True
    titles = [s["title"] for s in get_song_project_songs("P")]
    assert titles == ["밤이 지나면"]
    assert not mp3.exists()  # resolved via find_song_file and deleted


def test_remove_song_keep_file_option(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    mp3 = root / "P" / "songs" / "늦은 대답-cc33.mp3"
    _make_project(root, "P", [{"title": "늦은 대답", "file_path": str(mp3)}])
    mp3.write_bytes(b"audio")
    from app.project_manager import remove_song_from_project, get_song_project_songs
    assert remove_song_from_project("P", {"title": "늦은 대답"}, delete_file=False)
    assert get_song_project_songs("P") == []
    assert mp3.exists()


def test_remove_song_no_match_returns_false(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    _make_project(root, "P", [{"title": "곡A"}])
    from app.project_manager import remove_song_from_project
    assert remove_song_from_project("P", {"title": "곡B"}) is False


# ─── UI wiring ───────────────────────────────────────────────────────────────

def test_song_card_has_playback_and_project_delete():
    src = Path("app/ui/song_card.py").read_text(encoding="utf-8")
    assert "st.audio(" in src
    assert "def render_song_list(songs: list[dict], project_name: str | None = None" in src
    assert "remove_song_from_project" in src
    assert "find_song_file" in src
    assert "key_ns" in src


def test_project_album_passes_project_and_unique_keys():
    src = Path("app/tabs/song_lab.py").read_text(encoding="utf-8")
    assert "render_song_list(songs, project_name=name," in src
    assert 'key_ns=f"proj_{proj[\'slug\']}"' in src


def test_song_card_duration_fallback_reads_file():
    src = Path("app/ui/song_card.py").read_text(encoding="utf-8")
    assert "_file_duration" in src
    assert "mutagen" in src


try:
    from streamlit.testing.v1 import AppTest
    _HAS_APPTEST = True
except Exception:
    _HAS_APPTEST = False


@pytest.mark.skipif(not _HAS_APPTEST, reason="streamlit.testing.v1 not available")
def test_song_lab_project_mode_renders_with_player(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    mp3 = root / "재생테스트" / "songs" / "곡하나-abc123.mp3"
    _make_project(root, "재생테스트", [{"title": "곡하나", "file_path": "",
                                    "status": "submitted", "model": "v5.5"}])
    mp3.write_bytes(b"ID3fakemp3")
    at = AppTest.from_file("app/main.py")
    at.session_state["nav_page"] = "song_lab"
    at.session_state["song_lab_mode"] = "💿 프로젝트 관리"
    at.run(timeout=30)
    assert not at.exception
