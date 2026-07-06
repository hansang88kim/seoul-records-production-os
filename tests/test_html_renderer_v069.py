"""
tests/test_html_renderer_v069.py — v1.0.0-alpha.69.

services/thumbnail/html_renderer.py: HTML/CSS + Playwright thumbnail
renderer (replaces the PIL-based canva_branding.py for the new 6-form
design system). Playwright-dependent tests skip gracefully when the
browser isn't installed (matches the streamlit.testing.v1 AppTest pattern
already used elsewhere in this suite).
"""
from __future__ import annotations

import pytest
from pathlib import Path

import services.thumbnail.html_renderer as hr

try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as _p:
        _p.chromium.executable_path  # touch — raises if chromium isn't installed
    _HAS_PLAYWRIGHT = True
except Exception:
    _HAS_PLAYWRIGHT = False


# ─── Pure helpers (no browser needed) ───────────────────────────────────────

def test_recommended_font_css_matches_reference_mapping():
    # Ported verbatim from FORMS[].recFont in the reference HTML.
    assert hr.recommended_font_css("A") == "'Cormorant Garamond', serif"
    assert hr.recommended_font_css("B") == "'Playfair Display', serif"
    assert hr.recommended_font_css("C") == "'Bodoni Moda', serif"
    assert hr.recommended_font_css("D") == "'Prata', serif"
    assert hr.recommended_font_css("E") == "'Anton', sans-serif"
    assert hr.recommended_font_css("F") == "'Marcellus', serif"


def test_esc_escapes_html_special_chars():
    assert hr._esc("Rock & Roll <3") == "Rock &amp; Roll &lt;3"
    assert hr._esc("") == ""


def test_chunk_splits_evenly_and_remainder():
    assert hr._chunk(["a", "b", "c", "d", "e"], 2) == [["a", "b"], ["c", "d"], ["e"]]
    assert hr._chunk([], 3) == []


def test_font_italic_weight_lookup():
    italic, weight = hr._font_italic_weight("'Cormorant Garamond', serif")
    assert italic is True and weight == 700
    italic, weight = hr._font_italic_weight("'Montserrat', sans-serif")
    assert italic is False and weight == 800
    # Unknown/custom font string -> safe default, doesn't raise.
    italic, weight = hr._font_italic_weight("'Comic Sans MS', cursive")
    assert italic is False and weight == 700


def test_spine_forms_are_exactly_a_and_b():
    assert hr.SPINE_FORMS == ("A", "B")


def test_render_thumbnail_rejects_unknown_form_or_ratio(tmp_path):
    with pytest.raises(ValueError):
        hr.render_thumbnail(form="Z", ratio="169", bg_image_path="x.png",
                            out_path=str(tmp_path / "out.png"))
    with pytest.raises(ValueError):
        hr.render_thumbnail(form="A", ratio="43", bg_image_path="x.png",
                            out_path=str(tmp_path / "out.png"))


# ─── HTML assembly (no browser — inspect the generated markup) ─────────────

def test_build_html_document_embeds_fit_split_call_only_for_split_layouts():
    html_a = hr._build_html_document(
        form="A", ratio="169", bg_uri="data:image/png;base64,", subj_uri=None,
        kicker="K", title1="Seoul", title2="Nights", badge="", tracks=[],
        title_font_css=hr.recommended_font_css("A"), kr_font_css=hr.DEFAULT_KR_FONT_CSS,
        title_color="#fff", point_color="#e4be6a", spine_bg="#1a1420", spine_text="#f4efe4",
    )
    assert "fitSplit(1280);" in html_a  # split layout -> real measurement needed

    html_b = hr._build_html_document(
        form="B", ratio="169", bg_uri="data:image/png;base64,", subj_uri=None,
        kicker="K", title1="Seoul", title2="Nights", badge="", tracks=[],
        title_font_css=hr.recommended_font_css("B"), kr_font_css=hr.DEFAULT_KR_FONT_CSS,
        title_color="#fff", point_color="#e4be6a", spine_bg="#1a1420", spine_text="#f4efe4",
    )
    # The fitSplit() function is always defined (harmless if unused); only
    # the invocation should be conditional on a split/split_amp layout.
    assert "fitSplit(1280);" not in html_b


def test_build_html_document_a_form_places_cutout_above_darken_below_text():
    """z-index order (spec): background(0) < darken(1) < cutout(2) < text(5)."""
    html = hr._build_html_document(
        form="A", ratio="169", bg_uri="data:image/png;base64,BG", subj_uri="data:image/png;base64,SUBJ",
        kicker="K", title1="Seoul", title2="Nights", badge="", tracks=[],
        title_font_css=hr.recommended_font_css("A"), kr_font_css=hr.DEFAULT_KR_FONT_CSS,
        title_color="#fff", point_color="#e4be6a", spine_bg="#1a1420", spine_text="#f4efe4",
    )
    bg_pos = html.index("base64,BG")
    ov_pos = html.index('class="ov"')
    subj_pos = html.index("base64,SUBJ")
    text_pos = html.index("fit-word")
    assert bg_pos < ov_pos < subj_pos < text_pos
    assert 'style="z-index:2" src="data:image/png;base64,SUBJ"' in html


def test_build_html_document_a_form_without_cutout_has_no_subject_layer():
    """Current behavior (rembg not wired up yet): text-only overlay for A."""
    html = hr._build_html_document(
        form="A", ratio="169", bg_uri="data:image/png;base64,BG", subj_uri=None,
        kicker="K", title1="Seoul", title2="Nights", badge="", tracks=[],
        title_font_css=hr.recommended_font_css("A"), kr_font_css=hr.DEFAULT_KR_FONT_CSS,
        title_color="#fff", point_color="#e4be6a", spine_bg="#1a1420", spine_text="#f4efe4",
    )
    assert 'z-index:2' not in html


def test_build_html_document_11_spine_uses_flexbox_not_multicol():
    """Regression guard for the Chromium vertical-rl + column-width bug the
    spec explicitly calls out — must never regress to column-width."""
    html = hr._build_html_document(
        form="A", ratio="11", bg_uri="data:image/png;base64,", subj_uri=None,
        kicker="K", title1="Seoul", title2="Nights", badge="", tracks=["곡1", "곡2", "곡3"],
        title_font_css=hr.recommended_font_css("A"), kr_font_css=hr.DEFAULT_KR_FONT_CSS,
        title_color="#fff", point_color="#e4be6a", spine_bg="#1a1420", spine_text="#f4efe4",
    )
    assert "flex-direction:row;flex-wrap:wrap" in html
    assert "column-width" not in html
    assert "object-position:0% 30%" in html  # spec: left-anchored crop for spine forms


def test_build_html_document_11_non_spine_form_has_no_spine_markup():
    html = hr._build_html_document(
        form="D", ratio="11", bg_uri="data:image/png;base64,", subj_uri=None,
        kicker="K", title1="Seoul", title2="Nights", badge="NEON SEOUL", tracks=["곡1"],
        title_font_css=hr.recommended_font_css("D"), kr_font_css=hr.DEFAULT_KR_FONT_CSS,
        title_color="#fff", point_color="#e4be6a", spine_bg="#1a1420", spine_text="#f4efe4",
    )
    assert "SEOUL RECORDS</span>" not in html
    assert "NEON SEOUL" in html


# ─── Full render (needs the Playwright Chromium binary) ────────────────────

@pytest.fixture
def bg_image(tmp_path):
    """
    A synthetic but textured (not flat) background — the stddev sanity
    check needs real variance to be meaningful, and a flat solid color
    (e.g. a dark spine-form background) can legitimately sit under the
    threshold even when rendering succeeds perfectly.
    """
    from PIL import Image
    import random
    random.seed(42)
    img = Image.new("RGB", (1600, 900))
    px = img.load()
    # Full-range per-block randomness (not a low-contrast gradient) so any
    # crop/darken/small-sliver treatment (e.g. a 1:1 spine form's narrow
    # photo column) still retains enough variance for the stddev check —
    # a real generated photo has this much contrast everywhere too.
    for y in range(0, 900, 6):
        for x in range(0, 1600, 6):
            color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            for dy in range(6):
                for dx in range(6):
                    if x + dx < 1600 and y + dy < 900:
                        px[x + dx, y + dy] = color
    p = tmp_path / "bg.png"
    img.save(p)
    return str(p)


@pytest.mark.skipif(not _HAS_PLAYWRIGHT, reason="Playwright chromium not installed")
@pytest.mark.parametrize("form", ["A", "B", "C", "D", "E", "F"])
def test_render_thumbnail_169_all_forms_produce_valid_png(form, bg_image, tmp_path):
    out = hr.render_thumbnail(
        form=form, ratio="169", bg_image_path=bg_image,
        kicker="CITYPOP PLAYLIST", title1="Seoul", title2="Nights", badge="NEON SEOUL",
        tracks=["밤이 지나면", "서울의 뒷골목", "한강의 노을"],
        out_path=str(tmp_path / f"{form}_169.png"),
    )
    from PIL import Image
    assert Path(out).exists()
    assert Image.open(out).size == (1920, 1080)
    assert hr._render_stddev(out) >= 20  # not a blank/black load failure


@pytest.mark.skipif(not _HAS_PLAYWRIGHT, reason="Playwright chromium not installed")
@pytest.mark.parametrize("form", ["A", "D"])  # one spine form, one non-spine form
def test_render_thumbnail_11_produces_valid_png(form, bg_image, tmp_path):
    out = hr.render_thumbnail(
        form=form, ratio="11", bg_image_path=bg_image,
        kicker="CITYPOP PLAYLIST", title1="Seoul", title2="Nights", badge="NEON SEOUL",
        tracks=["밤이 지나면", "서울의 뒷골목", "한강의 노을"],
        out_path=str(tmp_path / f"{form}_11.png"),
    )
    from PIL import Image
    assert Path(out).exists()
    assert Image.open(out).size == (3000, 3000)
    assert hr._render_stddev(out) >= 20


@pytest.mark.skipif(not _HAS_PLAYWRIGHT, reason="Playwright chromium not installed")
def test_render_thumbnail_very_long_title_does_not_crash_fit_split(bg_image, tmp_path):
    """fitSplit() must shrink long split-layout titles without erroring out
    (floor is 48px — an extremely long title just clips, but must render)."""
    out = hr.render_thumbnail(
        form="A", ratio="169", bg_image_path=bg_image,
        title1="Extraordinarily Long Seoul Nights", title2="Another Very Long Title Indeed",
        out_path=str(tmp_path / "long_title.png"),
    )
    from PIL import Image
    assert Path(out).exists()
    assert Image.open(out).size == (1920, 1080)
    assert hr._render_stddev(out) >= 20


@pytest.mark.skipif(not _HAS_PLAYWRIGHT, reason="Playwright chromium not installed")
def test_render_thumbnail_subject_cutout_layers_above_background(bg_image, tmp_path):
    """A-form with a real (RGBA) cutout image — full path incl. Playwright,
    not just HTML assembly."""
    from PIL import Image
    cutout = tmp_path / "cutout.png"
    Image.new("RGBA", (400, 800), (255, 0, 0, 180)).save(cutout)

    out = hr.render_thumbnail(
        form="A", ratio="169", bg_image_path=bg_image, subject_cutout_path=str(cutout),
        title1="Seoul", title2="Nights", out_path=str(tmp_path / "a_cutout.png"),
    )
    assert Path(out).exists()
    assert hr._render_stddev(out) >= 20
