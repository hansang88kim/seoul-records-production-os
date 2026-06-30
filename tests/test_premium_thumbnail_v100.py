"""
tests/test_premium_thumbnail_v100.py — premium minimal renderer + HD deliverables.

Verifies the shared center-aligned premium renderer and that the three exported
deliverables come out at full resolution with Korean text intact. No network.
"""
from __future__ import annotations

import pytest
from pathlib import Path
from PIL import Image, ImageDraw

import services.thumbnail.session_store as ss
from services.thumbnail import canva_branding as cb
from services.thumbnail import asset_exporter as ae


@pytest.fixture(autouse=True)
def studio_tmp(monkeypatch, tmp_path):
    monkeypatch.setattr(ss, "_studio_root", lambda: tmp_path / "studio")
    yield


def _bg(sid, name="bg.png"):
    from services.thumbnail.image_provider import MockImageGenProvider
    p = ss.image_target_dir(sid) / name
    MockImageGenProvider().generate("citypop night", str(p), index=0, meta={})
    return str(p)


def _png_ok(path: str) -> bool:
    with open(path, "rb") as f:
        return f.read(8) == b"\x89PNG\r\n\x1a\n"


def test_premium_render_size_and_mode():
    sess = ss.create_session("korea", "x", "Vol.1")
    img = cb.render_premium_thumbnail(_bg(sess["session_id"]),
                                      "CityPop Playlist Vol.1", "1990s Night Drive",
                                      "Seoul Records", "#00d4ff", 1920, 1080)
    assert img.size == (1920, 1080)
    assert img.mode == "RGB"


def test_premium_render_korean_title_no_crash():
    sess = ss.create_session("korea", "비", "늦은 대답")
    img = cb.render_premium_thumbnail(_bg(sess["session_id"]),
                                      "늦은 대답", "서울 시티팝 Vol.1",
                                      "Seoul Records", "#ff4d6d", 1920, 1080)
    assert img.size == (1920, 1080)


def test_premium_render_no_title_variant():
    sess = ss.create_session("korea", "x", "Vol.1")
    img = cb.render_premium_thumbnail(_bg(sess["session_id"]), "", "",
                                      "Seoul Records", "#00d4ff", 1920, 1080,
                                      with_title=False)
    assert img.size == (1920, 1080)


def test_branded_thumbnail_is_full_hd():
    sess = ss.create_session("korea", "x", "Vol.1")
    sid = sess["session_id"]
    cand = {"candidate_id": "cand_001", "uploaded_image_path": _bg(sid),
            "canva_accent_color": "#00d4ff"}
    out = cb.mock_render_branded_thumbnail(sid, cand, "센터 제목", "Subtitle",
                                           "Seoul Records", "#00d4ff")
    assert out and _png_ok(out)
    assert Image.open(out).size == (1920, 1080)


def test_letter_spacing_helper():
    img = Image.new("RGBA", (800, 200), (0, 0, 0, 255))
    d = ImageDraw.Draw(img, "RGBA")
    f = cb._load_font(48, bold=True)
    w0 = cb._spaced_width(d, "ABCDE", f, 0)
    w1 = cb._spaced_width(d, "ABCDE", f, 10)
    assert w1 > w0  # tracking widens the text


def test_export_youtube_thumbnail_hd():
    sess = ss.create_session("korea", "x", "Vol.1")
    sid = sess["session_id"]
    out = ae.export_youtube_thumbnail(sid, _bg(sid), "CityPop Playlist Vol.1",
                                      "1990s Night Drive", "Seoul Records", "#00d4ff")
    assert out and Path(out).exists()
    assert Image.open(out).size == (1920, 1080)


def test_export_video_background_clean_hd():
    sess = ss.create_session("korea", "x", "Vol.1")
    sid = sess["session_id"]
    out = ae.export_video_playback_background(sid, _bg(sid), "Seoul Records")
    assert out and Path(out).exists()
    assert Image.open(out).size == (1920, 1080)


def test_export_streaming_cover_square_hires():
    sess = ss.create_session("korea", "x", "Vol.1")
    sid = sess["session_id"]
    out = ae.export_streaming_cover(sid, "", bg_path=_bg(sid),
                                    title="CityPop Playlist Vol.1",
                                    subtitle="1990s Night Drive",
                                    brand_text="Seoul Records", accent_color="#00d4ff")
    assert out and Path(out).exists()
    w, h = Image.open(out).size
    assert w == h and w >= 1440  # square, high-res


def test_font_selection_montserrat_black_title():
    # Hangul detection still works (used for optional sticker fallback)
    assert cb._has_hangul("밤의 끝에서") is True
    assert cb._has_hangul("Night Drive") is False
    # English title -> Montserrat; black=True -> Black (900) weight
    reg = cb._load_font(80, bold=True, text="CityPop Playlist")
    blk = cb._load_font(80, bold=True, text="CityPop Playlist", black=True)
    assert "Montserrat" in reg.getname()[0]
    assert blk.getname() == ("Montserrat", "Black")
    # Pretendard is no longer bundled
    assert not (cb._FONT_DIR / "Pretendard-Bold.otf").exists()


def _count_color(img, target, tol=35):
    px = img.convert("RGB").load()
    W, H = img.size
    n = 0
    for y in range(0, H, 4):
        for x in range(0, W, 4):
            r, g, b = px[x, y]
            if abs(r - target[0]) < tol and abs(g - target[1]) < tol and abs(b - target[2]) < tol:
                n += 1
    return n


def test_title_color_is_applied():
    sid = ss.create_session("korea", "x", "v")["session_id"]
    img = cb.render_premium_thumbnail(_bg(sid), "TITLE", "", "Brand", "#00d4ff",
                                      1920, 1080, title_color="#FF0000")
    assert _count_color(img, (255, 0, 0)) > 50  # red title pixels present


def test_title_scale_changes_size():
    sid = ss.create_session("korea", "x", "v")["session_id"]
    small = cb.render_premium_thumbnail(_bg(sid), "TITLE", "", "Brand", "#00d4ff",
                                        1920, 1080, title_color="#FF0000", title_scale=0.8)
    big = cb.render_premium_thumbnail(_bg(sid), "TITLE", "", "Brand", "#00d4ff",
                                      1920, 1080, title_color="#FF0000", title_scale=1.5)
    assert _count_color(big, (255, 0, 0)) > _count_color(small, (255, 0, 0))


def test_branded_thumbnail_accepts_color_and_scale():
    sid = ss.create_session("korea", "x", "v")["session_id"]
    cand = {"candidate_id": "c1", "uploaded_image_path": _bg(sid),
            "canva_accent_color": "#00d4ff"}
    out = cb.mock_render_branded_thumbnail(sid, cand, "CityPop Playlist", "Sub",
                                           "Seoul Records", "#00d4ff",
                                           title_color="#FFE7A8", title_scale=1.3)
    assert out and Image.open(out).size == (1920, 1080)


def test_cjk_font_is_noto_and_renders():
    from PIL import Image, ImageDraw
    f = cb._load_cjk_font(80, weight=700)
    assert "Noto" in f.getname()[0]
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    # Kanji + Hangul both have non-zero advance widths (glyphs present, not tofu)
    assert d.textlength("音楽", font=f) > 0
    assert d.textlength("시티팝", font=f) > 0


def test_cjk_subtext_renders_hangul_and_kanji():
    sid = ss.create_session("korea", "x", "v")["session_id"]
    for sub in ["시티팝", "夜の音楽", "音楽", "夜"]:
        img = cb.render_premium_thumbnail(_bg(sid), "TOKYO", "Sub", "Brand", "#00d4ff",
                                          1920, 1080, cjk_subtext=sub)
        assert img.size == (1920, 1080)


def test_branded_thumbnail_with_cjk_subtext():
    sid = ss.create_session("korea", "x", "v")["session_id"]
    cand = {"candidate_id": "c1", "uploaded_image_path": _bg(sid),
            "canva_accent_color": "#00d4ff"}
    out = cb.mock_render_branded_thumbnail(sid, cand, "TOKYO", "Vinyl Jazz",
                                           "Seoul Records", "#00d4ff",
                                           cjk_subtext="夜の音楽")
    assert out and Image.open(out).size == (1920, 1080)


def test_title_defaults_mapping():
    from services.thumbnail.country_presets import get_title_defaults
    assert get_title_defaults("japan")["city"] == "TOKYO"
    assert get_title_defaults("japan")["night_local"] == "夜の音楽"
    assert get_title_defaults("korea")["city"] == "SEOUL"
    assert get_title_defaults("thailand")["night_local"]  # non-empty
    # unknown country falls back to korea
    assert get_title_defaults("atlantis")["city"] == "SEOUL"


def test_script_detection():
    assert cb._has_cjk("夜の音楽") and cb._has_cjk("밤의 음악")
    assert cb._has_thai("ดนตรียามค่ำคืน")
    assert cb._has_devanagari("रात का संगीत")
    assert not cb._has_cjk("Nhac Dem") and not cb._has_thai("Musik Malam")


def test_subtext_font_per_script():
    assert "Noto Sans KR" in cb._load_subtext_font(60, "夜の音楽").getname()[0]
    assert "Thai" in cb._load_subtext_font(60, "ดนตรี").getname()[0]
    assert "Devanagari" in cb._load_subtext_font(60, "रात").getname()[0]
    assert "Montserrat" in cb._load_subtext_font(60, "Nhạc Đêm").getname()[0]


def test_render_all_country_scripts():
    from services.thumbnail.country_presets import get_title_defaults, list_countries
    sid = ss.create_session("korea", "x", "v")["session_id"]
    bgp = _bg(sid)
    for ckey, _ in list_countries():
        d = get_title_defaults(ckey)
        img = cb.render_premium_thumbnail(bgp, d["city"], "CityPop Playlist",
                                          "Seoul Records", "#00d4ff", 1920, 1080,
                                          cjk_subtext=d["night_local"])
        assert img.size == (1920, 1080)


def test_image_prompt_uses_selected_country():
    from services.thumbnail.prompt_generator import generate_flow_prompt
    from services.thumbnail.country_presets import get_culture
    # The image prompt must reflect the selected country, not always Japan.
    th = generate_flow_prompt("thailand", "night", 0)["main_prompt"]
    assert "Thai city-pop" in th and "Bangkok" in th
    assert "Japanese" not in th
    kr = generate_flow_prompt("korea", "night", 0)["main_prompt"]
    assert "Korean city-pop" in kr and "Seoul" in kr
    # Japan still maps to Japanese
    jp = generate_flow_prompt("japan", "night", 0)["main_prompt"]
    assert "Japanese city-pop" in jp
    assert get_culture("vietnam") == "Vietnamese"


def test_dual_ratio_native_generation_and_trim():
    import services.thumbnail.session_store as ss2
    from services.thumbnail.prompt_generator import generate_prompt_batch
    from services.thumbnail.image_provider import _autotrim_bars, _aspect_dims
    from PIL import Image as _Img, ImageDraw as _Dw
    # native dims per aspect
    assert _aspect_dims("16:9") == (1280, 720)
    assert _aspect_dims("1:1") == (1024, 1024)
    # generate_images yields native 16:9 + 1:1 per candidate (mock)
    sid = ss2.create_session("japan", "night", "v")["session_id"]
    cands = ss2.generate_images(sid, generate_prompt_batch("japan", "night", 1), use_real=False)
    c = cands[0]
    assert _Img.open(c["image_16x9"]).size == (1280, 720)
    assert _Img.open(c["image_1x1"]).size == (1024, 1024)
    # autotrim strips uniform white letterbox bars but leaves dark scenes intact
    wl = _Img.new("RGB", (1024, 1024), (255, 255, 255))
    _Dw.Draw(wl).rectangle([0, 224, 1024, 800], fill=(20, 30, 60))
    assert _autotrim_bars(wl).size[1] < 1024
    dark = _Img.new("RGB", (1280, 720), (12, 14, 26))
    assert _autotrim_bars(dark).size == (1280, 720)


def test_cover_prefers_native_square():
    import services.thumbnail.session_store as ss2
    import services.thumbnail.asset_exporter as ae2
    from services.thumbnail.prompt_generator import generate_prompt_batch
    from PIL import Image as _Img
    sid = ss2.create_session("korea", "night", "v")["session_id"]
    c = ss2.generate_images(sid, generate_prompt_batch("korea", "night", 1), use_real=False)[0]
    cover = ae2.export_streaming_cover(sid, "", c["image_16x9"], "SEOUL", "CityPop Playlist",
                                       "Seoul Records", "#00d4ff",
                                       square_bg_path=c["image_1x1"], cjk_subtext="밤의 음악")
    assert cover and _Img.open(cover).size == (3000, 3000)
