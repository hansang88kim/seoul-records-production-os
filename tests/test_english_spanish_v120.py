"""v1.0.0-alpha.120 — 영어(뉴욕)/스페인어(바르셀로나) 추가.

서양권 공략용. 라틴 문자권은 한국어와 글자수 체계가 달라 char_range로 분기하고,
프롬프트의 한국어 전제(작사 규칙·제목 예시)를 언어별로 갈라놓았다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

NEW = ["english", "spanish"]


# ─── 레지스트리 ──────────────────────────────────────────────────────────────

def test_new_languages_registered_with_expected_cities():
    from providers.ai.languages import LANGUAGES

    assert LANGUAGES["english"]["city"] == "New York"
    assert LANGUAGES["spanish"]["city"] == "Barcelona"
    assert LANGUAGES["english"]["lyric_language"] == "English"
    assert LANGUAGES["spanish"]["lyric_language"] == "Spanish"


def test_new_languages_have_every_field_the_prompt_reads():
    """build_system_prompt가 KeyError 없이 돌려면 9개 필드가 모두 있어야 한다."""
    from providers.ai.languages import LANGUAGES

    required = ("label", "lyric_language", "native_name", "city", "city_native",
                "locations", "title_examples", "char_target", "line_chars", "vibe")
    for key in NEW:
        for field in required:
            assert LANGUAGES[key].get(field), f"{key} missing {field}"


def test_new_languages_appear_in_ui_choices():
    from providers.ai.languages import language_choices

    keys = [k for k, _ in language_choices()]
    for key in NEW:
        assert key in keys


# ─── 글자수 밴드 (라틴 문자권) ───────────────────────────────────────────────

def test_latin_languages_get_a_much_larger_char_band():
    """한국어 320-400을 라틴 문자에 그대로 쓰면 곡이 텅 빈다."""
    from providers.ai.languages import char_range

    for key in NEW:
        lo, hi = char_range(key)
        assert lo >= 900, f"{key} floor too low for Latin script: {lo}"
        assert hi > lo


def test_existing_languages_keep_the_original_band():
    from providers.ai.languages import char_range

    for key in ("korean", "japanese", "thai", "vietnamese", "indonesian"):
        assert char_range(key) == (320, 400)


def test_prompt_states_the_language_specific_char_cap():
    from providers.ai.base import build_system_prompt
    from providers.ai.languages import char_range

    for key in NEW + ["korean"]:
        lo, hi = char_range(key)
        sp = build_system_prompt(key)
        assert f"{lo}-{hi} characters" in sp
        assert f"HARD CAP: {hi} chars MAX" in sp


# ─── 한국어 전제 제거 ────────────────────────────────────────────────────────

def test_non_korean_prompts_drop_korean_lyricist_framing():
    """영어/스페인어 가사에 한국어 어미 규칙이 새면 안 된다."""
    from providers.ai.base import build_system_prompt

    for key in NEW:
        sp = build_system_prompt(key)
        assert "KOREAN LYRICIST" not in sp
        assert "전문 작사가" not in sp
        assert "conversational Korean" not in sp
        assert "~어, ~지, ~걸" not in sp
        assert "나는 슬프다" not in sp


def test_non_korean_prompts_use_their_own_title_examples():
    from providers.ai.base import build_system_prompt
    from providers.ai.languages import LANGUAGES

    for key in NEW:
        sp = build_system_prompt(key)
        for example in LANGUAGES[key]["title_examples"]:
            assert example in sp
        # 한국어 제목 예시가 남아있으면 안 된다
        assert "밤이 지나면" not in sp
        assert "청계천 거리" not in sp


def test_korean_prompt_still_has_its_original_framing():
    """한국어 경로는 그대로 유지 — 회귀 방지."""
    from providers.ai.base import build_system_prompt

    sp = build_system_prompt("korean")
    assert "PROFESSIONAL KOREAN LYRICIST (전문 작사가)" in sp
    assert "~어, ~지, ~걸" in sp
    assert "밤이 지나면" in sp
    assert "320-400 characters" in sp


def test_style_is_still_japanese_citypop_for_new_languages():
    """언어가 바뀌어도 장르는 항상 일본 시티팝."""
    from providers.ai.base import build_system_prompt

    for key in NEW:
        sp = build_system_prompt(key)
        assert "Japanese city pop" in sp
        assert "NEVER mention saxophone" in sp


# ─── YouTube 패키징 ──────────────────────────────────────────────────────────

def test_youtube_treats_new_languages_as_non_korean():
    from services.youtube.description_translator import _LANG_NAMES, needs_translation

    assert _LANG_NAMES["english"] == "English"
    assert _LANG_NAMES["spanish"] == "Spanish"
    for key in NEW:
        assert needs_translation(key) is True


def test_youtube_lang_registry_stays_in_sync_with_languages():
    """두 레지스트리가 어긋나면 UI에만 있고 번역이 안 되는 언어가 생긴다."""
    from providers.ai.languages import LANGUAGES
    from services.youtube.description_translator import _LANG_NAMES

    assert set(_LANG_NAMES) == set(LANGUAGES)


def test_youtube_ui_offers_the_new_languages():
    src = Path("app/tabs/youtube_package.py").read_text(encoding="utf-8")
    assert '"english"' in src
    assert '"spanish"' in src


def test_metadata_generates_in_the_new_language(monkeypatch):
    """language='spanish'면 설명이 스페인어로 생성 요청된다."""
    import services.youtube.seo_description as SD
    from services.youtube.metadata_generator import generate_all_metadata

    seen = {}

    def _fake(chapters, **kwargs):
        seen["lang"] = kwargs.get("lang_name")
        return "<desc>"

    monkeypatch.setattr(SD, "generate_seo_description", _fake)
    out = generate_all_metadata("여름밤 시티팝", mood="여름밤", language="spanish")
    assert seen["lang"] == "Spanish"
    assert out["description_translated"] is True
    assert out["description_language"] == "Spanish"
