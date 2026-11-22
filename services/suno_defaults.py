"""Shared Suno generation defaults and per-album length assignment."""
from __future__ import annotations

import json
import random
from pathlib import Path

_PRESET = Path(__file__).resolve().parents[1] / "presets" / "suno" / "seoul_records_defaults.json"
SUNO_DEFAULTS = json.loads(_PRESET.read_text(encoding="utf-8"))
SUNO_VOCAL = SUNO_DEFAULTS["vocal_gender"]
DURATIONS = tuple(SUNO_DEFAULTS["duration_options_seconds"])
FALLBACK_DURATION = SUNO_DEFAULTS["fallback_duration_seconds"]


def assign_suno_durations(count: int, *, rng: random.Random | None = None) -> list[int]:
    """Use every duration once per cycle and avoid a repeat at each boundary."""
    shuffle = (rng or random).shuffle
    targets: list[int] = []
    while len(targets) < count:
        cycle = list(DURATIONS)
        shuffle(cycle)
        if targets and cycle[0] == targets[-1]:
            cycle[0], cycle[1] = cycle[1], cycle[0]
        targets.extend(cycle)
    return targets[:count]


def format_suno_duration(seconds: int) -> str:
    minute, second = divmod(seconds, 60)
    return f"{minute}:{second:02d}"


def suno_length_brief(concept: str, seconds: int) -> str:
    return (f"{concept}\n\nArrangement target: {format_suno_duration(seconds)}. "
            "Use concise sung lines and short instrumental breaks to fit this target.")


def suno_length_style(style: str, seconds: int | None) -> str:
    if not seconds or not style.strip():
        return style
    prefix = f"target length {format_suno_duration(seconds)}, concise arrangement, "
    return (prefix + style)[:1000].rstrip(" ,")


def suno_web_settings(seconds: int, vocal: str = SUNO_VOCAL) -> dict:
    return {"vocal_gender": vocal, "duration_mode": "Custom", "target_duration_seconds": seconds,
            "personalization": SUNO_DEFAULTS["personalization"], "max_mode": SUNO_DEFAULTS["max_mode"]}
