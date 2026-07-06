"""
tests/test_suno_auto_download_v050.py — v1.0.0-alpha.50, updated in alpha.52.

alpha.52 rule change: final-version selection is no longer "longer always
wins" — it now follows the 180~240s priority rule (see
services/suno_auto_download.py module docstring):
  1. Whichever clip's duration falls in [180, 240]s wins outright.
  2. If both are in range, the longer one wins.
  3. If neither is in range, whichever is closer to the range wins.
  4. If durations are EXACTLY equal, we can't tell them apart — download
     one, but never delete the other on Suno.

Function renamed auto_download_longest → auto_download_final_version
(old name kept as a working alias for backward compatibility).
delete_shorter kwarg renamed → delete_other (the concept generalized: we
no longer always delete "the shorter" one).

plan_suno_cleanup's OWN duration-based fallback (for web-downloaded songs
with no clip id in the filename) is a separate, unrelated code path and
is intentionally left unchanged/untested here — see
tests/test_suno_cleanup_v049.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.suno_auto_download import (
    auto_download_final_version, auto_download_longest,
    _safe_title, _clip_duration, _clip_audio_url,
    _in_range, _distance_to_range, _select_final_clip, _unique_path,
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


def test_old_name_is_a_working_alias():
    assert auto_download_longest is auto_download_final_version


def test_unique_path_appends_numeric_suffix_on_collision(tmp_path):
    dest = tmp_path / "곡_P.mp3"
    assert _unique_path(dest) == dest  # no collision yet

    dest.write_bytes(b"x")
    assert _unique_path(dest) == tmp_path / "곡_P_2.mp3"

    (tmp_path / "곡_P_2.mp3").write_bytes(b"x")
    assert _unique_path(dest) == tmp_path / "곡_P_3.mp3"


# ─── 180-240s 우선순위 규칙 (핵심 로직) ──────────────────────────────────────

def test_in_range_and_distance():
    assert _in_range(180) and _in_range(240) and _in_range(200)
    assert not _in_range(179.9) and not _in_range(240.1)
    assert _distance_to_range(200) == 0
    assert _distance_to_range(170) == 10
    assert _distance_to_range(250) == 10


def test_rule1_one_in_range_wins_outright():
    """190s(범위 안) vs 250s(범위 밖) → 190s가 무조건 승리."""
    a = ("aaaaaaaa", {"duration": 190.0})
    b = ("bbbbbbbb", {"duration": 250.0})
    winner, loser, tie = _select_final_clip(a, b)
    assert winner[0] == "aaaaaaaa" and loser[0] == "bbbbbbbb" and not tie


def test_rule2_both_in_range_longer_wins():
    a = ("aaaaaaaa", {"duration": 200.0})
    b = ("bbbbbbbb", {"duration": 220.0})
    winner, loser, tie = _select_final_clip(a, b)
    assert winner[0] == "bbbbbbbb" and not tie


def test_rule3_neither_in_range_closer_wins_178_vs_170():
    """사용자 예시 1: 178s, 170s → 178s (180에 더 가까움)."""
    a = ("aaaaaaaa", {"duration": 178.0})
    b = ("bbbbbbbb", {"duration": 170.0})
    winner, loser, tie = _select_final_clip(a, b)
    assert winner[0] == "aaaaaaaa" and not tie


def test_rule3_neither_in_range_closer_wins_245_vs_250():
    """사용자 예시 2: 245s, 250s → 245s (240에 더 가까움)."""
    a = ("aaaaaaaa", {"duration": 245.0})
    b = ("bbbbbbbb", {"duration": 250.0})
    winner, loser, tie = _select_final_clip(a, b)
    assert winner[0] == "aaaaaaaa" and not tie


def test_rule4_exact_duration_tie_is_flagged():
    a = ("aaaaaaaa", {"duration": 200.0})
    b = ("bbbbbbbb", {"duration": 200.0})
    winner, loser, tie = _select_final_clip(a, b)
    assert tie is True


def test_symmetric_distance_tie_break_prefers_longer_not_flagged_as_tie():
    """거리가 같아도(경계에서 대칭) 길이가 다르면 결정 가능 — is_tie는 False."""
    a = ("aaaaaaaa", {"duration": 175.0})   # 180-175=5
    b = ("bbbbbbbb", {"duration": 245.0})   # 245-240=5 (동일 거리)
    winner, loser, tie = _select_final_clip(a, b)
    assert winner[0] == "bbbbbbbb"  # 더 긴 245s 선택
    assert not tie


# ─── auto_download_final_version: end-to-end ────────────────────────────────

def test_downloads_in_range_winner_flat_and_deletes_other(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    _make_project(root, "방콕-Vol.01", [
        {"title": "늦은 대답", "file_path": "", "created_at": "t1",
         "task_id": "8df69261,b099c8aa"},
    ])
    fp = _FakeProvider({
        "8df69261": {"id": "8df69261-full", "duration": 250.0, "audio_url": "http://a/8"},
        "b099c8aa": {"id": "b099c8aa-full", "duration": 214.0, "audio_url": "http://a/b"},
    })
    rep = auto_download_final_version("방콕-Vol.01", provider=fp,
                                      downloader=_fake_downloader)

    assert len(rep["downloaded"]) == 1
    d = rep["downloaded"][0]
    assert d["clip_id"] == "b099c8aa"            # 214s가 범위 안(180-240), 250s는 범위 밖
    dest = Path(d["path"])
    assert dest.parent == root / "방콕-Vol.01" / "songs"
    # v1.0.0-alpha.68: filename is "{title}_{project}.mp3" (no clip id) —
    # song has no "project_slug" field here, so it falls back to
    # _song_slug(project_name).
    assert dest.name == "늦은 대답_방콕-Vol.01.mp3"
    assert dest.exists()
    assert fp.deleted == ["8df69261-full"]

    from app.project_manager import get_song_project_songs
    s = get_song_project_songs("방콕-Vol.01")[0]
    assert s["file_path"] == str(dest)
    assert s["duration"] == 214.0
    assert s["status"] == "saved"
    assert s["selected_clip_id"] == "b099c8aa-full"


def test_uses_recorded_project_slug_when_present(monkeypatch, tmp_path):
    """song에 project_slug가 기록돼 있으면 프로젝트명을 재슬러그화하지 않고 그대로 쓴다."""
    root = _patch_song_root(monkeypatch, tmp_path)
    _make_project(root, "P", [
        {"title": "곡", "file_path": "", "task_id": "8df69261,b099c8aa",
         "project_slug": "custom-slug"},
    ])
    fp = _FakeProvider({
        "8df69261": {"id": "8f", "duration": 200, "audio_url": "http://a/8"},
        "b099c8aa": {"id": "bf", "duration": 220, "audio_url": "http://a/b"},
    })
    rep = auto_download_final_version("P", provider=fp, downloader=_fake_downloader)
    dest = Path(rep["downloaded"][0]["path"])
    assert dest.name == "곡_custom-slug.mp3"


def test_existing_file_with_same_computed_name_gets_numeric_suffix(monkeypatch, tmp_path):
    """
    계산된 파일명(dest)이 이미 존재하면 덮어쓰지 않고 _2가 붙는다.

    (find_song_file()의 폴백 스캔은 song["title"]을 있는 그대로 접두 매칭에
    쓰지만, 실제 파일명은 _safe_title()로 금지문자를 치환한 뒤 만들어진다.
    제목에 금지문자가 있으면 그 둘이 갈라져서 find_song_file이 "이미 있음"으로
    잡아내지 못하는 경우가 실제로 있다 — 아래 "곡/1"이 그 예시. 이 테스트는
    바로 그 경로로 dest 충돌·_2 로직 자체를 검증한다.)
    """
    root = _patch_song_root(monkeypatch, tmp_path)
    _make_project(root, "P", [
        {"title": "곡/1", "file_path": "", "task_id": "8df69261,b099c8aa"},
    ])
    songs_dir = root / "P" / "songs"
    existing = songs_dir / "곡_1_P.mp3"  # _safe_title("곡/1") + "_" + "P"
    existing.write_bytes(b"already here")

    fp = _FakeProvider({
        "8df69261": {"id": "8f", "duration": 200, "audio_url": "http://a/8"},
        "b099c8aa": {"id": "bf", "duration": 220, "audio_url": "http://a/b"},
    })
    rep = auto_download_final_version("P", provider=fp, downloader=_fake_downloader)
    assert len(rep["downloaded"]) == 1
    dest = Path(rep["downloaded"][0]["path"])
    assert dest.name == "곡_1_P_2.mp3"
    assert dest.exists()
    assert existing.read_bytes() == b"already here"  # untouched, not overwritten


def test_delete_other_can_be_disabled(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
    _make_project(root, "P", [
        {"title": "곡", "file_path": "", "task_id": "8df69261,b099c8aa"},
    ])
    fp = _FakeProvider({
        "8df69261": {"id": "8f", "duration": 200, "audio_url": "http://a/8"},
        "b099c8aa": {"id": "bf", "duration": 220, "audio_url": "http://a/b"},
    })
    rep = auto_download_final_version("P", provider=fp, delete_other=False,
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
    rep = auto_download_final_version("P", provider=fp, downloader=_fake_downloader)
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
        "8df69261": {"id": "8f", "duration": 200, "audio_url": "http://a/8"},
        "b099c8aa": {"id": "bf", "duration": 220, "audio_url": "http://a/b"},
    })
    rep = auto_download_final_version("P", provider=fp,
                                      downloader=lambda u, d: False)
    assert rep["downloaded"] == []
    assert rep["failed"] and rep["failed"][0]["reason"] == "다운로드 실패"
    assert fp.deleted == []


def test_partial_info_failure_aborts_no_download_no_delete(monkeypatch, tmp_path):
    """클립 하나라도 정보 조회 실패 시 남은 클립을 '정답'으로 오판하지 않는다."""
    root = _patch_song_root(monkeypatch, tmp_path)
    _make_project(root, "P", [
        {"title": "곡", "file_path": "", "task_id": "8df69261,b099c8aa"},
    ])
    fp = _FakeProvider({
        "8df69261": {"id": "8f", "duration": 100, "audio_url": "http://a/8"},
        # b099c8aa 조회 실패 ({} 반환)
    })
    calls = []
    rep = auto_download_final_version(
        "P", provider=fp, downloader=lambda u, d: calls.append(u) or True)
    assert rep["downloaded"] == [] and rep["deleted"] == []
    assert fp.deleted == [] and calls == []
    assert rep["failed"] and "일부 클립 정보 조회 실패" in rep["failed"][0]["reason"]


def test_exact_tie_downloads_but_never_deletes(monkeypatch, tmp_path):
    """두 버전 길이가 정확히 같으면 다운로드만 하고 Suno 삭제는 금지."""
    root = _patch_song_root(monkeypatch, tmp_path)
    _make_project(root, "P", [
        {"title": "곡", "file_path": "", "task_id": "8df69261,b099c8aa"},
    ])
    fp = _FakeProvider({
        "8df69261": {"id": "8f", "duration": 200.0, "audio_url": "http://a/8"},
        "b099c8aa": {"id": "bf", "duration": 200.0, "audio_url": "http://a/b"},
    })
    rep = auto_download_final_version("P", provider=fp, downloader=_fake_downloader)
    assert len(rep["downloaded"]) == 1
    assert fp.deleted == [] and rep["deleted"] == []
    assert any("길이 동일" in s["reason"] for s in rep["skipped"])


# ─── plan 길이 규칙 폴백 (웹 다운로드 곡) — 변경 없음, 그대로 유지 ───────────

def test_plan_duration_fallback_for_web_downloads(monkeypatch, tmp_path):
    root = _patch_song_root(monkeypatch, tmp_path)
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
    assert e["keep_id"] == "8df69261"      # 긴 버전 유지 (이 폴백은 변경 없음)
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
    assert "auto_download_final_version" in src
    assert "최종본 자동 다운로드" in src
    assert "180~240s" in src
    assert "곡별 폴더 없음" in src
    assert 'plan_suno_cleanup(name, provider=_prov)' in src


def test_generation_paths_have_auto_pipeline_hook():
    """생성 완료 즉시(버튼 없이) 자동 다운로드+삭제가 실행되도록 배선 확인."""
    worker = Path("workers/suno_generation_worker.py").read_text(encoding="utf-8")
    assert "auto_download_final_version" in worker
    ui = Path("app/tabs/song_lab.py").read_text(encoding="utf-8")
    assert ui.count("auto_download_final_version") >= 3  # 버튼 1 + 후크 2


def test_hooks_no_longer_silently_swallow_failures():
    """예전엔 except Exception: pass로 완전히 침묵 — 이제는 실패를 보여준다."""
    worker = Path("workers/suno_generation_worker.py").read_text(encoding="utf-8")
    assert "자동 다운로드 파이프라인 오류" in worker
    ui = Path("app/tabs/song_lab.py").read_text(encoding="utf-8")
    assert "자동 다운로드 파이프라인 오류" in ui


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
