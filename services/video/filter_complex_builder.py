"""
services/video/filter_complex_builder.py — overlay_plan → FFmpeg filter_complex (v0.7.2).

Turns the overlay_plan into a real FFmpeg -filter_complex graph and the
matching input list, so preview/full renders actually contain:
  - dynamic audio-reactive visualizer (driven by the REAL audio input index)
  - Canva visualizer frame PNG
  - per-track Now Playing PNGs (scheduled by chapter time)
  - CTA sticker PNG (scheduled every N minutes)
  - optional center title PNG + film grain

Input index convention (must match the command builder):
  input 0 = background image (looped)
  input 1 = MP3 concat audio
  input 2.. = overlay PNGs (visualizer frame, now playing cards, cta, ...)

The audio for the visualizer is therefore [1:a], NOT [0:a].
"""
from __future__ import annotations

from pathlib import Path

from services.thumbnail import asset_types as AT


# Fixed input indices
BG_INPUT = 0
AUDIO_INPUT = 1
FIRST_OVERLAY_INPUT = 2

# Canvas geometry (1920x1080)
CANVAS_W = 1920
CANVAS_H = 1080


def _hex_to_ffmpeg(color: str) -> str:
    return "0x" + (color or "#ff4d6d").lstrip("#")


def _between(start: float, end: float) -> str:
    return f"between(t,{int(start)},{int(end)})"


def build_cta_enable_expr(schedule: list[dict]) -> str:
    """
    Build an FFmpeg enable expression for the CTA sticker:
      between(t,300,310)+between(t,600,610)+...
    """
    if not schedule:
        return "0"
    return "+".join(_between(s["start_sec"], s["end_sec"]) for s in schedule)


def build_now_playing_enable_expr(start: float, end: float) -> str:
    """Enable expression for one track's Now Playing card."""
    return _between(start, end)


def collect_overlay_inputs(overlay_plan: dict) -> list[dict]:
    """
    Build the ordered overlay input list (PNGs) that must be added to the
    FFmpeg command as -i inputs, with their roles. The ORDER here defines the
    input indices used by the filter graph.

    Returns [{role, path, ...}] starting at FIRST_OVERLAY_INPUT.
    """
    inputs: list[dict] = []

    viz = overlay_plan.get("visualizer", {})
    if viz.get("enabled") and viz.get("frame_png"):
        inputs.append({"role": AT.VISUALIZER_FRAME_ASSET, "path": viz["frame_png"]})

    np = overlay_plan.get("now_playing", {})
    if np.get("enabled"):
        for item in np.get("schedule", []):
            if item.get("png"):
                inputs.append({
                    "role": AT.NOW_PLAYING_CARD_ASSET,
                    "path": item["png"],
                    "start_sec": item["start_sec"],
                    "end_sec": item["end_sec"],
                    "track_name": item.get("track_name", ""),
                })

    cta = overlay_plan.get("cta_sticker", {})
    if cta.get("enabled") and cta.get("png"):
        inputs.append({
            "role": AT.CTA_STICKER_ASSET,
            "path": cta["png"],
            "schedule": cta.get("schedule", []),
        })

    center = overlay_plan.get("center_title", {})
    if center.get("enabled") and center.get("png"):
        inputs.append({"role": AT.CENTER_TITLE_ASSET, "path": center["png"]})

    return inputs


def build_video_filter_complex(
    render_plan: dict,
    overlay_plan: dict,
    preview_seconds: int | None = None,
    preview_cta_now: bool = False,
) -> dict:
    """
    Build the full -filter_complex string + the overlay input list.

    Returns:
      {
        "filter_complex": str,
        "overlay_inputs": [{role, path, ...}],  # in input-index order
        "final_video_label": "[vout]",
        "map_audio": "1:a",
      }
    """
    overlay_inputs = collect_overlay_inputs(overlay_plan)
    parts: list[str] = []

    # Base: scale background to canvas
    parts.append(f"[{BG_INPUT}:v]scale={CANVAS_W}:{CANVAS_H},setsar=1[base]")
    current = "[base]"

    # Map overlay inputs to their ffmpeg input indices
    # index = FIRST_OVERLAY_INPUT + position in overlay_inputs
    role_index: dict[int, int] = {}
    for pos, ov in enumerate(overlay_inputs):
        role_index[pos] = FIRST_OVERLAY_INPUT + pos

    layer_order = overlay_plan.get("layer_order", [])

    # 1) Dynamic visualizer (audio-reactive) — uses AUDIO_INPUT, not background
    viz = overlay_plan.get("visualizer", {})
    if viz.get("enabled"):
        current = add_visualizer_layer(parts, current, viz)

    # 2) Visualizer frame PNG (find its input index)
    frame_idx = _find_input_index(overlay_inputs, AT.VISUALIZER_FRAME_ASSET)
    if frame_idx is not None:
        current = add_visualizer_frame_layer(parts, current, frame_idx)

    # 3) Now Playing PNGs (scheduled per chapter)
    np_items = [(i, ov) for i, ov in enumerate(overlay_inputs)
                if ov["role"] == AT.NOW_PLAYING_CARD_ASSET]
    if np_items:
        current = add_now_playing_layers(parts, current, np_items, preview_seconds)

    # 4) CTA sticker (scheduled every N minutes)
    cta_idx = _find_input_index(overlay_inputs, AT.CTA_STICKER_ASSET)
    if cta_idx is not None:
        cta = overlay_plan.get("cta_sticker", {})
        current = add_cta_sticker_layers(parts, current, cta_idx, cta,
                                         preview_seconds, preview_cta_now)

    # 5) Center title (optional)
    center_idx = _find_input_index(overlay_inputs, AT.CENTER_TITLE_ASSET)
    if center_idx is not None:
        current = add_center_title_layer(parts, current, center_idx)

    # 6) Film grain (optional, generated)
    if overlay_plan.get("film_grain", {}).get("enabled"):
        current = add_film_grain_layer(parts, current, preview_seconds)

    # Final label
    parts.append(f"{current}format=yuv420p[vout]")

    return {
        "filter_complex": ";".join(parts),
        "overlay_inputs": overlay_inputs,
        "final_video_label": "[vout]",
        "map_audio": f"{AUDIO_INPUT}:a",
    }


def _find_input_index(overlay_inputs: list[dict], role: str) -> int | None:
    """Return the ffmpeg input index for the first overlay matching `role`."""
    for pos, ov in enumerate(overlay_inputs):
        if ov["role"] == role:
            return FIRST_OVERLAY_INPUT + pos
    return None


# ─── Layer builders ──────────────────────────────────────────────────────────

def add_visualizer_layer(parts: list[str], current: str, viz: dict) -> str:
    """
    Add the dynamic audio-reactive visualizer. CRITICAL: uses [1:a] (the real
    audio input), not [0:a] (the background). Composites onto `current`.
    """
    cfg = viz.get("config", {})
    style = cfg.get("style", "citypop_glow")
    h = cfg.get("height", 160)
    opacity = cfg.get("opacity", 0.85)
    color = _hex_to_ffmpeg(cfg.get("color", "#ff4d6d"))

    # Generate the waveform/eq from the REAL audio input
    if style == "minimal_wave":
        gen = f"[{AUDIO_INPUT}:a]showwaves=s={CANVAS_W}x{h}:mode=line:rate=25:colors={color}[vizraw]"
    elif style == "soft_eq_bars":
        gen = f"[{AUDIO_INPUT}:a]showfreqs=s={CANVAS_W}x{h}:mode=bar:ascale=log:colors={color}[vizraw]"
    else:  # citypop_glow
        gen = (f"[{AUDIO_INPUT}:a]showwaves=s={CANVAS_W}x{h}:mode=cline:rate=25:colors={color},"
               f"gblur=sigma=3[vizraw]")
    parts.append(gen)

    # Apply opacity
    parts.append(f"[vizraw]format=rgba,colorchannelmixer=aa={opacity}[viz_alpha]")

    # Overlay at the bottom (position by style/cfg)
    y = CANVAS_H - h - 40  # default bottom margin
    parts.append(f"{current}[viz_alpha]overlay=x=0:y={y}[v_viz]")
    return "[v_viz]"


def add_visualizer_frame_layer(parts: list[str], current: str, input_idx: int) -> str:
    """Overlay the Canva visualizer frame PNG (bottom)."""
    parts.append(f"[{input_idx}:v]format=rgba[vframe]")
    parts.append(f"{current}[vframe]overlay=x=0:y={CANVAS_H - 220}[v_vframe]")
    return "[v_vframe]"


def add_now_playing_layers(parts: list[str], current: str,
                           np_items: list[tuple[int, dict]],
                           preview_seconds: int | None) -> str:
    """
    Overlay each track's Now Playing PNG only during its chapter time window.
    enable='between(t,start,end)' per track.
    """
    for pos, ov in np_items:
        idx = FIRST_OVERLAY_INPUT + pos
        start = ov.get("start_sec", 0)
        end = ov.get("end_sec", 0)
        # In preview, clamp the window so something shows in the short clip
        if preview_seconds is not None:
            if start >= preview_seconds:
                continue  # this track won't appear in the preview window
            end = min(end, preview_seconds)
        enable = build_now_playing_enable_expr(start, end)
        label_in = current
        label_out = f"[v_np{pos}]"
        parts.append(f"[{idx}:v]format=rgba[np{pos}]")
        parts.append(
            f"{label_in}[np{pos}]overlay=x=60:y=60:enable='{enable}'{label_out}"
        )
        current = label_out
    return current


def add_cta_sticker_layers(parts: list[str], current: str, input_idx: int,
                           cta: dict, preview_seconds: int | None,
                           preview_cta_now: bool) -> str:
    """
    Overlay the CTA sticker top-right with a schedule:
      enable='between(t,300,310)+between(t,600,610)+...'
    In preview, optionally force it on for the whole short clip.
    """
    schedule = cta.get("schedule", [])
    if preview_seconds is not None:
        if preview_cta_now:
            enable = _between(0, preview_seconds)
        else:
            # Only windows that fall within the preview
            clamped = [s for s in schedule if s["start_sec"] < preview_seconds]
            enable = build_cta_enable_expr(clamped) if clamped else "0"
    else:
        enable = build_cta_enable_expr(schedule)

    parts.append(f"[{input_idx}:v]format=rgba[cta]")
    parts.append(
        f"{current}[cta]overlay=x=W-w-60:y=40:enable='{enable}'[v_cta]"
    )
    return "[v_cta]"


def add_center_title_layer(parts: list[str], current: str, input_idx: int) -> str:
    """Overlay an optional center title PNG (centered)."""
    parts.append(f"[{input_idx}:v]format=rgba[ctitle]")
    parts.append(f"{current}[ctitle]overlay=x=(W-w)/2:y=(H-h)/2[v_ctitle]")
    return "[v_ctitle]"


def add_film_grain_layer(parts: list[str], current: str,
                         preview_seconds: int | None) -> str:
    """Add a generated film grain overlay (noise)."""
    parts.append(
        f"{current}noise=alls=12:allf=t+u[v_grain]"
    )
    return "[v_grain]"
