"""
services/video/visualizer.py — Dynamic equalizer (v1.0.0-alpha.40).

Builds an audio-reactive visualizer from the actual MP3 audio using FFmpeg's
native "showfreqs" filter — real-time filter-graph rendering, not per-frame
custom drawing, so it stays fast even for hour-long compilation videos.

Single style: classic_bars — crisp classic EQ bars, LOG frequency scale.

v1.0.0-alpha.40: cut down to one style (classic_bars) per user direction —
all other styles (minimal_dots/minimal_wave/soft_eq_bars/citypop_glow/
mirrored_bars/lissajous_scope/spectrum_fire/spectrum_terrain, added across
alpha.31-37) removed. Also fixed a real visual bug in classic_bars: it used
ascale=lin (linear AMPLITUDE scale) but the actual problem was the FREQUENCY
axis — showfreqs' default frequency scale is linear too, so most of a
typical song's energy (bass/low-mid) bunches into the left ~20% of the bar
and the high end sits nearly flat/invisible on the right. Real hardware/
software equalizers display frequency on a LOG scale for exactly this
reason. Added fscale=log, which spreads bass out and compresses treble into
a comparable amount of screen space — the classic evenly-populated EQ-bar
look, and the actual fix for the "all bunched left, right barely moves"
issue.

Position/size/opacity/glow are fully configurable and are reflected in the
real filter_complex (see filter_complex_builder.add_visualizer_layer).

NOTE on audio input index: the standalone build_visualizer_filter() below is
DEPRECATED for rendering — the real renderer composites via
filter_complex_builder, which uses the correct audio input index ([1:a]).
build_visualizer_filter() now accepts audio_input_index to avoid the old
hard-coded [0:a] confusion.
"""
from __future__ import annotations

import warnings


VISUALIZER_STYLES = ["classic_bars"]

# Named color-theme presets (quick-pick swatches, in addition to the
# free-form color picker already in the UI).
COLOR_THEMES: dict[str, str] = {
    "네온 퍼플": "#7c5cff",
    "선셋 오렌지": "#ff7a45",
    "시안": "#00d4ff",
    "매혹 마젠타": "#ff4d6d",
    "앰버": "#ffb347",
    "실버": "#c8ccd4",
    "슬레이트 블루": "#5b6b9e",
    "그린": "#2ecc71",
    "틸": "#2ec4b6",
    "코랄": "#ff6b6b",
    "스카이 블루": "#7fd4e8",
    "핑크": "#ff8fc4",
    "옐로우": "#ffe066",
}

# Canvas geometry
CANVAS_W = 1920
CANVAS_H = 1080


def visualizer_config(
    style: str = "classic_bars",
    color: str = "#ff4d6d",
    height: int = 160,
    opacity: float = 0.85,
    position: str = "bottom",
    y_position: int | None = None,
    bottom_margin: int = 40,
    width_percent: int = 100,
    glow_strength: float = 3.0,
) -> dict:
    """
    Build a visualizer config (validated) with full position/size controls.

    y_position: explicit top-Y of the visualizer band. If None, computed from
                bottom_margin (CANVAS_H - height - bottom_margin).
    bottom_margin: gap from the bottom edge (used when y_position is None).
    width_percent: visualizer width as a % of canvas width (10-100).
    height: visualizer band height in px.
    opacity: 0..1.
    glow_strength: unused by classic_bars; kept for config-shape stability.
    """
    if style not in VISUALIZER_STYLES:
        style = "classic_bars"

    height = int(height)
    width_percent = int(max(10, min(100, width_percent)))

    if y_position is None:
        y_position = CANVAS_H - height - int(bottom_margin)

    return {
        "style": style,
        "color": color,
        "height": height,
        "opacity": float(max(0.0, min(1.0, opacity))),
        "position": position,
        "y_position": int(y_position),
        "bottom_margin": int(bottom_margin),
        "width_percent": width_percent,
        "glow_strength": float(glow_strength),
        "audio_reactive": True,  # always driven by the real MP3 audio
    }


def visualizer_width_px(cfg: dict) -> int:
    """Compute the visualizer width in pixels from width_percent."""
    pct = cfg.get("width_percent", 100)
    return int(CANVAS_W * pct / 100)


def visualizer_x_offset(cfg: dict) -> int:
    """Center the visualizer horizontally when width < canvas."""
    return (CANVAS_W - visualizer_width_px(cfg)) // 2


def build_visualizer_filter(cfg: dict, width: int = 1920,
                            audio_input_index: int = 1) -> str:
    """
    DEPRECATED for rendering — use filter_complex_builder.add_visualizer_layer.

    Build a standalone FFmpeg filter snippet for the visualizer from the real
    audio. `audio_input_index` selects which input's audio to read (default 1,
    matching the renderer's 0=bg / 1=audio convention). Produces [viz].
    """
    warnings.warn(
        "build_visualizer_filter is deprecated; the renderer uses "
        "filter_complex_builder.add_visualizer_layer (correct audio input).",
        DeprecationWarning, stacklevel=2,
    )
    h = cfg.get("height", 160)
    color = cfg.get("color", "#ff4d6d").lstrip("#")
    a = f"[{audio_input_index}:a]"
    # fscale=log balances bass-vs-treble screen space (see module docstring).
    return f"{a}showfreqs=s={width}x{h}:mode=bar:ascale=lin:fscale=log:colors=0x{color}[viz]"


def save_visualizer_config(cfg: dict) -> dict:
    """Return the config (kept as a function for symmetry / future disk save)."""
    return dict(cfg)
