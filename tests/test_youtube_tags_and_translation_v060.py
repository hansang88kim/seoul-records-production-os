"""
tests/test_youtube_tags_and_translation_v060.py — v1.0.0-alpha.60

Two user requests:
  1. Tags: keep them ENGLISH and fixed, but expand for SEO so the tag
     string is >400 chars (was only ~180/500). generate_tags now returns a
     curated fixed English set filling toward ~480 chars, under the 500
     hard cap.
  2. Description: keep the Korean DJ HANA frame as the base, but when the
     song language is a non-Korean supported language (Thai, Vietnamese,
     Indonesian, Japanese), auto-translate the PROSE frame via OpenAI/
     Gemini while preserving the tracklist verbatim. Tags stay English.
     On missing key / failure, keep the Korean original (never hard-fail).
"""
from __future__ import annotations

import pytest

from services.youtube import metadata_generator as MG
from services.youtube import description_translator as DT
from services.youtube import seo_description as MG_SEO


# ── Tags: English, fixed, SEO-expanded (>400, <500 chars) ──────────────────

def test_tag_string_is_over_400_and_under_500_chars():
    for args in [("Korea", "", 1), ("", "", 1), ("Thailand", "sunset", 3)]:
        tags = MG.generate_tags(*args)
        joined = ",".join(tags)
        assert len(joined) >= 400, f"tags too short: {len(joined)} for {args}"
        assert len(joined) < 500, f"tags over 500: {len(joined)} for {args}"


def test_tags_are_all_english_no_hash():
    tags = MG.generate_tags("Korea", "", 1)
    for t in tags:
        assert not t.startswith("#")
        # No Hangul / Thai / etc. — ASCII-only English tags.
        assert t.isascii(), f"non-English tag: {t}"


def test_core_seo_tags_present():
    tags = [t.lower() for t in MG.generate_tags("", "", 1)]
    for must in ["citypop", "city pop", "playlist", "night drive",
                 "seoul records", "japanese citypop"]:
        assert must in tags


def test_tags_are_stable_fixed_not_random():
    a = MG.generate_tags("Korea", "", 1)
    b = MG.generate_tags("Korea", "", 1)
    assert a == b  # deterministic


# ── v1.0.0-alpha.125: language-aware tags ──────────────────────────────────

def test_korean_playlist_tags_stay_all_english():
    """Korean (default) keeps the original all-English SEO set unchanged."""
    tags = MG.generate_tags("Korea", "", 1, language="korean")
    assert all(t.isascii() for t in tags)
    low = [t.lower() for t in tags]
    assert "korean citypop" in low and "seoul records" in low


def test_thai_playlist_adds_native_thai_tags():
    """A Thai playlist gets native Thai-script tags + Thailand folding, drops
    the Korea-locale tags, but keeps the channel brand."""
    tags = MG.generate_tags("Thailand", "", 1, language="thai")
    low = [t.lower() for t in tags]
    assert "ซิตี้ป็อป" in tags               # Thai 'city pop' (native script)
    assert any(not t.isascii() for t in tags)  # native tags present
    assert "thailand citypop" in low          # country folded in
    assert "seoul records" in low             # channel brand kept
    assert "korean citypop" not in low        # Korea-locale dropped
    assert "seoul night" not in low
    assert "k citypop" not in low


def test_foreign_tags_stay_under_500_chars():
    # YouTube's 500-char tag budget is comma-joined (matches generate_tags' trim).
    for lang, country in [("thai", "Thailand"), ("vietnamese", "Vietnam"),
                          ("japanese", "Japan"), ("indonesian", "Indonesia")]:
        tags = MG.generate_tags(country, "", 1, language=lang)
        assert len(",".join(tags)) < 500, f"{lang} tags over 500"


def test_clean_track_title_strips_space_separated_number():
    """v1.0.0-alpha.125: '01 title' (space, no dot) must not become '01. 01 …'."""
    from services.youtube.metadata_generator import _clean_track_title
    assert _clean_track_title("01 เสียงของคืน.mp3") == "เสียงของคืน"
    assert _clean_track_title("02 곡 제목.wav") == "곡 제목"
    # existing dot/paren behaviour preserved
    assert _clean_track_title("03. 명동의 비.mp3") == "명동의 비"
    assert _clean_track_title("04) Song.mp3") == "Song"
    # a genuine 4-digit numeric-leading title is NOT stripped
    assert _clean_track_title("1980 Tokyo").startswith("1980")


# ── Translation: language gating ───────────────────────────────────────────

def test_needs_translation_gating():
    assert DT.needs_translation("korean") is False
    assert DT.needs_translation("") is False
    assert DT.needs_translation("thai") is True
    assert DT.needs_translation("vietnamese") is True
    assert DT.needs_translation("indonesian") is True
    assert DT.needs_translation("japanese") is True
    assert DT.needs_translation("klingon") is False


def test_korean_is_never_translated():
    desc = MG_SEO.generate_seo_description(
        [{"timestamp": "00:00", "title": "A"}], use_llm=False)
    res = DT.translate_description(desc, "korean")
    assert res["translated"] is False
    assert res["description"] == desc


def test_tracklist_is_split_out_and_preserved(monkeypatch):
    """When translating, the tracklist block must be spliced back verbatim
    and never sent to the model."""
    chapters = [{"timestamp": "00:00", "title": "แสงไฟเยาวราช"},
                {"timestamp": "3:24", "title": "คืนที่อารีย์"}]
    desc = MG_SEO.generate_seo_description(chapters, use_llm=False)

    sent_texts = []

    def fake_translate(text, target, provider_order=("openai", "gemini")):
        sent_texts.append(text)
        # Return a marker so we can see head/tail were translated.
        return f"[{target}]{text}"

    monkeypatch.setattr(DT, "_translate_text", fake_translate)
    res = DT.translate_description(desc, "thai")

    assert res["translated"] is True
    assert res["language"] == "Thai"
    # The exact tracklist lines survive verbatim in the final description.
    assert "00:00:00  01. แสงไฟเยาวราช" in res["description"]
    assert "00:03:24  02. คืนที่อารีย์" in res["description"]
    # The tracklist text was NEVER passed to the translator.
    for sent in sent_texts:
        assert "00:00:00  01." not in sent


def test_translation_falls_back_to_korean_on_failure(monkeypatch):
    desc = MG_SEO.generate_seo_description(
        [{"timestamp": "00:00", "title": "A"}], use_llm=False)

    monkeypatch.setattr(DT, "_translate_text",
                        lambda *a, **k: None)  # simulate no key / failure
    res = DT.translate_description(desc, "vietnamese")
    assert res["translated"] is False
    assert res["language"] == "Korean"
    assert res["description"] == desc


def test_generate_all_metadata_generates_in_song_language(monkeypatch):
    # v1.0.0-alpha.117: description is now generated DIRECTLY in the song's
    # language (not Korean-then-translated). Inject language-marked sections.
    import services.youtube.seo_description as SEO
    monkeypatch.setattr(
        SEO, "_llm_sections",
        lambda mood, vol, n, lang_name="Korean", country="Korea": {
            "intro": f"<{lang_name}>intro", "keywords": "Neon, Retro",
            "moods": f"<{lang_name}>moods",
            "faq": [{"q": "a", "a": "b"}, {"q": "c", "a": "d"}, {"q": "e", "a": "f"}]})
    meta = MG.generate_all_metadata(
        "", "Thailand", 1, "", "", 60, language="thai")
    assert meta["description_translated"] is True
    assert meta["description_language"] == "Thai"
    assert "<Thai>" in meta["description"]      # prose written in the song language
    # v1.0.0-alpha.125: a Thai playlist now carries native Thai-script tags
    # (local discoverability) alongside the English city-pop core.
    assert any(not t.isascii() for t in meta["tags"]), "expected native Thai tags"
    assert "ซิตี้ป็อป" in meta["tags"]
    assert "seoul records" in [t.lower() for t in meta["tags"]]  # brand kept


def test_generate_all_metadata_korean_no_translation():
    meta = MG.generate_all_metadata("", "Korea", 1, "", "", 60, language="korean")
    assert meta["description_translated"] is False
    assert "🏖️ 감성 키워드" in meta["description"]  # untouched Korean SEO frame


def test_translate_can_be_disabled_even_for_foreign_language(monkeypatch):
    called = {"n": 0}

    def spy(*a, **k):
        called["n"] += 1
        return "x"
    monkeypatch.setattr(DT, "_translate_text", spy)

    meta = MG.generate_all_metadata(
        "", "Thailand", 1, "", "", 60, language="thai", translate=False)
    assert called["n"] == 0  # translation skipped
    assert meta["description_translated"] is False


def test_ui_has_language_selector():
    from pathlib import Path
    src = Path("app/tabs/youtube_package.py").read_text(encoding="utf-8")
    assert "yt_language" in src
    assert "곡 언어" in src
    assert "description_translated" in src
