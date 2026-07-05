"""
services/video/visualizer.py — Dynamic waveform / equalizer (v1.0.0-alpha.37).

Builds an audio-reactive visualizer from the actual MP3 audio using FFmpeg's
native audio-visualization filters (showwaves / showfreqs / showspectrum /
avectorscope) — real-time filter-graph rendering, not per-frame custom
drawing, so it stays fast even for hour-long compilation videos.

Nine styles:
  - minimal_dots     : clean dot-to-dot waveform line (default)
  - minimal_wave      : thin continuous wave line
  - soft_eq_bars      : soft equalizer bars (log scale)
  - citypop_glow      : glowing wave with gaussian bloom
  - classic_bars      : crisp classic EQ bars (linear scale)
  - mirrored_bars     : EQ bars mirrored top/bottom (vstack)
  - lissajous_scope   : organic circular/blob audio pattern (stereo Lissajous
                        figure — the closest native-FFmpeg equivalent to a
                        "Circular"/"Blob" style; needs stereo audio to look
                        full, degrades to a thin line on mono sources)
  - spectrum_fire     : glowing warm-toned frequency spectrum (FFmpeg's
                        built-in "fire" colormap — "Ring of Fire" mood)
  - spectrum_terrain  : scrolling colorful frequency landscape (FFmpeg's
                        built-in "terrain" colormap)

Position/size/opacity/glow are fully configurable and are reflected in the
real filter_complex (see filter_complex_builder.add_visualizer_layer).

NOTE on audio input index: the standalone build_visualizer_filter() below is
DEPRECATED for rendering — the real renderer composites via
filter_complex_builder, which uses the correct audio input index ([1:a]).
build_visualizer_filter() now accepts audio_input_index to avoid the old
hard-coded [0:a] confusion.

NOTE on scope: fancier shader-style looks from consumer visualizer tools
(Particles, Starfield, Clouds, Lava Lamp, Jellyfish) are NOT included here —
those require per-frame custom rendering (not an FFmpeg filter-graph), which
would make hour-long render times balloon. The 9 styles above are the set
that's genuinely achievable via FFmpeg's real-time audio filters.
"""
from __future__ import annotations

import warnings


VISUALIZER_STYLES = [
    "minimal_dots", "minimal_wave", "soft_eq_bars", "citypop_glow",
    "classic_bars", "mirrored_bars", "lissajous_scope",
    "spectrum_fire", "spectrum_terrain",
]

# Styles driven by FFmpeg's own built-in colormap (showspectrum "color"
# option) rather than a single configurable hex color. The UI should disable/
# ignore the color picker for these — picking a custom color has no effect.
FIXED_PALETTE_STYLES = {"spectrum_fire", "spectrum_terrain"}

# Named color-theme presets for the configurable styles (quick-pick swatches,
# in addition to the free-form color picker already in the UI).
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
    elif style == "classic_bars":
        return f"{a}showfreqs=s={width}x{h}:mode=bar:ascale=lin:colors=0x{color}[viz]"
    elif style == "mirrored_bars":
        h2 = max(1, h // 2)
        return (f"{a}showfreqs=s={width}x{h2}:mode=bar:ascale=log:colors=0x{color}[b];"
                f"[b]split[b1][b2];[b2]vflip[b2f];[b1][b2f]vstack=inputs=2[viz]")
    elif style == "lissajous_scope":
        return (f"{a}avectorscope=s={width}x{h}:mode=lissajous:rate=25:"
                f"rc=0x{color[0:2] or '80'}:gc=0x{color[2:4] or '80'}:bc=0x{color[4:6] or '80'}[viz]")
    elif style == "spectrum_fire":
        return f"{a}showspectrum=s={width}x{h}:mode=combined:color=fire:scale=log[viz]"
    elif style == "spectrum_terrain":
        return f"{a}showspectrum=s={width}x{h}:mode=combined:color=terrain:slide=scroll[viz]"
    else:  # citypop_glow
        glow = cfg.get("glow_strength", 3.0)
        return (f"{a}showwaves=s={width}x{h}:mode=cline:rate=25:colors=0x{color},"
                f"gblur=sigma={glow}[viz]")


def save_visualizer_config(cfg: dict) -> dict:
    """Return the config (kept as a function for symmetry / future disk save)."""
    return dict(cfg)
