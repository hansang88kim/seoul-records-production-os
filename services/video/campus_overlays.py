"""ASS captions and audio-driven rounded waveform for the campus renderer."""
from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

_FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"


def _ass_time(seconds: float) -> str:
    centiseconds = round(seconds * 100)
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    seconds, fraction = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{fraction:02d}"


def _ass_color(red: int, green: int, blue: int) -> str:
    return f"&H{blue:02X}{green:02X}{red:02X}&"


def _ass_text(text: str) -> str:
    return text.replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\n", " ").replace("\r", " ")


def _position(x: int, y: int, font: str, size: int, alignment: int = 5) -> str:
    return f"{{\\an{alignment}\\pos({x},{y})\\fn{font}\\fs{size}}}"


def _highlight(x: int, y: int, width: int, height: int, settings: dict) -> str:
    red, green, blue, opacity = settings["active_fill_rgba"]
    er, eg, eb, edge_opacity = settings["active_outline_rgba"]
    return (f"{{\\an7\\pos({x},{y})\\p1\\bord1\\shad0"
            f"\\1c{_ass_color(red, green, blue)}\\1a&H{255 - opacity:02X}&"
            f"\\3c{_ass_color(er, eg, eb)}\\3a&H{255 - edge_opacity:02X}&}}"
            f"m 0 0 l {width} 0 {width} {height} 0 {height} 0 0")


def write_campus_ass(
    path: Path, plan: dict, preset: dict, captions: dict, start_frame: int, end_frame: int,
) -> None:
    video, lyric_style = preset["video"], preset["lyrics"]
    track_style, title_style = preset["track_list"], preset["track_title"]
    clip_start, clip_end = start_frame / plan["fps"], end_frame / plan["fps"]
    events = []

    def add(layer: int, start: float, end: float, text: str) -> None:
        start = max(start, clip_start) - clip_start
        end = min(end, clip_end) - clip_start
        if round(end * 100) > round(start * 100):
            events.append((layer, start, end, text))

    # Column-major order preserves the approved down-then-across layout.
    columns = track_style["column_x_px"]
    rows = max(track_style["rows_per_column"], math.ceil(len(plan["entries"]) / len(columns)))
    y0 = track_style["first_row_y_px"]
    gap = max(1, min(track_style["row_spacing_px"], (video["height"] - y0 - 5) // rows))
    title_size = min(track_style["title_size_px"], max(1, gap - 2))
    number_size = min(track_style["number_size_px"], title_size)
    measure = ImageFont.truetype(str(_FONT_DIR / "NotoSansKR.ttf"), title_size)
    canvas_end = min(video["width"] - 20, columns[-1] + min(b - a for a, b in zip(columns, columns[1:])))
    for index, entry in enumerate(plan["entries"]):
        start, end = entry["start_sec"], entry["end_sec"]
        column, row = divmod(index, rows)
        x, y = columns[column], y0 + row * gap
        right = (columns + [canvas_end])[column + 1]
        title_x = x + 30
        title_text = _ass_text(entry["title"])
        text_width = measure.getlength(title_text)
        available = right - title_x - 15
        horizontal_scale = min(100, max(1, int(100 * available / max(1, text_width))))
        number = _position(x, y, track_style["number_font"], number_size, 7)
        title = _position(title_x, y, track_style["title_font"], title_size, 7)
        add(1, 0, clip_end, number + f"{index + 1:02d}")
        add(1, 0, clip_end, title + f"{{\\fscx{horizontal_scale}}}" + title_text)
        active_start = 0 if index == 0 else start
        highlight_width = math.ceil(title_x - x + text_width * horizontal_scale / 100 + 12)
        add(0, active_start, end, _highlight(x - 5, y - 1, highlight_width, gap, track_style))

        title_card = _position(*title_style["anchor_px"], title_style["font"], title_style["size_px"])
        fade_in = 0 if index == 0 else 160
        add(2, active_start, min(end, active_start + title_style["duration_seconds"]),
            title_card + f"{{\\fad({fade_in},240)}}{index + 1:02d}. {title_text}")

        track_captions = captions.get(str(index + 1))
        if track_captions:
            _write_track_captions(add, start, end, lyric_style, track_captions)

    script = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video['width']}
PlayResY: {video['height']}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Jua,54,&H00FFFFFF,&H00FFFFFF,&H001A1A1A,&H60000000,0,0,0,0,100,100,0,0,1,1.5,0,5,15,15,15,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    with path.open("w", encoding="utf-8") as subtitles:
        subtitles.write(script)
        for layer, start, end, text in events:
            subtitles.write(f"Dialogue: {layer},{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{text}\n")


def _write_track_captions(add, audio_start: float, audio_end: float, style: dict, captions: dict) -> None:
    lead = style["appearance_lead_ms"] / 1000
    position = _position(*style["anchor_px"], style["font"], style["size_px"])
    color = _ass_color(*bytes.fromhex(style["highlight_color"].lstrip("#")))
    highlight = f"{{\\1c{color}}}"
    duration = audio_end - audio_start
    lyrics = captions["lyrics"]
    first_vocal = lyrics[0]["syllables"][0]["start_sec"] if lyrics else math.inf
    cues = []
    for line in lyrics:
        show = max(0, line["syllables"][0]["start_sec"] - lead)
        end = duration if style["hold_until_next_cue"] else line["end_sec"]
        cues.append((show, end, line["syllables"]))
    for segment in captions["instrumental"]:
        if segment["end_sec"] <= first_vocal <= style["opening_label_threshold_seconds"]:
            continue
        cues.append((segment["start_sec"], segment["end_sec"], None))
    cues.sort(key=lambda cue: cue[0])
    for index, (start, stop, syllables) in enumerate(cues):
        next_cue = cues[index + 1][0] if index + 1 < len(cues) else duration
        stop = min(stop, next_cue, duration)
        if syllables is None:
            add(3, audio_start + start, audio_start + stop,
                position + highlight + _ass_text(style["instrumental_label"]))
            continue
        times = [start, *(s["start_sec"] for s in syllables), stop]
        syllable_text = [_ass_text(s["text"]).replace(" ", r"\h") for s in syllables]
        for count, (left, right) in enumerate(zip(times, times[1:])):
            colored = "".join(syllable_text[:count])
            waiting = "".join(syllable_text[count:])
            text = position + highlight + colored + r"{\1c&HFFFFFF&}" + waiting
            add(3, audio_start + left, audio_start + min(right, stop), text)


def iter_waveform_masks(
    wav_path: Path, plan: dict, settings: dict, start_frame: int, end_frame: int,
):
    """Read overlapping Hann windows and emit one antialiased mask per video frame."""
    rate, fft_size = settings["analysis_sample_rate"], settings["fft_size"]
    count = settings["capsules"]
    _, _, width, height = settings["box_px"]
    band_edges = np.geomspace(*settings["frequency_range_hz"], count + 1)
    band_bins = np.searchsorted(np.fft.rfftfreq(fft_size, 1 / rate), band_edges)
    low, high = band_bins[:-1], np.maximum(band_bins[1:], band_bins[:-1] + 1)
    window = np.hanning(fft_size).reshape(-1, 1)
    idle = settings["idle_half_height_px"]
    peak = settings["max_half_height_px"]
    radius = settings["radius_px"] * 2
    center = height
    positions = [(index + 0.5) * width * 2 / count for index in range(count)]
    idle_heights = np.full(count, idle)
    heights = idle_heights.copy()
    spans = iter(plan["entries"])
    active = next(spans, None)

    def mask(levels) -> bytes:
        frame = Image.new("L", (width * 2, height * 2))
        draw = ImageDraw.Draw(frame)
        for x, level in zip(positions, levels):
            bounds = (x - radius, center - 2 * level, x + radius, center + 2 * level)
            draw.rounded_rectangle(bounds, radius=radius, fill=255)
        return frame.resize((width, height), Image.Resampling.LANCZOS).tobytes()

    idle_mask = mask(idle_heights)
    fade_frames = round(plan["fps"] * 0.6)
    with wave.open(str(wav_path), "rb") as audio:
        audio_frames = audio.getnframes()
        for frame in range(start_frame, end_frame):
            while active and frame >= active["end_frame"]:
                active = next(spans, None)
            if not active or frame < active["start_frame"]:
                heights[:] = idle
                if frame < fade_frames:
                    pixels = np.frombuffer(idle_mask, dtype=np.uint8)
                    yield (pixels * (frame / fade_frames)).astype(np.uint8).tobytes()
                else:
                    yield idle_mask
                continue
            fps = plan["fps"]
            clip_center = round((frame - start_frame) * rate / fps)
            left = max(0, round((active["start_frame"] - start_frame) * rate / fps),
                       clip_center - fft_size // 2)
            right = min(audio_frames, round((active["end_frame"] - start_frame) * rate / fps),
                        clip_center + fft_size // 2)
            audio.setpos(left)
            samples = np.frombuffer(audio.readframes(max(0, right - left)), dtype="<i2").reshape(-1, 2)
            segment = np.zeros((fft_size, 2), dtype=np.float32)
            offset = max(0, left - clip_center + fft_size // 2)
            segment[offset:offset + len(samples)] = samples / 32768
            spectrum = np.fft.rfft(segment * window, axis=0)
            energy = (np.abs(spectrum) ** 2).mean(axis=1)
            integral = np.concatenate(([0.0], np.cumsum(energy)))
            bands = np.sqrt((integral[high] - integral[low]) / (high - low)) / window.sum()
            levels = np.clip(np.log1p(85 * bands) / 2.3, 0, 1)
            heights = heights * 0.60 + (idle + (peak - idle) * levels) * 0.40
            yield mask(heights)
