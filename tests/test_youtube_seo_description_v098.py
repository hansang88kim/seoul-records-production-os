"""
tests/test_youtube_seo_description_v098.py — SEO city-pop playlist description
(v1.0.0-alpha.98). DJ HANA removed; LLM (OpenAI→Gemini) writes the variable
prose with a mood-aware template fallback; tracklist stays verbatim.
"""
from __future__ import annotations

from services.youtube import seo_description as SEO


def _chapters():
    return [
        {"timestamp": "00:00", "title": "서울의 밤불빛"},
        {"timestamp": "3:04", "title": "서울 불안한 사랑"},
        {"timestamp": "1:02:10", "title": "자정의 정거장"},
    ]


def test_title_is_seo_playlist_format_no_dj_hana():
    t = SEO.generate_seo_title("Korea", 61, "감성 터지는 청량한 여름밤", 18)
    assert t.startswith("[Playlist]")
    assert "서울 시티팝" in t and "18곡" in t
    assert "Korean Seoul City pop Vol.61" in t
    assert "DJ HANA" not in t and "Mixset" not in t


def test_description_fallback_has_all_sections_and_verbatim_tracklist():
    d = SEO.generate_seo_description(_chapters(), mood="네온 가득한 명동의 새벽",
                                     volume=61, use_llm=False)
    for section in ("🏖️ 감성 키워드", "🎧 추천 무드",
                    "🎶 총 3곡 연속 재생", "FAQ 자주 묻는 질문",
                    "🎵 저작권 안내", "© All rights reserved.", "#KoreanCityPop"):
        assert section in d
    # tracklist verbatim + numbered + HH:MM:SS
    assert "00:00:00  01. 서울의 밤불빛" in d
    assert "01:02:10  03. 자정의 정거장" in d
    # DJ HANA persona is gone
    assert "DJ HANA" not in d and "믹스셋" not in d


def test_mood_is_woven_into_fallback():
    d = SEO.generate_seo_description(_chapters(), mood="rainy night drive", use_llm=False)
    assert "rainy night drive" in d


def test_no_chapters_uses_placeholder():
    d = SEO.generate_seo_description([], use_llm=False)
    assert "자동 생성" in d
    assert "총 0곡" in d


def test_suggest_mood_returns_known_and_can_avoid():
    m = SEO.suggest_mood()
    assert m in SEO.SEOUL_MOODS
    # avoiding a value never returns that exact one (pool has >1 entry)
    a = SEO.SEOUL_MOODS[0]
    for _ in range(20):
        assert SEO.suggest_mood(avoid=a) != a


def test_extract_json_tolerates_prose_wrapping():
    assert SEO._extract_json('here you go {"intro":"x","faq":[]} thanks')["intro"] == "x"
    assert SEO._extract_json("no json here") is None


def test_llm_sections_used_when_available(monkeypatch):
    good = ('{"intro":"밤의 서울","keywords":"Neon, Retro","moods":"드라이브 🚗",'
            '"faq":[{"q":"a","a":"b"},{"q":"c","a":"d"},{"q":"e","a":"f"}]}')
    monkeypatch.setattr(SEO, "_call_ORDER", None, raising=False)
    import services.youtube.description_translator as DT
    monkeypatch.setattr(DT, "_call_openai", lambda p: good)
    monkeypatch.setattr(DT, "_call_gemini", lambda p: None)
    d = SEO.generate_seo_description(_chapters(), mood="x", use_llm=True)
    assert "밤의 서울" in d and "Neon, Retro" in d
    # tracklist still verbatim (never from the LLM)
    assert "00:00:00  01. 서울의 밤불빛" in d
