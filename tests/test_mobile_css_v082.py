"""
tests/test_mobile_css_v082.py — the Streamlit app ships mobile-responsive CSS.

The app's look is a large inline <style> block injected in app/main.py. Before
v1.0.0-alpha.82 it had NO mobile breakpoint, so on phones the 18px/2.6rem
desktop scale squeezed content and button/radio labels were clipped by
`white-space:nowrap; text-overflow:ellipsis`. These tests assert the mobile
media query and its key fixes are present (static source check — no browser).
"""
from __future__ import annotations

import re
from pathlib import Path

MAIN = Path("app/main.py").read_text(encoding="utf-8")
STYLE = MAIN.split("<style>", 1)[1].split("</style>", 1)[0]
# just the @media (max-width: 640px){...} body
_M = re.search(r"@media \(max-width: 640px\)\s*\{(.*)\n    \}\n", STYLE, re.DOTALL)
MOBILE = _M.group(1) if _M else ""


def test_mobile_media_query_present():
    assert "@media (max-width: 640px)" in STYLE
    assert MOBILE, "mobile media-query body not found"


def test_mobile_reduces_root_font_and_container_padding():
    assert "html { font-size: 15px; }" in MOBILE
    # container side padding drops from the desktop 2.6rem to <=1.1rem
    assert re.search(r"\.block-container \{ padding: 1\.1rem 0\.85rem", MOBILE)


def test_mobile_buttons_wrap_not_clip():
    # the desktop rule ellipsis-clips button labels; mobile must un-clip them
    assert "white-space: normal" in MOBILE
    assert "text-overflow: clip" in MOBILE
    assert "height: auto" in MOBILE


def test_mobile_radio_wraps():
    assert "flex-wrap: wrap" in MOBILE  # mode-selector radios wrap on mobile


def test_desktop_button_rule_still_clips():
    # desktop behavior unchanged (nowrap+ellipsis) OUTSIDE the media query
    desktop = STYLE.split("@media (max-width: 640px)")[0]
    assert "white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" in desktop


def test_mobile_stacks_columns_for_full_width_inputs():
    # v1.0.0-alpha.83: multi-column rows stack on mobile so selectboxes/inputs
    # get full width (fixes the cramped/truncated mood picker).
    assert 'min-width: 100% !important' in MOBILE
    assert '[data-testid="stHorizontalBlock"] > [data-testid="stColumn"]' in MOBILE


def test_mobile_keeps_tight_action_rows_horizontal():
    # song-list action buttons opt out of stacking via st.container(key="srx-actrow…")
    assert 'st-key-srx-actrow' in MOBILE
    assert 'flex-wrap: nowrap !important' in MOBILE


def test_song_list_is_compact_card_layout():
    # v1.0.0-alpha.83: the song list no longer uses the 6-column table (which
    # stacked into ~10 lines/song on mobile); it uses a compact card + a
    # keyed action row that stays horizontal.
    src = Path("app/ui/song_card.py").read_text(encoding="utf-8")
    assert 'st.container(key=f"srx-actrow-' in src
    assert 'st.columns([0.4, 3, 0.8, 0.8, 0.6, 2.4])' not in src  # old 6-col table gone


def test_style_block_braces_balanced():
    assert STYLE.count("{") == STYLE.count("}")
