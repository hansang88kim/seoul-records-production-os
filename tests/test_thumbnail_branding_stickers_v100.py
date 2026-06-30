"""
tests/test_thumbnail_branding_stickers_v100.py — auto-composite YouTube stickers.

Verifies the local PIL renderer produces a real 1920x1080 thumbnail with the
equalizer / 구독 / 좋아요 stickers, renders Korean text without crashing, and
records the sticker flags. No network, no Canva.
"""
from __future__ import annotations

import pytest
from pathlib import Path

import services.thumbnail.session_store as ss
from services.thumbnail import canva_branding as cb


@pytest.fixture(autouse=True)
def studio_tmp(monkeypatch, tmp_path):
    monkeypatch.setattr(ss, "_studio_root", lambda: tmp_path / "studio")
    yield


def _png_ok(path: str) -> bool:
    with open(path, "rb") as f:
        return f.read(8) == b"\x89PNG\r\n\x1a\n"


def _bg(sid) -> str:
    from services.thumbnail.image_provider import MockImageGenProvider
    p = ss.image_target_dir(sid) / "bg.png"
    MockImageGenProvider().generate("citypop night", str(p), index=0, meta={})
    return str(p)


def _cand(sid, accent="#00d4ff"):
    return {"candidate_id": "cand_001", "uploaded_image_path": _bg(sid),
            "canva_accent_color": accent}


def test_font_loader_returns_font():
    f = cb._load_font(48, bold=True)
    assert f is not None


def test_branded_thumbnail_renders_png_with_stickers():
    sess = ss.create_session("korea", "neon", "Vol.1")
    sid = sess["session_id"]
    out = cb.mock_render_branded_thumbnail(
        sid, _cand(sid), "Seoul Night", "1990s Drive", "Seoul Records", "#00d4ff",
        show_equalizer=True, show_subscribe=True, show_like=True,
    )
    assert out and Path(out).exists() and _png_ok(out)
    from PIL import Image
    assert Image.open(out).size == (1920, 1080)


def test_branded_korean_title_no_crash():
    sess = ss.create_session("korea", "비 오는 밤", "늦은 대답")
    sid = sess["session_id"]
    out = cb.mock_render_branded_thumbnail(
        sid, _cand(sid), "늦은 대답", "서울 시티팝 Vol.1", "Seoul Records", "#ff4d6d",
    )
    assert out and Path(out).exists() and _png_ok(out)


def test_sticker_flags_recorded_in_metadata(tmp_path):
    sess = ss.create_session("korea", "x", "Vol.2")
    sid = sess["session_id"]
    cb.mock_render_branded_thumbnail(
        sid, _cand(sid), "T", "S", "B", "#00d4ff",
        show_equalizer=True, show_subscribe=False, show_like=True,
    )
    meta = ss.session_path(sid) / "branded" / "thumbnail_branding_metadata.json"
    import json
    data = json.loads(meta.read_text(encoding="utf-8"))
    st = data[-1]["stickers"]
    assert st == {"equalizer": True, "subscribe": False, "like": True}


def test_all_stickers_off_still_renders():
    sess = ss.create_session("korea", "x", "Vol.3")
    sid = sess["session_id"]
    out = cb.mock_render_branded_thumbnail(
        sid, _cand(sid), "Title", "", "Seoul Records", "#00d4ff",
        show_equalizer=False, show_subscribe=False, show_like=False,
    )
    assert out and Path(out).exists() and _png_ok(out)


def test_title_center_layout_renders():
    sess = ss.create_session("korea", "x", "Vol.4")
    sid = sess["session_id"]
    out = cb.mock_render_branded_thumbnail(
        sid, _cand(sid), "센터 제목", "Subtitle", "Seoul Records", "#00d4ff",
        title_layout="center",
    )
    assert out and Path(out).exists() and _png_ok(out)


def test_equalizer_and_pills_helpers_draw(tmp_path):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (600, 200), (0, 0, 0, 255))
    d = ImageDraw.Draw(img, "RGBA")
    cb._draw_equalizer(d, (10, 10, 300, 180), (0, 212, 255), bars=12, seed=1)
    w1, h1 = cb._draw_subscribe(d, 10, 10)
    w2, h2 = cb._draw_like(d, 10, 100, accent_rgb=(255, 77, 109))
    assert w1 > 0 and h1 > 0 and w2 > 0 and h2 > 0
