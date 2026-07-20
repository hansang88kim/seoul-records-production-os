"""v1.0.0-alpha.121 — 국가/도시·무드가 제목·설명에 실제로 반영된다.

증상: 국가/도시를 '일본, 도쿄, 시부야'로 넣고 언어를 English로 골라도, 제목·설명이
한국어 + Seoul 고정으로 나왔다. country/lang_name이 인자로만 받아지고 프롬프트에
전혀 안 들어가고 있었다.
"""
from __future__ import annotations

import services.youtube.seo_description as SEO


TOKYO = "일본, 도쿄, 시부야"


# ─── 제목 ────────────────────────────────────────────────────────────────────

def test_title_prompt_carries_country_and_language():
    p = SEO._title_prompt("여름, 이별", volume=1, n_tracks=19,
                          country=TOKYO, lang_name="English")
    assert TOKYO in p
    assert "in English" in p
    assert f"'{TOKYO} City Pop'" in p
    # 다른 도시가 강제되면 안 된다
    assert "Korean Seoul City Pop" not in p


def test_title_prompt_includes_the_mood():
    p = SEO._title_prompt("비 내리는 서울밤", volume=1, n_tracks=5)
    assert "비 내리는 서울밤" in p


def test_title_fallback_uses_the_chosen_country():
    t = SEO.generate_seo_title(country=TOKYO, volume=2, mood="여름",
                               n_tracks=19, use_llm=False)
    assert TOKYO in t
    assert "서울" not in t
    assert "Seoul" not in t


def test_title_fallback_keeps_original_wording_for_korea():
    """한국 기본값은 기존 문구 그대로 — 회귀 방지."""
    t = SEO.generate_seo_title(country="Korea", volume=61, mood="여름밤",
                               n_tracks=18, use_llm=False)
    assert "한국 서울 시티팝" in t
    assert "Korean Seoul City pop Vol.61" in t


# ─── 설명 ────────────────────────────────────────────────────────────────────

def test_sections_prompt_carries_country_and_language():
    p = SEO._sections_prompt("여름, 이별", volume=1, n_tracks=19,
                             lang_name="English", country=TOKYO)
    assert TOKYO in p
    assert f"SET IN {TOKYO}" in p
    assert "in English" in p
    # Seoul 하드코딩이 남아있으면 안 된다
    assert "Seoul's night" not in p
    assert "Korean Seoul City Pop" not in p


def test_description_passes_country_down_to_the_prompt(monkeypatch):
    seen = {}

    def _spy(mood, volume, n_tracks, lang_name="Korean", country="Korea"):
        seen["country"] = country
        seen["lang"] = lang_name
        return None                      # LLM 실패 → 폴백 경로

    monkeypatch.setattr(SEO, "_llm_sections", _spy)
    SEO.generate_seo_description([], mood="여름", country=TOKYO,
                                 lang_name="English")
    assert seen["country"] == TOKYO
    assert seen["lang"] == "English"


def test_fallback_description_drops_seoul_landmarks_for_other_cities():
    out = SEO.generate_seo_description([], mood="여름", country=TOKYO,
                                       use_llm=False)
    assert TOKYO in out
    for landmark in ("남산", "한강", "을지로", "명동", "청계천"):
        assert landmark not in out


def test_fallback_description_keeps_seoul_landmarks_for_korea():
    out = SEO.generate_seo_description([], mood="여름", country="Korea",
                                       use_llm=False)
    assert "남산" in out
    assert "한국형 시티팝 컬렉션" in out


# ─── metadata_generator 배선 ─────────────────────────────────────────────────

def test_metadata_generator_passes_language_to_the_title(monkeypatch):
    """언어를 English로 고르면 제목도 English로 생성 요청돼야 한다."""
    import services.youtube.metadata_generator as MG

    seen = {}

    def _fake_title(country="Korea", volume=1, mood="", n_tracks=0,
                    edition="Disco Edition", use_llm=True, lang_name="Korean"):
        seen["country"] = country
        seen["lang"] = lang_name
        return "[Playlist] x"

    monkeypatch.setattr(SEO, "generate_seo_title", _fake_title)
    monkeypatch.setattr(SEO, "generate_seo_description",
                        lambda *a, **k: "<desc>")
    MG.generate_all_metadata("", country=TOKYO, volume=1, mood="여름",
                             language="english")
    assert seen["country"] == TOKYO
    assert seen["lang"] == "English"
