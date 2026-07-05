"""
tests/test_video_background_pick_v047.py — v1.0.0-alpha.47

The Video Renderer picks the 16:9 playback background DIRECTLY
(list_video_backgrounds) instead of picking a thumbnail session and
trusting select_video_background's auto rule — rendering only ever needs
the 16:9 playback background. Also kills the old "⚠️ None" warning path.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from services.thumbnail import asset_types as AT


def _patch_studio(monkeypatch, tmp_path):
    studio = tmp_path / "studio"
    studio.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("services.thumbnail.session_store._studio_root", lambda: studio)
    return studio


def _write_png(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    # 1x1 PNG
    path.write_bytes(bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c626001000000ffff03000006000557bfabd40000000049454e44ae426082"
    ))


def test_list_video_backgrounds_exports_and_sources(monkeypatch, tmp_path):
    _patch_studio(monkeypatch, tmp_path)
    from services.thumbnail import session_store as ss
    from services.thumbnail.video_renderer_rules import (
        list_video_backgrounds, CLEAN_SOURCE_16X9,
    )

    sess = ss.create_session("korea", "rainy night drive", "CityPop Playlist")
    sid = sess["session_id"]

    # 1) exported video playback background
    export = (ss.session_path(sid) / "exports"
              / AT.EXPORT_FILENAMES[AT.VIDEO_PLAYBACK_BACKGROUND_16X9])
    _write_png(export)

    # 2) a clean generated source candidate
    raw = ss.session_path(sid) / "candidates" / "cand_001.png"
    _write_png(raw)
    ss.save_prompts(sid, [{
        "main_prompt": "p", "negative_prompt": "n", "scene": "s",
        "title_safe_area": "", "color_palette": [], "canva_accent_color": "",
        "composition_note": "", "country": "korea", "theme": "t",
    }])
    cands = ss.load_candidates(sid)
    cands[0]["uploaded_image_path"] = str(raw)
    ss.save_candidates(sid, cands)

    options = list_video_backgrounds(limit=10)
    kinds = {o["kind"] for o in options}
    assert "export" in kinds
    assert "source" in kinds

    export_opt = next(o for o in options if o["kind"] == "export")
    assert export_opt["asset_type"] == AT.VIDEO_PLAYBACK_BACKGROUND_16X9
    assert export_opt["is_clean_playback"] is True
    assert export_opt["path"] == str(export)
    assert export_opt["label"].startswith("🎬 영상 배경 16:9 · ")
    assert sid in export_opt["label"]  # Library-identical session label

    source_opt = next(o for o in options if o["kind"] == "source")
    assert source_opt["asset_type"] == CLEAN_SOURCE_16X9
    assert source_opt["is_clean_playback"] is True
    assert source_opt["candidate_id"] == "cand_001"


def test_list_video_backgrounds_empty(monkeypatch, tmp_path):
    _patch_studio(monkeypatch, tmp_path)
    from services.thumbnail.video_renderer_rules import list_video_backgrounds
    assert list_video_backgrounds(limit=5) == []


def test_video_renderer_picks_background_directly():
    src = Path("app/tabs/video_renderer.py").read_text(encoding="utf-8")
    assert "list_video_backgrounds" in src
    assert "16:9 영상 배경 직접 선택" in src
    # Old flow removed: no thumbnail-session picker, no auto rule call,
    # and the "⚠️ None" warning path is gone.
    assert "Thumbnail 세션 선택" not in src
    assert "select_video_background" not in src
    assert "st.warning(f\"⚠️ {bg_info['warning']}\")" not in src


def test_select_video_background_rule_still_intact():
    # Exports 탭 hint + existing tests still rely on the auto rule.
    from services.thumbnail.video_renderer_rules import select_video_background
    assert callable(select_video_background)


try:
    from streamlit.testing.v1 import AppTest
    _HAS_APPTEST = True
except Exception:
    _HAS_APPTEST = False


@pytest.mark.skipif(not _HAS_APPTEST, reason="streamlit.testing.v1 not available")
def test_video_renderer_page_renders_with_new_background_picker():
    at = AppTest.from_file("app/main.py")
    at.session_state["nav_page"] = "video"
    at.run(timeout=30)
    assert not at.exception
