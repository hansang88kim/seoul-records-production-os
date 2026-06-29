"""
services/video/visualizer.py — Dynamic waveform / equalizer (v0.7.3).

Builds an audio-reactive visualizer from the actual MP3 audio. Three styles:
  - minimal_wave   : thin wave line
  - soft_eq_bars   : soft equalizer bars
  - citypop_glow   : glowing wave with bloom

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


VISUALIZER_STYLES = ["minimal_wave", "soft_eq_bars", "citypop_glow"]

# Canvas geometry
CANVAS_W = 1920
CANVAS_H = 1080


def visualizer_config(
    style: str = "citypop_glow",
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
    glow_strength: gaussian blur sigma for the glow style.
    """
    if style not in VISUALIZER_STYLES:
        style = "citypop_glow"

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
    style = cfg.get("style", "citypop_glow")
    h = cfg.get("height", 160)
    color = cfg.get("color", "#ff4d6d").lstrip("#")
    a = f"[{audio_input_index}:a]"

    if style == "minimal_wave":
        return f"{a}showwaves=s={width}x{h}:mode=line:rate=25:colors=0x{color}[viz]"
    elif style == "soft_eq_bars":
        return f"{a}showfreqs=s={width}x{h}:mode=bar:ascale=log:colors=0x{color}[viz]"
    else:  # citypop_glow
        glow = cfg.get("glow_strength", 3.0)
        return (f"{a}showwaves=s={width}x{h}:mode=cline:rate=25:colors=0x{color},"
                f"gblur=sigma={glow}[viz]")


def save_visualizer_config(cfg: dict) -> dict:
    """Return the config (kept as a function for symmetry / future disk save)."""
    return dict(cfg)
