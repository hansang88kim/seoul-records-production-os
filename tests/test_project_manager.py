"""
tests/test_project_manager.py — Song-project folder system tests.
"""
from __future__ import annotations
import json
import shutil
from pathlib import Path
import pytest


@pytest.fixture(autouse=True)
def clean_projects(monkeypatch, tmp_path):
    """Redirect OUTPUTS_DIR to a temp folder for each test."""
    import app.project_manager as pm
    monkeypatch.setattr(pm, "OUTPUTS_DIR", tmp_path)
    yield
    # cleanup handled by tmp_path


def test_song_slug_preserves_korean():
    from app.project_manager import _song_slug
    assert _song_slug("서울 시티팝 Vol.1") == "서울-시티팝-Vol.1"
    assert _song_slug("") == "default"
    assert _song_slug("a/b:c") == "a_b_c"


def test_song_project_dir_creates_songs_folder():
    from app.project_manager import song_project_dir
    d = song_project_dir("테스트 프로젝트")
    assert d.exists()
    assert (d / "songs").exists()


def test_add_song_to_project_and_list():
    from app.project_manager import add_song_to_project, list_song_projects, get_song_project_songs
    song = {"title": "청계천 거리에서", "status": "completed", "file_path": "/tmp/x.mp3"}
    add_song_to_project("서울 시티팝", song)

    projects = list_song_projects()
    assert len(projects) == 1
    assert projects[0]["name"] == "서울 시티팝"
    assert projects[0]["song_count"] == 1

    songs = get_song_project_songs("서울 시티팝")
    assert songs[0]["title"] == "청계천 거리에서"
    assert songs[0]["project"] == "서울 시티팝"


def test_songs_grouped_by_project():
    """Songs in different projects stay separate."""
    from app.project_manager import add_song_to_project, get_song_project_songs
    add_song_to_project("프로젝트A", {"title": "곡1", "file_path": "/tmp/1.mp3"})
    add_song_to_project("프로젝트A", {"title": "곡2", "file_path": "/tmp/2.mp3"})
    add_song_to_project("프로젝트B", {"title": "곡3", "file_path": "/tmp/3.mp3"})

    a_songs = get_song_project_songs("프로젝트A")
    b_songs = get_song_project_songs("프로젝트B")
    assert len(a_songs) == 2
    assert len(b_songs) == 1
    titles_a = {s["title"] for s in a_songs}
    assert titles_a == {"곡1", "곡2"}


def test_project_download_dir_inside_project():
    from app.project_manager import song_project_download_dir, song_project_dir
    pdir = song_project_dir("앨범1")
    dl = song_project_download_dir("앨범1", "노래 제목")
    # Download dir must be under the project's songs/ folder
    assert str(pdir / "songs") in str(dl)


def test_delete_project():
    from app.project_manager import add_song_to_project, delete_song_project, list_song_projects
    add_song_to_project("삭제될프로젝트", {"title": "곡", "file_path": "/tmp/x.mp3"})
    assert len(list_song_projects()) == 1
    assert delete_song_project("삭제될프로젝트") is True
    assert len(list_song_projects()) == 0


def test_manifest_persists_to_disk():
    from app.project_manager import add_song_to_project, _song_manifest_path
    add_song_to_project("디스크테스트", {"title": "곡", "file_path": "/tmp/x.mp3"})
    mpath = _song_manifest_path("디스크테스트")
    assert mpath.exists()
    data = json.loads(mpath.read_text(encoding="utf-8"))
    assert data["name"] == "디스크테스트"
    assert len(data["songs"]) == 1
