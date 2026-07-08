"""
tests/test_shared_mood_v062.py — v1.0.0-alpha.62

The song concept, the thumbnail theme, and the YouTube upload mood used to
be three independent text boxes, so they could drift apart (a "비 오는 서울
밤" song with a "summer sunset" thumbnail and a generic description). This
introduces one shared mood (services/shared_mood.py) that all three read
and write, plus a variation ring so the thumbnail tab can offer matching
options in a dropdown. The shared mood is also woven into the YouTube
title/description/tags.
"""
from __future__ import annotations

from services import shared_mood as SM
from services.youtube import metadata_generator as MG
from services.youtube import seo_description as MG_SEO


def test_set_and_get_shared_mood():
    st = {}
    SM.set_shared_mood(st, "비 오는 서울 밤")
    assert SM.get_shared_mood(st) == "비 오는 서울 밤"


def test_shared_mood_is_read_by_all_three_surfaces():
    """One value; song/thumbnail/youtube all read the same key."""
    st = {}
    SM.set_shared_mood(st, "루프탑에서 보는 야경")
    # Whatever surface reads it gets the same string.
    assert SM.get_shared_mood(st) == "루프탑에서 보는 야경"
    assert st[SM.SHARED_MOOD_KEY] == "루프탑에서 보는 야경"


def test_mood_options_include_current_first_and_are_padded():
    st = {}
    SM.set_shared_mood(st, "막차를 놓친 새벽")
    opts = SM.get_mood_options(st)
    assert opts[0] == "막차를 놓친 새벽"
    assert len(opts) > 1  # padded with curated pool


def test_add_variation_registers_in_options_ring():
    st = {}
    SM.set_shared_mood(st, "네온 불빛 골목길")
    new = SM.add_variation(st)
    assert new  # got a suggestion
    assert new in st[SM.SHARED_MOOD_OPTIONS_KEY]
    # add_variation must not silently change the *selected* mood.
    assert SM.get_shared_mood(st) == "네온 불빛 골목길"


def test_options_ring_dedupes_and_caps():
    st = {}
    for i in range(20):
        SM.set_shared_mood(st, f"mood-{i}")
    ring = st[SM.SHARED_MOOD_OPTIONS_KEY]
    assert len(ring) <= 12
    assert len(ring) == len(set(ring))


# ── Mood woven into YouTube metadata ───────────────────────────────────────

def test_mood_appears_in_description_when_set():
    # v1.0.0-alpha.98: SEO description (fallback, no key) weaves the mood in.
    desc = MG_SEO.generate_seo_description(
        [{"timestamp": "00:00", "title": "A"}], mood="rainy night drive", use_llm=False)
    assert "rainy night drive" in desc


def test_no_mood_line_when_mood_empty():
    desc = MG_SEO.generate_seo_description(
        [{"timestamp": "00:00", "title": "A"}], mood="", use_llm=False)
    assert "rainy night drive" not in desc      # nothing spurious injected
    assert "한국형 시티팝" in desc               # still a valid description


def test_english_mood_folds_into_tags():
    tags = MG.generate_tags("Korea", "rainy night drive", 1)
    assert any("rainy night drive" in t for t in tags)
    joined = ",".join(tags)
    assert 400 <= len(joined) < 500


def test_korean_mood_stays_out_of_tags():
    """Tags remain all-English even if the shared mood is Korean."""
    tags = MG.generate_tags("Korea", "비 오는 서울 밤", 1)
    assert all(t.isascii() for t in tags)


def test_core_and_brand_tags_always_survive_trim():
    for mood in ["rainy night drive", "", "sunset drive vibes"]:
        low = [t.lower() for t in MG.generate_tags("Korea", mood, 1)]
        for must in ["citypop", "playlist", "seoul records"]:
            assert must in low, f"{must} missing for mood={mood!r}"


def test_generate_all_metadata_threads_mood_through():
    meta = MG.generate_all_metadata(
        "", "Korea", 1, "neon night drive", "", 60, language="korean")
    assert "neon night drive" in meta["description"]
    assert any("neon night drive" in t for t in meta["tags"])


def test_ui_surfaces_share_mood():
    from pathlib import Path
    thumb = Path("app/tabs/thumbnail_studio.py").read_text(encoding="utf-8")
    yt = Path("app/tabs/youtube_package.py").read_text(encoding="utf-8")
    assert "shared_mood" in thumb and "thumb_theme_select" in thumb
    assert "shared_mood" in yt
    # thumbnail theme is now a dropdown fed by shared options + 🎲
    assert "get_mood_options" in thumb
