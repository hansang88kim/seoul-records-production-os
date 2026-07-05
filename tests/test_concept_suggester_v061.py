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


def test_next_concept_returns_from_pool():
    state = {}
    c = CS.next_concept(state)
    assert c in CS.CITYPOP_CONCEPTS


def test_next_concept_no_immediate_repeat():
    state = {}
    prev = ""
    for _ in range(40):  # more than the pool size → forces reshuffle
        c = CS.next_concept(state, avoid=prev)
        assert c != prev, "immediate repeat returned"
        prev = c


def test_next_concept_walks_whole_pool_before_repeating():
    state = {}
    seen = set()
    # One full cycle should cover every concept exactly once.
    for _ in range(len(CS.CITYPOP_CONCEPTS)):
        seen.add(CS.next_concept(state))
    assert seen == set(CS.CITYPOP_CONCEPTS)


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
