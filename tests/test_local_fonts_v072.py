"""
tests/test_local_fonts_v072.py — v1.0.0-alpha.72.

Local-first @font-face for services/thumbnail/html_renderer.py: all 14 font
families are bundled under assets/fonts/ (OFL-licensed) and embedded as
base64 data URIs, with the original Google CDN file kept as an in-rule
fallback src. Verifies the asset files exist, the generated CSS wires them
up correctly, graceful degradation when a local file is missing, and (when
Playwright is available) an actual render with every font CDN domain
blocked in the browser.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import services.thumbnail.html_renderer as hr

try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as _p:
        _p.chromium.executable_path
    _HAS_PLAYWRIGHT = True
except Exception:
    _HAS_PLAYWRIGHT = False


# ─── Asset files actually exist on disk ─────────────────────────────────────

def test_all_font_face_local_files_exist_on_disk():
    missing = [
        local_filename for _, _, _, local_filename, _, _ in hr._FONT_FACES
        if not (hr._FONTS_DIR / local_filename).exists()
    ]
    assert missing == [], f"missing bundled font files: {missing}"


def test_all_ten_title_fonts_and_four_kr_fonts_are_covered():
    families = {family for family, *_ in hr._FONT_FACES}
    title_families = {f["css"].split("'")[1] for f in hr.FONTS}
    kr_families = {f["css"].split("'")[1] for f in hr.KR_FONTS}
    assert title_families <= families
    assert kr_families <= families


def test_license_file_exists_and_documents_ofl():
    licenses = hr._FONTS_DIR / "LICENSES.md"
    assert licenses.exists()
    text = licenses.read_text(encoding="utf-8")
    assert "Open Font License" in text
    for family, *_ in hr._FONT_FACES:
        assert family in text, f"{family} not documented in LICENSES.md"


# ─── font_face_css() generation ──────────────────────────────────────────────

def test_font_face_css_embeds_local_data_uri_for_every_face():
    css = hr.font_face_css()
    assert css.count("@font-face") == len(hr._FONT_FACES)
    assert css.count("data:font/woff2;base64,") == len(hr._FONT_FACES)
    for family, style, weight, _, fallback_url, fallback_format in hr._FONT_FACES:
        assert f"font-family: '{family}'" in css
        assert f"font-style: {style}" in css
        assert f"font-weight: {weight}" in css
        assert fallback_url in css
        assert f"format('{fallback_format}')" in css


def test_font_face_css_is_cached_across_calls():
    assert hr.font_face_css() is hr.font_face_css()


def test_local_src_listed_before_cdn_fallback_src():
    """Per the CSS spec a browser only tries the NEXT src if the current one
    fails — so local must be the first entry, CDN second, in the same rule."""
    css = hr.font_face_css()
    for block in css.split("@font-face")[1:]:
        local_pos = block.find("data:font/woff2;base64,")
        cdn_pos = block.find("fonts.gstatic.com")
        if cdn_pos == -1:
            cdn_pos = block.find("githubusercontent.com")
        assert local_pos != -1 and cdn_pos != -1 and local_pos < cdn_pos


def test_build_html_document_uses_font_face_css_not_a_cdn_link():
    html = hr._build_html_document(
        form="B", ratio="169", bg_uri="data:image/png;base64,", subj_uri=None,
        kicker="K", title1="Seoul", title2="Nights", badge="", tracks=[],
        title_font_css=hr.recommended_font_css("B"), kr_font_css=hr.DEFAULT_KR_FONT_CSS,
        title_color="#fff", point_color="#e4be6a", spine_bg="#1a1420", spine_text="#f4efe4",
    )
    assert "@font-face" in html
    assert "data:font/woff2;base64," in html
    assert '<link href="https://fonts.googleapis.com' not in html


# ─── Graceful degradation when a local file is missing ─────────────────────

def test_font_face_src_falls_back_to_cdn_only_when_local_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(hr, "_FONTS_DIR", tmp_path)  # empty dir — no font files
    src = hr._font_face_src("does-not-exist.woff2", "https://example.com/f.woff2", "woff2")
    assert "data:font/woff2;base64," not in src
    assert "https://example.com/f.woff2" in src


# ─── Real render, all font CDNs blocked (offline/firewalled insurance) ─────

@pytest.mark.skipif(not _HAS_PLAYWRIGHT, reason="Playwright chromium not installed")
def test_render_succeeds_with_every_font_cdn_domain_blocked(tmp_path):
    """
    The actual insurance this feature exists for: block every domain a
    font could conceivably load from (Google Fonts CDN + the GitHub raw
    fallback for Korean fonts) and confirm the render still succeeds with
    healthy pixel variance — i.e. genuinely local, not just CDN-fast.
    """
    from PIL import Image
    import tempfile
    from playwright.sync_api import sync_playwright

    bg = tmp_path / "bg.png"
    Image.new("RGB", (1600, 900), (35, 45, 75)).save(bg)
    bg_uri = hr._image_data_uri(str(bg))

    blocked_hosts = ("fonts.gstatic.com", "fonts.googleapis.com", "githubusercontent.com")
    hits = []

    def handle_route(route, request):
        if any(h in request.url for h in blocked_hosts):
            hits.append(request.url)
            route.abort()
        else:
            route.continue_()

    html = hr._build_html_document(
        form="A", ratio="169", bg_uri=bg_uri, subj_uri=None,
        kicker="CITYPOP PLAYLIST", title1="Seoul", title2="Nights", badge="",
        tracks=["밤이 지나면", "서울의 뒷골목", "한강의 노을"],
        title_font_css=hr.recommended_font_css("A"), kr_font_css=hr.DEFAULT_KR_FONT_CSS,
        title_color="#f6efe2", point_color="#e4be6a", spine_bg="#1a1420", spine_text="#f4efe4",
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as tf:
        tf.write(html)
        html_path = tf.name

    out = str(tmp_path / "offline_render.png")
    logical_w, logical_h = hr._LOGICAL["169"]
    target_w, target_h = hr._TARGET["169"]
    scale = target_w / logical_w

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--ignore-certificate-errors"])
        context = browser.new_context(ignore_https_errors=True, device_scale_factor=scale)
        context.route("**/*", handle_route)
        page = context.new_page()
        page.set_viewport_size({"width": logical_w, "height": logical_h})
        page.goto(f"file://{html_path}")
        page.wait_for_function(
            """() => {
                const imgs=[...document.querySelectorAll('img')];
                return imgs.length>0 && imgs.every(i=>i.complete && i.naturalWidth>0);
            }""",
            timeout=30000,
        )
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(400)
        page.screenshot(path=out)
        browser.close()
    Path(html_path).unlink(missing_ok=True)
    hr._resize_to_exact(out, target_w, target_h)

    assert hits == [], f"font CDN was actually reached despite blocking: {hits}"
    assert Path(out).exists()
    assert Image.open(out).size == (1920, 1080)
    assert hr._render_stddev(out) >= 20
