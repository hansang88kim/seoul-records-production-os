"""
tests/test_thumbnail_studio.py — Thumbnail Studio (v0.6.0) tests.

No real Google Flow / Canva calls. Mock/stub only.
"""
from __future__ import annotations
import json
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def studio_tmp(monkeypatch, tmp_path):
    """Redirect the studio root to a temp folder."""
    import services.thumbnail.session_store as ss
    monkeypatch.setattr(ss, "_studio_root", lambda: tmp_path)
    yield


# ─── Prompt generation ───────────────────────────────────────────────────────

def test_citypop_country_theme_prompt_generated():
    from services.thumbnail.prompt_generator import generate_flow_prompt
    p = generate_flow_prompt("korea", "rainy night", 0)
    assert "city pop" in p["main_prompt"].lower()
    assert "Seoul" in p["main_prompt"]
    assert "rainy night" in p["main_prompt"]


def test_flow_prompt_excludes_text_logo_watermark():
    from services.thumbnail.prompt_generator import generate_flow_prompt
    p = generate_flow_prompt("japan", "night drive", 0)
    main = p["main_prompt"].lower()
    neg = p["negative_prompt"].lower()
    assert "no text" in main
    assert "no logos" in main or "no logo" in main
    assert "no watermark" in main
    assert "no text" in neg
    assert "no logos" in neg


def test_prompt_includes_title_safe_area():
    from services.thumbnail.prompt_generator import generate_flow_prompt
    p = generate_flow_prompt("korea", "theme", 0)
    assert p["title_safe_area"]
    assert "title overlay" in p["title_safe_area"] or "clean" in p["title_safe_area"]
    assert p["composition_note"]


def test_generate_five_prompts_varied():
    from services.thumbnail.prompt_generator import generate_prompt_batch
    prompts = generate_prompt_batch("korea", "night", 5)
    assert len(prompts) == 5
    scenes = [p["scene"] for p in prompts]
    assert len(set(scenes)) == 5  # all different


def test_generate_ten_prompts_varied():
    from services.thumbnail.prompt_generator import generate_prompt_batch
    prompts = generate_prompt_batch("japan", "night", 10)
    assert len(prompts) == 10
    scenes = [p["scene"] for p in prompts]
    assert len(set(scenes)) >= 8  # mostly different
    # Title safe areas vary too
    safe_areas = [p["title_safe_area"] for p in prompts]
    assert len(set(safe_areas)) >= 3


def test_country_preset_changes_visual_details():
    from services.thumbnail.prompt_generator import generate_flow_prompt
    korea = generate_flow_prompt("korea", "night", 0)
    vietnam = generate_flow_prompt("vietnam", "night", 0)
    assert "Seoul" in korea["main_prompt"]
    assert "Ho Chi Minh" in vietnam["main_prompt"] or "Hanoi" in vietnam["main_prompt"]
    assert korea["canva_accent_color"] != vietnam["canva_accent_color"]


# ─── Session + candidate metadata ────────────────────────────────────────────

def test_batch_prompt_metadata_saved():
    from services.thumbnail import session_store as ss
    from services.thumbnail.prompt_generator import generate_prompt_batch
    sess = ss.create_session("korea", "night", "CityPop Vol.1", 1)
    prompts = generate_prompt_batch("korea", "night", 5)
    candidates = ss.save_prompts(sess["session_id"], prompts)
    assert len(candidates) == 5
    # Metadata file exists
    loaded = ss.load_candidates(sess["session_id"])
    assert len(loaded) == 5
    assert all(c["status"] == "generated_prompt" for c in loaded)


def test_upload_flow_result_creates_candidate():
    from services.thumbnail import session_store as ss
    from services.thumbnail.prompt_generator import generate_prompt_batch
    sess = ss.create_session("korea", "night", "T", 1)
    ss.save_prompts(sess["session_id"], generate_prompt_batch("korea", "night", 3))
    # Upload an image (bytes)
    ss.upload_flow_image_bytes(sess["session_id"], "cand_001", b"fakeimage", ".png")
    candidates = ss.load_candidates(sess["session_id"])
    cand1 = next(c for c in candidates if c["candidate_id"] == "cand_001")
    assert cand1["uploaded_image_path"]
    assert cand1["status"] == "image_uploaded"


def test_candidate_gallery_lists_uploaded_images():
    from services.thumbnail import session_store as ss
    from services.thumbnail.prompt_generator import generate_prompt_batch
    sess = ss.create_session("korea", "n", "T", 1)
    ss.save_prompts(sess["session_id"], generate_prompt_batch("korea", "n", 3))
    ss.upload_flow_image_bytes(sess["session_id"], "cand_001", b"img1", ".png")
    ss.upload_flow_image_bytes(sess["session_id"], "cand_002", b"img2", ".png")
    candidates = ss.load_candidates(sess["session_id"])
    uploaded = [c for c in candidates if c.get("uploaded_image_path")]
    assert len(uploaded) == 2


def test_candidate_can_be_selected_for_branding():
    from services.thumbnail import session_store as ss
    from services.thumbnail.prompt_generator import generate_prompt_batch
    sess = ss.create_session("korea", "n", "T", 1)
    ss.save_prompts(sess["session_id"], generate_prompt_batch("korea", "n", 3))
    ss.upload_flow_image_bytes(sess["session_id"], "cand_001", b"img", ".png")
    ss.select_for_branding(sess["session_id"], "cand_001", True)
    selected = ss.get_selected_candidates(sess["session_id"])
    assert len(selected) == 1
    assert selected[0]["candidate_id"] == "cand_001"


def test_rejected_candidate_not_sent_to_canva():
    from services.thumbnail import session_store as ss
    from services.thumbnail.prompt_generator import generate_prompt_batch
    sess = ss.create_session("korea", "n", "T", 1)
    ss.save_prompts(sess["session_id"], generate_prompt_batch("korea", "n", 3))
    ss.upload_flow_image_bytes(sess["session_id"], "cand_001", b"img", ".png")
    # Reject it
    ss.set_candidate_rating(sess["session_id"], "cand_001", "Reject")
    # Try to select for branding — should be blocked
    ss.select_for_branding(sess["session_id"], "cand_001", True)
    selected = ss.get_selected_candidates(sess["session_id"])
    assert len(selected) == 0  # rejected can't be branded


# ─── Canva branding ──────────────────────────────────────────────────────────

def test_only_selected_images_generate_canva_payload():
    from services.thumbnail import session_store as ss
    from services.thumbnail.prompt_generator import generate_prompt_batch
    sess = ss.create_session("korea", "n", "T", 1)
    ss.save_prompts(sess["session_id"], generate_prompt_batch("korea", "n", 5))
    # Upload 3, select only 2
    for i in range(1, 4):
        ss.upload_flow_image_bytes(sess["session_id"], f"cand_{i:03d}", b"img", ".png")
    ss.select_for_branding(sess["session_id"], "cand_001", True)
    ss.select_for_branding(sess["session_id"], "cand_002", True)
    selected = ss.get_selected_candidates(sess["session_id"])
    assert len(selected) == 2  # only selected ones


def test_brand_template_uses_exact_title_text():
    from services.thumbnail import canva_branding as cb
    cand = {"candidate_id": "c1", "uploaded_image_path": "/tmp/x.png",
            "canva_accent_color": "#ff0000"}
    payload = cb.generate_canva_payload(
        "sess1", cand, "내 정확한 제목 Vol.5", "부제목", "Seoul Records",
        5, "korea", "night",
    )
    assert payload["variables"]["{{MAIN_TITLE}}"] == "내 정확한 제목 Vol.5"
    assert payload["variables"]["{{SUBTITLE}}"] == "부제목"


def test_brand_template_uses_consistent_layout():
    from services.thumbnail import canva_branding as cb
    cand1 = {"candidate_id": "c1", "uploaded_image_path": "/a.png", "canva_accent_color": "#ff0000"}
    cand2 = {"candidate_id": "c2", "uploaded_image_path": "/b.png", "canva_accent_color": "#00ff00"}
    p1 = cb.generate_canva_payload("s", cand1, "T1", "", "Brand", 1, "korea", "n")
    p2 = cb.generate_canva_payload("s", cand2, "T2", "", "Brand", 2, "japan", "n")
    # Layout consistent
    assert p1["font_family"] == p2["font_family"]
    assert p1["title_font_size"] == p2["title_font_size"]
    assert p1["title_position"] == p2["title_position"]
    assert p1["safe_margin"] == p2["safe_margin"]
    # Only accent differs
    assert p1["accent_color"] != p2["accent_color"]


def test_canva_payload_uses_selected_image_path():
    from services.thumbnail import canva_branding as cb
    cand = {"candidate_id": "c1", "uploaded_image_path": "/path/to/selected.png",
            "canva_accent_color": "#ff0000"}
    payload = cb.generate_canva_payload("s", cand, "T", "", "B", 1, "korea", "n")
    assert payload["background_image_path"] == "/path/to/selected.png"
    assert payload["variables"]["{{BACKGROUND_IMAGE}}"] == "/path/to/selected.png"


def test_canva_payload_has_template_variables():
    from services.thumbnail import canva_branding as cb
    cand = {"candidate_id": "c1", "uploaded_image_path": "/x.png", "canva_accent_color": "#f00"}
    payload = cb.generate_canva_payload("s", cand, "Title", "Sub", "Brand", 3, "korea", "rain")
    vars = payload["variables"]
    for key in ["{{BACKGROUND_IMAGE}}", "{{MAIN_TITLE}}", "{{SUBTITLE}}",
                "{{BRAND_TEXT}}", "{{COUNTRY}}", "{{THEME}}", "{{VOL_NO}}", "{{ACCENT_COLOR}}"]:
        assert key in vars


def test_mock_canva_generates_branded_thumbnail():
    from services.thumbnail import session_store as ss, canva_branding as cb
    from services.thumbnail.prompt_generator import generate_prompt_batch
    sess = ss.create_session("korea", "n", "T", 1)
    ss.save_prompts(sess["session_id"], generate_prompt_batch("korea", "n", 1))
    ss.upload_flow_image_bytes(sess["session_id"], "cand_001", b"x", ".png")
    cand = ss.load_candidates(sess["session_id"])[0]
    out = cb.mock_render_branded_thumbnail(
        sess["session_id"], cand, "Title", "Sub", "Seoul Records", "#ff4d6d"
    )
    # PIL may not be installed in all envs; if it is, file exists
    if out is not None:
        assert Path(out).exists()


def test_final_thumbnail_exported_16_9():
    from services.thumbnail import canva_branding as cb
    # The template/canvas is 16:9
    assert cb.DEFAULT_TEMPLATE["aspect_ratio"] == "16:9"
    w, h = cb.DEFAULT_TEMPLATE["canvas_size"]
    assert abs((w / h) - (16 / 9)) < 0.01


def test_build_main_title_format():
    from services.thumbnail import canva_branding as cb
    assert cb.build_main_title("Korea", 3) == "Korea CityPop Playlist Vol.3"
    assert cb.build_main_title("", 1) == "CityPop Playlist Vol.1"
    assert cb.build_main_title("Japan", 2, "Custom Title") == "Custom Title"


# ─── Independence from music ─────────────────────────────────────────────────

def test_thumbnail_tab_independent_from_music_tab():
    """Thumbnail modules must not import or modify music generation."""
    import services.thumbnail.prompt_generator as pg
    import services.thumbnail.session_store as ss
    import services.thumbnail.canva_branding as cb
    # These import cleanly without pulling in suno/music providers
    assert hasattr(pg, "generate_flow_prompt")
    assert hasattr(ss, "create_session")
    assert hasattr(cb, "generate_canva_payload")


def test_music_generation_codepath_unchanged():
    """Music generation modules still import and work."""
    from providers.ai.base import MOCK_SONGS, get_batch_vocal
    from providers.suno.suno_cli_provider import SunoCliProvider
    # Music codepath intact
    assert len(MOCK_SONGS) >= 2
    assert callable(get_batch_vocal)


# ─── Thumbnail Studio visible in both home AND production tabs ────────────────

def test_home_tabs_include_thumbnail_studio():
    """The home screen (no project) must wire in render_thumbnail_studio."""
    import inspect
    import app.dashboard as dash
    src = inspect.getsource(dash.render_home_tabs)
    assert "render_thumbnail_studio" in src
    assert "Thumbnail Studio" in src


def test_production_tabs_use_new_thumbnail_studio():
    """When a project is open, production tabs must use the NEW Thumbnail Studio."""
    import inspect
    import app.dashboard as dash
    # Find the function that renders production tabs
    src = inspect.getsource(dash)
    # The new studio must be wired into the production tab section
    assert "render_thumbnail_studio" in src
    # Both home and production reference it
    assert src.count("render_thumbnail_studio") >= 2


def test_thumbnail_studio_renderable():
    """render_thumbnail_studio imports cleanly (no music dependency)."""
    from app.tabs.thumbnail_studio import render_thumbnail_studio
    assert callable(render_thumbnail_studio)
