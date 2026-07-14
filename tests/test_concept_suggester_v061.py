"""
tests/test_concept_suggester_v061.py — v1.0.0-alpha.61

The AI Composer's concept field used to be an empty box with only a
placeholder. The user asked for a 🎲 변주 button that proposes ONE
city-pop-appropriate concept keyword at a time, cycling so each press
gives something new. services/concept_suggester.py provides that from a
curated Seoul-Records-mood Korean pool (works with zero API keys).
"""
from __future__ import annotations

from services import concept_suggester as CS


def test_pool_is_nonempty_and_korean_citypop():
    assert len(CS.CITYPOP_CONCEPTS) >= 20
    # Sanity: a couple of expected on-brand seeds are present.
    assert "비 오는 서울 밤" in CS.CITYPOP_CONCEPTS
    assert any("한강" in c for c in CS.CITYPOP_CONCEPTS)


def test_pool_spans_diverse_themes():
    # v1.0.0-alpha.104: the pool must NOT be all one late-night/loneliness tone.
    pool = " · ".join(CS.CITYPOP_CONCEPTS)
    assert "면접" in pool or "취준생" in pool          # 20s worries
    assert "첫 데이트" in pool or "짝사랑" in pool       # love (varied)
    assert "재개발" in pool or "월세" in pool            # changing-city hardship
    assert "잘 버텼다" in pool or "다시 시작" in pool     # self-comfort
    assert len(CS._THEME_CATEGORIES) >= 6


def test_next_concept_returns_from_pool():
    # use_llm=False keeps it pool-only + deterministic, independent of env keys.
    state = {}
    c = CS.next_concept(state, use_llm=False)
    assert c in CS.CITYPOP_CONCEPTS


def test_next_concept_no_immediate_repeat():
    state = {}
    prev = ""
    for _ in range(60):  # more than the pool size → forces reshuffle
        c = CS.next_concept(state, avoid=prev, use_llm=False)
        assert c != prev, "immediate repeat returned"
        prev = c


def test_next_concept_walks_whole_pool_before_repeating():
    state = {}
    seen = set()
    # One full cycle should cover every concept exactly once (pool path).
    for _ in range(len(CS.CITYPOP_CONCEPTS)):
        seen.add(CS.next_concept(state, use_llm=False))
    assert seen == set(CS.CITYPOP_CONCEPTS)


def test_next_concept_uses_llm_when_available(monkeypatch):
    # v1.0.0-alpha.104: with a key present, each press GENERATES a fresh concept.
    import services.youtube.description_translator as DT
    monkeypatch.setattr(DT, "_call_openai", lambda p: "면접을 마치고 나온 오후")
    monkeypatch.setattr(DT, "_call_gemini", lambda p: None)
    c = CS.next_concept({}, use_llm=True)
    assert c == "면접을 마치고 나온 오후"          # fresh, not necessarily in the pool


def test_llm_fresh_concept_falls_back_on_failure(monkeypatch):
    import services.youtube.description_translator as DT
    monkeypatch.setattr(DT, "_call_openai", lambda p: None)
    monkeypatch.setattr(DT, "_call_gemini", lambda p: None)
    assert CS._llm_fresh_concept("x") == ""       # no key/failure → empty → caller uses pool


def test_suggest_many_distinct():
    picks = CS.suggest_many(5)
    assert len(picks) == 5
    assert len(set(picks)) == 5


def test_suggest_many_clamps_to_pool_size():
    picks = CS.suggest_many(9999)
    assert len(picks) == len(CS.CITYPOP_CONCEPTS)


def test_ui_has_variation_button_in_both_composers():
    from pathlib import Path
    for path in ["app/ui/composer_panel.py", "app/tabs/song_lab.py"]:
        src = Path(path).read_text(encoding="utf-8")
        assert "next_concept" in src, f"{path} missing variation wiring"
        assert "변주" in src or "🎲" in src
