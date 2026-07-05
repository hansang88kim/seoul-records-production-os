"""
services/shared_mood.py — v1.0.0-alpha.62

A single source of truth for the "mood / theme" that must stay consistent
across the whole pipeline: the SONG concept, the THUMBNAIL theme, and the
YouTube upload mood/description. Previously each of these three had its own
independent text box, so a song about "비 오는 서울 밤" could end up with a
"summer sunset" thumbnail and a generic English YouTube description — they
were never linked.

This module keeps the shared mood in Streamlit's session_state under one
key, plus a small ring of variation suggestions (drawn from
concept_suggester) so the thumbnail tab can offer them as a dropdown that
matches whatever the composer just used. Pure helpers here; the UI wires
them in.
"""
from __future__ import annotations

SHARED_MOOD_KEY = "shared_mood"
SHARED_MOOD_OPTIONS_KEY = "shared_mood_options"


def get_shared_mood(state: dict, default: str = "") -> str:
    """Current shared mood/theme (empty string if unset)."""
    return (state.get(SHARED_MOOD_KEY) or default or "").strip()


def set_shared_mood(state: dict, mood: str) -> str:
    """Set the shared mood/theme; also ensures it's in the options ring."""
    mood = (mood or "").strip()
    state[SHARED_MOOD_KEY] = mood
    if mood:
        opts = state.get(SHARED_MOOD_OPTIONS_KEY) or []
        if mood not in opts:
            opts.insert(0, mood)
        state[SHARED_MOOD_OPTIONS_KEY] = opts[:12]  # keep a small ring
    return mood


def get_mood_options(state: dict, include_pool: bool = True,
                     pool_n: int = 8) -> list[str]:
    """
    Options for a mood dropdown: whatever moods have been used/suggested so
    far (most recent first), optionally padded with fresh curated city-pop
    concepts so the list is never empty. The current shared mood is always
    first if set.
    """
    opts = list(state.get(SHARED_MOOD_OPTIONS_KEY) or [])
    current = get_shared_mood(state)
    if current and current in opts:
        opts.remove(current)
    if current:
        opts.insert(0, current)

    if include_pool:
        from services.concept_suggester import suggest_many
        for c in suggest_many(pool_n):
            if c not in opts:
                opts.append(c)

    # Dedupe preserving order.
    seen = set()
    out = []
    for o in opts:
        if o and o not in seen:
            seen.add(o)
            out.append(o)
    return out


def add_variation(state: dict) -> str:
    """
    Produce one new city-pop mood variation, register it in the options
    ring (so it shows up in the dropdown), and return it. Does NOT change
    the currently-selected shared mood — the caller decides whether to
    select it.
    """
    from services.concept_suggester import next_concept
    sug = next_concept(state, avoid=get_shared_mood(state))
    opts = state.get(SHARED_MOOD_OPTIONS_KEY) or []
    if sug not in opts:
        opts.insert(0, sug)
    state[SHARED_MOOD_OPTIONS_KEY] = opts[:12]
    return sug
