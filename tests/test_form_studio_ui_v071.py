"""
tests/test_form_studio_ui_v071.py — v1.0.0-alpha.71.

app/tabs/thumbnail_studio.py: "🆕 프리미엄 (형태별)" mode (services/thumbnail/
html_renderer.py wired into the UI) + the Prompt Lab form selector that
feeds services/thumbnail/prompt_generator.generate_prompt_batch(form=...).

No Playwright renders here — services/thumbnail/html_renderer.py's own test
suite (test_html_renderer_v069.py) already covers full-render correctness.
These tests only verify the Streamlit wiring holds together.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

SRC = Path("app/tabs/thumbnail_studio.py").read_text(encoding="utf-8")


# ─── Static wiring checks ────────────────────────────────────────────────────

def test_new_mode_registered_and_dispatched():
    assert "🆕 프리미엄 (형태별)" in SRC
    assert "_render_form_studio" in SRC
    assert 'mode.startswith("🆕")' in SRC


def test_form_studio_imports_html_renderer_and_calls_render_thumbnail():
    assert "from services.thumbnail import html_renderer as hr" in SRC
    assert "hr.render_thumbnail(" in SRC


def test_form_studio_exposes_all_controls_from_the_md_spec():
    # 형태, 비율, 폰트(제목/한글), 텍스트(키커/제목1·2/뱃지/트랙), 색상(제목/포인트 + 스파인)
    for needle in (
        "hr.FORMS", "form_studio_ratio", "form_studio_title_font_idx",
        "form_studio_kr_font_idx", "form_studio_kicker", "form_studio_t1",
        "form_studio_t2", "form_studio_badge", "form_studio_tracks",
        "form_studio_title_color", "form_studio_point_color",
        "form_studio_spine_bg", "form_studio_spine_text",
    ):
        assert needle in SRC, f"missing control: {needle}"


def test_prompt_lab_form_selector_feeds_generate_prompt_batch():
    assert "thumb_form_idx" in SRC
    assert "generate_prompt_batch(country_key, theme, count, include_person=include_person,\n" \
           "                                        form=selected_form)" in SRC or \
           "form=selected_form" in SRC


def test_spine_controls_only_shown_for_11_ratio_and_spine_forms():
    assert 'ratio == "11" and form in hr.SPINE_FORMS' in SRC


def test_recommended_font_auto_applied_on_form_change():
    assert '_form_studio_prev_form' in SRC
    assert "hr.FORMS[form]['recFont']" in SRC or 'hr.FORMS[form]["recFont"]' in SRC


# ─── AppTest smoke tests ─────────────────────────────────────────────────────

try:
    from streamlit.testing.v1 import AppTest
    _HAS_APPTEST = True
except Exception:
    _HAS_APPTEST = False


@pytest.mark.skipif(not _HAS_APPTEST, reason="streamlit.testing.v1 not available")
def test_form_studio_mode_with_no_session_shows_info_not_exception():
    at = AppTest.from_file("app/main.py")
    at.session_state["nav_page"] = "thumbnail"
    at.run(timeout=30)
    assert not at.exception

    # The mode radio is the first (unkeyed) radio on the page.
    at.radio[0].set_value("🆕 프리미엄 (형태별)")
    at.run(timeout=30)
    assert not at.exception
    assert any("Prompt Lab" in i.value for i in at.info)


@pytest.mark.skipif(not _HAS_APPTEST, reason="streamlit.testing.v1 not available")
def test_form_studio_mode_with_session_but_no_candidates_shows_warning(monkeypatch, tmp_path):
    import services.thumbnail.session_store as ss
    monkeypatch.setattr(ss, "_studio_root", lambda: tmp_path)
    sess = ss.create_session("korea", "night", "Seoul Nights")

    at = AppTest.from_file("app/main.py")
    at.session_state["nav_page"] = "thumbnail"
    at.session_state["thumb_session_id"] = sess["session_id"]
    at.run(timeout=30)
    at.radio[0].set_value("🆕 프리미엄 (형태별)")
    at.run(timeout=30)
    assert not at.exception
    assert any("선택되지 않았습니다" in w.value for w in at.warning)


@pytest.mark.skipif(not _HAS_APPTEST, reason="streamlit.testing.v1 not available")
def test_form_studio_mode_renders_full_controls_with_selected_candidate(monkeypatch, tmp_path):
    """Full happy path (minus the actual Playwright render click) — every
    control from the .md spec must appear without raising."""
    from PIL import Image
    import services.thumbnail.session_store as ss
    monkeypatch.setattr(ss, "_studio_root", lambda: tmp_path)
    sess = ss.create_session("korea", "night", "Seoul Nights")
    sid = sess["session_id"]

    img_path = tmp_path / sid / "candidates" / "images" / "cand_001.png"
    img_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1024, 1024), (30, 40, 70)).save(img_path)

    candidates = [{
        "candidate_id": "cand_001",
        "uploaded_image_path": str(img_path),
        "rating": "favorite",
        "selected_for_branding": True,
    }]
    ss.save_candidates(sid, candidates)

    at = AppTest.from_file("app/main.py")
    at.session_state["nav_page"] = "thumbnail"
    at.session_state["thumb_session_id"] = sid
    at.run(timeout=30)
    at.radio[0].set_value("🆕 프리미엄 (형태별)")
    at.run(timeout=30)
    assert not at.exception
    # Render button present and NOT disabled (a real image was resolved).
    render_btn = next(b for b in at.button if "렌더링" in (b.label or ""))
    assert render_btn.disabled is False
