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
