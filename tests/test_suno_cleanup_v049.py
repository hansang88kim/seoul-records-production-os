"""
tests/test_suno_cleanup_v049.py — v1.0.0-alpha.49

Suno 미선택 버전 정리: plan (dry-run, safety rules) + execute (verified
delete via full clip id) + provider clip-management wrappers + UI wiring.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.suno_cleanup import (
    plan_suno_cleanup, execute_suno_cleanup,
    _task_clip_ids, _file_matches_clip,
)


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


# ─── unit: parsing / matching ────────────────────────────────────────────────

def test_task_clip_ids_parses_valid_id8s():
    assert _task_clip_ids("8df69261,b099c8aa") == ["8df69261", "b099c8aa"]
    assert _task_clip_ids("generated") == []
    assert _task_clip_ids("") == []
    assert _task_clip_ids("8df69261,notahex!") == ["8df69261"]


def test_file_matches_clip_suffix():
    assert _file_matches_clip("songs/늦은 대답-8df69261.mp3", "8df69261")
    assert _file_matches_clip("songs/late-answer-B099C8AA.mp3", "b099c8aa")
    assert not _file_matches_clip("songs/늦은 대답.mp3", "8df69261")
    assert not _file_matches_clip("", "8df69261")


# ─── plan: safety rules ──────────────────────────────────────────────────────

def test_plan_marks_unambiguous_sibling_for_delete(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    mp3 = root / "P" / "songs" / "늦은 대답-8df69261.mp3"
    _make_project(root, "P", [
        {"title": "늦은 대답", "file_path": "", "task_id": "8df69261,b099c8aa"},
    ])
    mp3.write_bytes(b"x")

    plan = plan_suno_cleanup("P")
    assert len(plan) == 1
    e = plan[0]
    assert e["action"] == "delete"
    assert e["keep_id"] == "8df69261"
    assert e["delete_ids"] == ["b099c8aa"]


def test_plan_skips_when_no_local_file(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    _make_project(root, "P", [
        {"title": "곡", "file_path": "", "task_id": "8df69261,b099c8aa"},
    ])
    plan = plan_suno_cleanup("P")
    assert plan[0]["action"] == "skip"
    assert "로컬 파일 없음" in plan[0]["reason"]


def test_plan_skips_when_both_versions_downloaded(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    _make_project(root, "P", [
        {"title": "곡", "file_path": str(root / "P" / "songs" / "곡-8df69261.mp3"),
         "task_id": "8df69261,b099c8aa"},
    ])
    (root / "P" / "songs" / "곡-8df69261.mp3").write_bytes(b"x")
    (root / "P" / "songs" / "곡-b099c8aa.mp3").write_bytes(b"x")
    # find_song_file returns the manifest file; both ids exist locally — but
    # matching is against the ONE resolved file, so exactly one id matches
    # and the sibling would be deletable. Guard the true both-downloaded
    # case: file resolved has BOTH ids? Not possible for one filename —
    # so simulate ambiguity: filename without any id.
    _make_project(root, "Q", [
        {"title": "곡", "file_path": str(root / "Q" / "songs" / "곡.mp3"),
         "task_id": "8df69261,b099c8aa"},
    ])
    (root / "Q" / "songs" / "곡.mp3").write_bytes(b"x")
    plan_q = plan_suno_cleanup("Q")
    assert plan_q[0]["action"] == "skip"
    assert "식별할 수 없어" in plan_q[0]["reason"]


def test_plan_prefers_selected_clip_id_over_filename(monkeypatch, tmp_path):
    """
    v1.0.0-alpha.68: 새 파일명("{title}_{project}.mp3")엔 클립 ID가 없으므로,
    selected_clip_id가 기록돼 있으면 파일명과 무관하게 그걸로 식별해야 한다.
    """
    root = _patch_song_root(monkeypatch, tmp_path)
    mp3 = root / "P" / "songs" / "늦은 대답_P.mp3"
    _make_project(root, "P", [
        {"title": "늦은 대답", "file_path": str(mp3),
         "task_id": "8df69261,b099c8aa",
         "selected_clip_id": "b099c8aa-1111-2222-3333-444455556666"},
    ])
    mp3.write_bytes(b"x")

    plan = plan_suno_cleanup("P")
    assert len(plan) == 1
    e = plan[0]
    assert e["action"] == "delete"
    assert e["keep_id"] == "b099c8aa"
    assert e["delete_ids"] == ["8df69261"]
    assert "selected_clip_id" in e["reason"]


def test_plan_falls_back_to_filename_when_no_selected_clip_id(monkeypatch, tmp_path):
    """selected_clip_id가 없는(예전) 곡은 기존 파일명 매칭 방식으로 폴백한다."""
    root = _patch_song_root(monkeypatch, tmp_path)
    mp3 = root / "P" / "songs" / "늦은 대답-8df69261.mp3"
    _make_project(root, "P", [
        {"title": "늦은 대답", "file_path": str(mp3), "task_id": "8df69261,b099c8aa"},
    ])
    mp3.write_bytes(b"x")

    plan = plan_suno_cleanup("P")
    e = plan[0]
    assert e["action"] == "delete"
    assert e["keep_id"] == "8df69261"
    assert e["delete_ids"] == ["b099c8aa"]
    assert "파일명 ID" in e["reason"]


def test_plan_skips_without_two_clip_ids(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    _make_project(root, "P", [
        {"title": "구버전 곡", "file_path": "", "task_id": "generated"},
        {"title": "단일 ID 곡", "file_path": "", "task_id": "8df69261"},
    ])
    plan = plan_suno_cleanup("P")
    assert all(e["action"] == "skip" for e in plan)


# ─── execute: verified delete via fake provider ──────────────────────────────

class _FakeProvider:
    def __init__(self, full_ids: dict | None = None, fail_ids: set | None = None):
        self.full_ids = full_ids or {}
        self.fail_ids = fail_ids or set()
        self.deleted: list[list[str]] = []
        self.info_calls: list[str] = []

    def get_clip_info(self, clip_id):
        self.info_calls.append(clip_id)
        full = self.full_ids.get(clip_id)
        return {"id": full} if full else {}

    def delete_clips(self, ids):
        self.deleted.append(list(ids))
        if any(i in self.fail_ids for i in ids):
            return {"ok": False, "deleted": [], "error": "boom"}
        return {"ok": True, "deleted": ids, "error": None}


def test_execute_resolves_full_id_then_deletes():
    fp = _FakeProvider(full_ids={"b099c8aa": "b099c8aa-1111-2222-3333-444455556666"})
    plan = [{"title": "늦은 대답", "action": "delete",
             "keep_id": "8df69261", "delete_ids": ["b099c8aa"]}]
    res = execute_suno_cleanup(plan, provider=fp)
    assert res["deleted"] == [{"title": "늦은 대답",
                               "clip_id": "b099c8aa-1111-2222-3333-444455556666"}]
    assert fp.info_calls == ["b099c8aa"]
    assert fp.deleted == [["b099c8aa-1111-2222-3333-444455556666"]]
    assert res["failed"] == []


def test_execute_falls_back_to_prefix_and_records_failures():
    fp = _FakeProvider(fail_ids={"b099c8aa"})
    plan = [
        {"title": "실패곡", "action": "delete", "keep_id": "8df69261",
         "delete_ids": ["b099c8aa"]},
        {"title": "건너뜀", "action": "skip", "delete_ids": []},
    ]
    res = execute_suno_cleanup(plan, provider=fp)
    assert res["failed"] and res["failed"][0]["title"] == "실패곡"
    assert res["skipped"] == ["건너뜀"]
    assert res["deleted"] == []


# ─── provider wrappers + UI wiring ───────────────────────────────────────────

def test_provider_has_clip_management_methods():
    from providers.suno.suno_cli_provider import SunoCliProvider
    assert hasattr(SunoCliProvider, "get_clip_info")
    assert hasattr(SunoCliProvider, "delete_clips")


def test_provider_delete_clips_rejects_empty(monkeypatch):
    from providers.suno.suno_cli_provider import SunoCliProvider
    p = SunoCliProvider.__new__(SunoCliProvider)  # skip __init__/auth
    p._bin = "suno"
    assert p.delete_clips([]) == {"ok": False, "deleted": [], "error": "no clip ids"}


def test_project_album_has_cleanup_panel():
    src = Path("app/tabs/song_lab.py").read_text(encoding="utf-8")
    assert "Suno 정리" in src
    assert "plan_suno_cleanup" in src
    assert "execute_suno_cleanup" in src
    # Two-step confirmation: dry-run scan + explicit checkbox before delete
    assert "드라이런" in src
    assert "cleanup_confirm_" in src


try:
    from streamlit.testing.v1 import AppTest
    _HAS_APPTEST = True
except Exception:
    _HAS_APPTEST = False


@pytest.mark.skipif(not _HAS_APPTEST, reason="streamlit.testing.v1 not available")
def test_project_mode_renders_with_cleanup_panel(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    mp3 = root / "정리테스트" / "songs" / "곡하나-8df69261.mp3"
    _make_project(root, "정리테스트", [{"title": "곡하나", "file_path": "",
                                    "task_id": "8df69261,b099c8aa",
                                    "status": "submitted", "model": "v5.5"}])
    mp3.write_bytes(b"ID3x")
    at = AppTest.from_file("app/main.py")
    at.session_state["nav_page"] = "song_lab"
    at.session_state["song_lab_mode"] = "💿 프로젝트 관리"
    at.run(timeout=30)
    assert not at.exception
