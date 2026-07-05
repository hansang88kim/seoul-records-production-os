"""
tests/test_suno_auto_download_v050.py — v1.0.0-alpha.50

길이 규칙 자동화: 두 버전 중 긴 클립을 자동 다운로드(프로젝트 폴더 FLAT,
곡별 폴더 없음)하고 짧은 버전을 Suno에서 삭제 — 사용자 선택 불필요.
plan_suno_cleanup의 길이 규칙 폴백(웹 다운로드로 파일명에 ID가 없는 곡)도
검증한다.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.suno_auto_download import (
    auto_download_longest, _safe_title, _clip_duration, _clip_audio_url,
)
from services.suno_cleanup import plan_suno_cleanup


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


class _FakeProvider:
    """clip_id8 → {id, duration, audio_url} 매핑 기반 페이크."""
    def __init__(self, clips: dict):
        self.clips = clips
        self.deleted: list[str] = []

    def get_clip_info(self, cid):
        return dict(self.clips.get(cid, {}))

    def delete_clips(self, ids):
        self.deleted.extend(ids)
        return {"ok": True, "deleted": ids, "error": None}


def _fake_downloader(url, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"MP3:" + url.encode())
    return True


# ─── helpers ─────────────────────────────────────────────────────────────────

def test_safe_title_strips_forbidden_chars():
    assert _safe_title('밤/의:음악*?"') == "밤_의_음악___"
    assert _safe_title("") == "무제"


def test_clip_duration_and_audio_url_fallbacks():
    assert _clip_duration({"duration": 191.2}) == 191.2
    assert _clip_duration({"metadata": {"duration": 60}}) == 60.0
    assert _clip_duration({}) == 0.0
    assert _clip_audio_url({"audio_url": "u"}) == "u"
    assert _clip_audio_url({}) == ""


# ─── auto download (길이 규칙) ───────────────────────────────────────────────

def test_downloads_longer_clip_flat_and_deletes_shorter(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    _make_project(root, "방콕-Vol.01", [
        {"title": "늦은 대답", "file_path": "", "created_at": "t1",
         "task_id": "8df69261,b099c8aa"},
    ])
    fp = _FakeProvider({
        "8df69261": {"id": "8df69261-full", "duration": 175.0, "audio_url": "http://a/8"},
        "b099c8aa": {"id": "b099c8aa-full", "duration": 214.0, "audio_url": "http://a/b"},
    })
    rep = auto_download_longest("방콕-Vol.01", provider=fp,
                                downloader=_fake_downloader)

    assert len(rep["downloaded"]) == 1
    d = rep["downloaded"][0]
    assert d["clip_id"] == "b099c8aa"            # 더 긴 214s 버전
    dest = Path(d["path"])
    # FLAT: song_projects/<프로젝트>/songs/ 바로 아래, 곡별 폴더 없음
    assert dest.parent == root / "방콕-Vol.01" / "songs"
    assert dest.name == "늦은 대답-b099c8aa.mp3"
    assert dest.exists()

    # 짧은 버전만 Suno에서 삭제 (full id로)
    assert fp.deleted == ["8df69261-full"]

    # manifest 갱신 확인
    from app.project_manager import get_song_project_songs
    s = get_song_project_songs("방콕-Vol.01")[0]
    assert s["file_path"] == str(dest)
    assert s["duration"] == 214.0
    assert s["status"] == "saved"
    assert s["selected_clip_id"] == "b099c8aa-full"


def test_delete_shorter_can_be_disabled(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    _make_project(root, "P", [
        {"title": "곡", "file_path": "", "task_id": "8df69261,b099c8aa"},
    ])
    fp = _FakeProvider({
        "8df69261": {"id": "8f", "duration": 100, "audio_url": "http://a/8"},
        "b099c8aa": {"id": "bf", "duration": 200, "audio_url": "http://a/b"},
    })
    rep = auto_download_longest("P", provider=fp, delete_shorter=False,
                                downloader=_fake_downloader)
    assert rep["downloaded"] and fp.deleted == [] and rep["deleted"] == []


def test_skips_songs_already_downloaded_or_without_ids(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    existing = root / "P" / "songs" / "이미있음-8df69261.mp3"
    _make_project(root, "P", [
        {"title": "이미있음", "file_path": str(existing), "task_id": "8df69261,b099c8aa"},
        {"title": "ID없음", "file_path": "", "task_id": "generated"},
    ])
    existing.write_bytes(b"x")
    fp = _FakeProvider({})
    rep = auto_download_longest("P", provider=fp, downloader=_fake_downloader)
    assert rep["downloaded"] == []
    reasons = " / ".join(s["reason"] for s in rep["skipped"])
    assert "이미 로컬 파일" in reasons and "클립 ID 2개 미기록" in reasons
    assert fp.deleted == []


def test_download_failure_does_not_delete_anything(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    _make_project(root, "P", [
        {"title": "곡", "file_path": "", "task_id": "8df69261,b099c8aa"},
    ])
    fp = _FakeProvider({
        "8df69261": {"id": "8f", "duration": 100, "audio_url": "http://a/8"},
        "b099c8aa": {"id": "bf", "duration": 200, "audio_url": "http://a/b"},
    })
    rep = auto_download_longest("P", provider=fp,
                                downloader=lambda u, d: False)
    assert rep["downloaded"] == []
    assert rep["failed"] and rep["failed"][0]["reason"] == "다운로드 실패"
    assert fp.deleted == []   # 다운로드 실패 시 Suno 삭제 금지


# ─── plan 길이 규칙 폴백 (웹 다운로드 곡) ────────────────────────────────────

def test_plan_duration_fallback_for_web_downloads(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    # 파일명에 클립 ID가 없는 웹 다운로드 파일
    mp3 = root / "P" / "songs" / "곡제목.mp3"
    _make_project(root, "P", [
        {"title": "곡제목", "file_path": str(mp3), "task_id": "8df69261,b099c8aa"},
    ])
    mp3.write_bytes(b"x")
    fp = _FakeProvider({
        "8df69261": {"id": "8f", "duration": 208.0},
        "b099c8aa": {"id": "bf", "duration": 171.0},
    })
    plan = plan_suno_cleanup("P", provider=fp)
    e = plan[0]
    assert e["action"] == "delete"
    assert e["keep_id"] == "8df69261"      # 긴 버전 유지
    assert e["delete_ids"] == ["b099c8aa"]
    assert "길이 규칙" in e["reason"]


def test_plan_duration_fallback_skips_on_tie_or_unknown(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    mp3 = root / "P" / "songs" / "곡제목.mp3"
    _make_project(root, "P", [
        {"title": "곡제목", "file_path": str(mp3), "task_id": "8df69261,b099c8aa"},
    ])
    mp3.write_bytes(b"x")
    fp = _FakeProvider({
        "8df69261": {"id": "8f", "duration": 180.0},
        "b099c8aa": {"id": "bf", "duration": 180.0},
    })
    plan = plan_suno_cleanup("P", provider=fp)
    assert plan[0]["action"] == "skip"
    assert "길이 동일" in plan[0]["reason"]


def test_plan_without_provider_keeps_offline_behavior(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    mp3 = root / "P" / "songs" / "곡제목.mp3"
    _make_project(root, "P", [
        {"title": "곡제목", "file_path": str(mp3), "task_id": "8df69261,b099c8aa"},
    ])
    mp3.write_bytes(b"x")
    plan = plan_suno_cleanup("P")   # provider 없음 → 기존 오프라인 규칙
    assert plan[0]["action"] == "skip"
    assert "식별할 수 없어" in plan[0]["reason"]


# ─── UI wiring ───────────────────────────────────────────────────────────────

def test_project_album_has_auto_download_button():
    src = Path("app/tabs/song_lab.py").read_text(encoding="utf-8")
    assert "auto_download_longest" in src
    assert "최종본 자동 다운로드" in src
    assert "곡별 폴더 없음" in src
    assert 'plan_suno_cleanup(name, provider=_prov)' in src


try:
    from streamlit.testing.v1 import AppTest
    _HAS_APPTEST = True
except Exception:
    _HAS_APPTEST = False


@pytest.mark.skipif(not _HAS_APPTEST, reason="streamlit.testing.v1 not available")
def test_project_mode_renders_with_auto_download(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    _make_project(root, "자동다운", [{"title": "곡", "file_path": "",
                                  "task_id": "8df69261,b099c8aa",
                                  "status": "submitted", "model": "v5.5"}])
    at = AppTest.from_file("app/main.py")
    at.session_state["nav_page"] = "song_lab"
    at.session_state["song_lab_mode"] = "💿 프로젝트 관리"
    at.run(timeout=30)
    assert not at.exception


# ─── 검수 후 강화된 안전규칙 (alpha.50 최종) ─────────────────────────────────

def test_partial_info_failure_aborts_no_download_no_delete(monkeypatch, tmp_path):
    """클립 하나라도 정보 조회 실패 시 남은 클립을 '긴 쪽'으로 오판하지 않는다."""
    root = _patch_song_root(monkeypatch, tmp_path)
    _make_project(root, "P", [
        {"title": "곡", "file_path": "", "task_id": "8df69261,b099c8aa"},
    ])
    fp = _FakeProvider({
        "8df69261": {"id": "8f", "duration": 100, "audio_url": "http://a/8"},
        # b099c8aa 조회 실패 ({} 반환)
    })
    calls = []
    rep = auto_download_longest("P", provider=fp,
                                downloader=lambda u, d: calls.append(u) or True)
    assert rep["downloaded"] == [] and rep["deleted"] == []
    assert fp.deleted == [] and calls == []
    assert rep["failed"] and "일부 클립 정보 조회 실패" in rep["failed"][0]["reason"]


def test_tie_downloads_but_never_deletes(monkeypatch, tmp_path):
    """두 버전 길이가 같으면 규칙 적용 불가 — 다운로드만 하고 삭제는 금지."""
    root = _patch_song_root(monkeypatch, tmp_path)
    _make_project(root, "P", [
        {"title": "곡", "file_path": "", "task_id": "8df69261,b099c8aa"},
    ])
    fp = _FakeProvider({
        "8df69261": {"id": "8f", "duration": 180.0, "audio_url": "http://a/8"},
        "b099c8aa": {"id": "bf", "duration": 180.0, "audio_url": "http://a/b"},
    })
    rep = auto_download_longest("P", provider=fp, downloader=_fake_downloader)
    assert len(rep["downloaded"]) == 1
    assert fp.deleted == [] and rep["deleted"] == []
    assert any("길이 동일" in s["reason"] for s in rep["skipped"])


def test_generation_paths_have_auto_pipeline_hook():
    """생성 완료 즉시(버튼 없이) 자동 다운로드+삭제가 실행되도록 배선 확인."""
    worker = Path("workers/suno_generation_worker.py").read_text(encoding="utf-8")
    assert "auto_download_longest" in worker
    ui = Path("app/tabs/song_lab.py").read_text(encoding="utf-8")
    assert ui.count("auto_download_longest") >= 3  # 버튼 1 + 후크 2
