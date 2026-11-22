"""Render campus previews and full videos with the same timing and overlays."""
from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from services.video.campus_overlays import iter_waveform_masks, write_campus_ass
from services.video.campus_plan import render_window
from services.video.playlist_builder import format_chapters_txt
from services.video.render_plan import _ffmpeg

AUDIO_RATE = 48000
AUDIO_FRAME_BYTES = 4


class RenderCancelled(Exception):
    pass


def _check_cancel(cancelled) -> None:
    if cancelled():
        raise RenderCancelled()


def _run_ffmpeg(args: list[str]) -> bytes:
    result = subprocess.run([_ffmpeg(), "-hide_banner", "-loglevel", "error", *args],
                            capture_output=True, timeout=120)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def _mix_audio(
    path: Path, plan: dict, transition: dict, start_frame: int, end_frame: int, cancelled,
) -> None:
    samples_per_frame = AUDIO_RATE // plan["fps"]
    clip_start, clip_end = start_frame * samples_per_frame, end_frame * samples_per_frame
    cursor = clip_start
    entries = plan["entries"]
    with wave.open(str(path), "wb") as audio:
        audio.setparams((2, 2, AUDIO_RATE, 0, "NONE", "not compressed"))
        for index, track in enumerate(entries):
            _check_cancel(cancelled)
            first = track["start_frame"] * samples_per_frame
            last = track["end_frame"] * samples_per_frame
            left, right = max(first, clip_start), min(last, clip_end)
            if right <= left:
                continue
            offset, count = left - first, right - left
            if left > cursor:
                audio.writeframesraw(bytes((left - cursor) * AUDIO_FRAME_BYTES))
            data = _run_ffmpeg([
                "-xerror", "-ss", f"{offset / AUDIO_RATE:.8f}", "-i", track["path"],
                "-t", f"{count / AUDIO_RATE:.8f}", "-vn", "-ar", str(AUDIO_RATE),
                "-ac", "2", "-f", "s16le", "pipe:1",
            ])
            if not data:
                raise ValueError(f"음원을 디코딩할 수 없습니다. {track['name']}")
            size = count * AUDIO_FRAME_BYTES
            samples = np.frombuffer(data[:size].ljust(size, b"\0"), dtype="<i2").reshape(-1, 2)
            positions = np.arange(offset, offset + count)
            fade_in = min(last - first, transition["fade_in_ms"] * AUDIO_RATE // 1000) if index else 0
            fade_out = (min(last - first - fade_in, transition["fade_out_ms"] * AUDIO_RATE // 1000)
                        if index < len(entries) - 1 else 0)
            if fade_in or fade_out:
                gain = np.ones(count)
                if fade_in:
                    gain *= np.minimum(1, positions / fade_in)
                if fade_out:
                    gain *= np.minimum(1, (last - first - 1 - positions) / fade_out)
                samples = np.rint(samples * gain[:, None]).astype("<i2")
            audio.writeframesraw(samples.tobytes())
            cursor = right
        if cursor < clip_end:
            audio.writeframesraw(bytes((clip_end - cursor) * AUDIO_FRAME_BYTES))


def _encode(
    folder: Path, background: Path, logo: str, plan: dict, preset: dict,
    start: int, end: int, cancelled, progress,
) -> Path:
    fps = plan["fps"]
    width, height = preset["video"]["width"], preset["video"]["height"]
    waveform = preset["waveform"]
    x, y, mask_width, mask_height = waveform["box_px"]
    color = waveform["color"].lstrip("#")
    fonts = Path(__file__).resolve().parents[2] / "assets" / "fonts"
    (folder / "fonts").mkdir()
    for name in ("NotoSansKR.ttf", "Jua-Regular.ttf", "SpaceMono-Regular.ttf"):
        path = fonts / name
        if path.is_file():
            (folder / "fonts" / name).write_bytes(path.read_bytes())

    graph = [
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1[background]",
        f"color=c=0x{color}:s={mask_width}x{mask_height}:r={fps},format=rgb24[white]",
        "[1:v]format=gray[mask]",
        "[white][mask]alphamerge[wave]",
        f"[background][wave]overlay={x}:{y}:shortest=1[scene]",
    ]
    logo_input = []
    scene = "scene"
    if logo:
        logo_input = ["-loop", "1", "-framerate", str(fps), "-i", str(Path(logo).resolve())]
        fade = ",fade=t=in:d=0.6:alpha=1" if start == 0 else ""
        graph.extend([
            f"[3:v]scale=200:-1,format=rgba{fade}[logo]",
            "[scene][logo]overlay=W-w-48:H-h-32[branded]",
        ])
        scene = "branded"
    graph.append(f"[{scene}]ass=captions.ass:fontsdir=fonts,"
                 "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p[v]")
    output = folder / "render.mp4"
    command = [
        _ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-nostdin",
        "-loop", "1", "-framerate", str(fps), "-i", str(background),
        "-f", "rawvideo", "-pix_fmt", "gray", "-s:v", f"{mask_width}x{mask_height}",
        "-r", str(fps), "-i", "pipe:0", "-i", "audio.wav", *logo_input,
        "-filter_complex_threads", "2", "-filter_complex", ";".join(graph),
        "-map", "[v]", "-map", "2:a", "-t", f"{(end - start) / fps:.8f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-threads", "4",
        "-pix_fmt", "yuv420p", "-color_range", "tv",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-c:a", "aac", "-ar", str(AUDIO_RATE), "-ac", "2", "-b:a", "320k",
        "-movflags", "+faststart", output.name,
    ]
    with (folder / "ffmpeg_errors.log").open("w+b") as errors:
        encoder = subprocess.Popen(command, cwd=folder, stdin=subprocess.PIPE,
                                   stdout=subprocess.DEVNULL, stderr=errors)
        try:
            frames = iter_waveform_masks(folder / "waveform.wav", plan, waveform, start, end)
            for count, pixels in enumerate(frames):
                if count % 6 == 0:
                    _check_cancel(cancelled)
                encoder.stdin.write(pixels)
                if count % fps == 0:
                    progress(count / fps, "영상 인코딩 중")
            encoder.stdin.close()
            while encoder.poll() is None:
                _check_cancel(cancelled)
                try:
                    encoder.wait(timeout=0.25)
                except subprocess.TimeoutExpired:
                    continue
        except BrokenPipeError:
            encoder.wait(timeout=5)
        finally:
            if encoder.poll() is None:
                encoder.kill()
                encoder.wait()
            if not encoder.stdin.closed:
                encoder.stdin.close()
        if encoder.returncode or not output.is_file():
            errors.seek(0)
            raise RuntimeError(errors.read().decode("utf-8", errors="replace").strip()
                               or "FFmpeg가 영상 파일을 만들지 못했습니다.")
    return output


def render_campus(request: dict, output_path: str, *, cancelled, progress) -> None:
    """Produce complete outputs before exposing them to the Studio or its scanners."""
    plan, preset, mode = request["playlist"], request["preset"], request["mode"]
    start, end = render_window(plan, preset, mode)
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    background = Path(request["background"]).resolve()
    if not background.is_file():
        raise ValueError("선택한 영상 배경을 찾을 수 없습니다.")
    with TemporaryDirectory(prefix=".campus-render-", dir=output.parent) as temp:
        folder = Path(temp)
        audio = folder / "audio.wav"
        progress(0, "곡 순서와 전환 기준으로 오디오 준비 중")
        _mix_audio(audio, plan, preset["transition"], start, end, cancelled)
        _check_cancel(cancelled)
        _run_ffmpeg(["-i", str(audio), "-ar", str(preset["waveform"]["analysis_sample_rate"]),
                     "-ac", "2", "-c:a", "pcm_s16le", str(folder / "waveform.wav")])
        write_campus_ass(folder / "captions.ass", plan, preset, request["captions"], start, end)
        rendered = _encode(folder, background, request.get("logo", ""), plan, preset,
                           start, end, cancelled, progress)
        _check_cancel(cancelled)
        if mode == "full":
            (folder / "playlist_plan.json").write_text(
                json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
            (folder / "render_plan.json").write_text(
                json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8")
            (folder / "chapters.txt").write_text(format_chapters_txt(plan), encoding="utf-8")
            for name in ("playlist_plan.json", "render_plan.json", "chapters.txt"):
                (folder / name).replace(output.parent / name)
            audio.replace(output.parent / "final_audio_mix.wav")
        rendered.replace(output)
