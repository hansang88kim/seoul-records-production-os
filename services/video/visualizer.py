"""
services/video/visualizer.py — Dynamic waveform / equalizer (v0.7.1).

Builds an audio-reactive visualizer from the actual MP3 audio. Three styles:
  - minimal_wave   : thin wave line
  - soft_eq_bars   : soft equalizer bars
  - citypop_glow   : glowing wave with bloom

Position/height/opacity/color are configurable. The visualizer is composited
inside the Canva visualizer_frame. FFmpeg's native showwaves/showspectrum is
used as the rendering primitive (fallback), but driven by real audio.
"""
from __future__ import annotations


VISUALIZER_STYLES = ["minimal_wave", "soft_eq_bars", "citypop_glow"]


def visualizer_config(
    style: str = "citypop_glow",
    color: str = "#ff4d6d",
    height: int = 160,
    opacity: float = 0.85,
    position: str = "bottom",
) -> dict:
    """Build a visualizer config (validated)."""
    if style not in VISUALIZER_STYLES:
        style = "citypop_glow"
    return {
        "style": style,
        "color": color,
        "height": int(height),
        "opacity": float(max(0.0, min(1.0, opacity))),
        "position": position,
        "audio_reactive": True,  # always driven by the real MP3 audio
    }


def build_visualizer_filter(cfg: dict, width: int = 1920) -> str:
    """
    Build the FFmpeg filter snippet for the visualizer from the real audio.
    Returns a filtergraph fragment that consumes [0:a] and produces [viz].

    These use showwaves/showcqt/showfreqs as the rendering primitive but are
    fully driven by the input MP3 audio (audio-reactive), per spec. The Canva
    visualizer_frame is overlaid on top separately.
    """
    style = cfg.get("style", "citypop_glow")
    h = cfg.get("height", 160)
    color = cfg.get("color", "#ff4d6d").lstrip("#")

    if style == "minimal_wave":
        # Thin single wave line
        return (
            f"[0:a]showwaves=s={width}x{h}:mode=line:rate=25:colors=0x{color}[viz]"
        )
    elif style == "soft_eq_bars":
        # Soft equalizer bars
        return (
            f"[0:a]showfreqs=s={width}x{h}:mode=bar:ascale=log:"
            f"colors=0x{color}[viz]"
        )
    else:  # citypop_glow
        # Glowing wave (wave + gblur bloom)
        return (
            f"[0:a]showwaves=s={width}x{h}:mode=cline:rate=25:colors=0x{color},"
            f"gblur=sigma=3[viz]"
        )


def save_visualizer_config(cfg: dict) -> dict:
    """Return the config (kept as a function for symmetry / future disk save)."""
    return dict(cfg)
