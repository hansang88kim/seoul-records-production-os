"""Regression checks for the learned Suno, campus and distribution handoff."""
import json
import random
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from services.suno_defaults import DURATIONS, assign_suno_durations, suno_web_settings
from services.video.campus_overlays import write_campus_ass
from services.video.campus_plan import build_campus_playlist, load_campus_preset, read_captions, render_window


def test_suno_shuffles_seven_lengths_per_cycle_without_boundary_repeats():
    targets = assign_suno_durations(25, rng=random.Random(7))
    assert len(targets) == 25
    assert all(set(targets[i:i + 7]) == set(DURATIONS) for i in (0, 7, 14))
    assert all(first != second for first, second in zip(targets, targets[1:]))
    assert suno_web_settings(targets[0]) == {
        "vocal_gender": "Female", "duration_mode": "Custom", "target_duration_seconds": targets[0],
        "personalization": True, "max_mode": True,
    }


def test_suno_batch_style_respects_default_vocal_and_stores_track_length():
    from app.tabs.song_lab import _generate_plan_only

    result = _generate_plan_only("비 오는 캠퍼스", "mock", track_no=0, target_duration_seconds=170)
    assert result["status"] == "drafted"
    assert result["vocal_gender"] == "Female"
    assert "female vocal" in result["style"].lower()
    assert result["target_duration_seconds"] == 170


def test_campus_preview_transition_and_held_caps(tmp_path):
    preset = load_campus_preset()
    tracks = [{"path": str(tmp_path / f"{number}.wav"), "name": f"{number:02d} 곡.wav",
               "title": f"곡 {number}?", "duration_sec": 170} for number in range(1, 20)]
    plan = build_campus_playlist(tracks, preset)
    assert plan["entries"][0]["start_frame"] == 60
    assert plan["entries"][1]["start_frame"] - plan["entries"][0]["end_frame"] == 9
    assert plan["chapters"][0]["start_sec"] == 0
    assert plan["chapters"][1]["start_sec"] == 172.3
    assert render_window(plan, preset, "preview") == (0, 1800)
    start, end = render_window(plan, preset, "transition")
    assert start < plan["entries"][1]["start_frame"] < end

    timing = {
        "tracks": [{"track_no": 1,
                    "lyrics": [{"end_sec": 3.0, "syllables": [{"start_sec": 1.2, "text": "첫줄"}]},
                               {"end_sec": 12.0, "syllables": [{"start_sec": 11.0, "text": "다음"}]}],
                    "instrumental": [{"start_sec": 0, "end_sec": 1.1}, {"start_sec": 8, "end_sec": 11}]}]
    }
    captions = read_captions(json.dumps(timing, ensure_ascii=False).encode(), plan)
    path = tmp_path / "captions.ass"
    write_campus_ass(path, plan, preset, captions, 0, 1800)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert any(r"\pos(756,949)" in line and line.endswith("06") for line in lines)
    assert any("0:00:03.20,0:00:10.00" in line and "첫줄" in line for line in lines)
    assert len([line for line in lines if "간주중 ♪" in line]) == 1


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="needs FFmpeg and FFprobe")
def test_campus_background_job_renders_real_video_and_exact_silent_gap(tmp_path, monkeypatch):
    from services.video import render_job_store
    from workers.video_render_worker import run_render_job

    monkeypatch.setattr(render_job_store, "_jobs_dir", lambda: tmp_path / "jobs")
    audio_rate = 48000
    tracks = []
    for number, pitch in enumerate((220, 660), 1):
        path = tmp_path / f"{number:02d}.wav"
        signal = np.rint(np.sin(2 * np.pi * pitch * np.arange(audio_rate) / audio_rate) * 18000)
        with wave.open(str(path), "wb") as audio:
            audio.setparams((2, 2, audio_rate, 0, "NONE", "not compressed"))
            audio.writeframes(np.column_stack((signal, signal)).astype("<i2").tobytes())
        tracks.append({"path": str(path), "name": path.name, "title": f"곡 {number}?", "duration_sec": 1})

    preset = load_campus_preset()
    plan = build_campus_playlist(tracks, preset)
    cover = tmp_path / "background.jpg"
    Image.new("RGB", (1920, 1080), (18, 43, 36)).save(cover)
    request = {"playlist": plan, "preset": preset, "mode": "full",
               "background": str(cover), "captions": {}, "selected_candidate_id": "2"}
    output = tmp_path / "render" / "final_video.mp4"
    job = render_job_store.create_render_job(str(output.parent), [], plan["total_seconds"], str(output))
    job_id = job["render_job_id"]
    job_dir = render_job_store._job_path(job_id)
    (job_dir / "campus_request.json").write_text(json.dumps(request), encoding="utf-8")
    run_render_job(job_id)
    assert render_job_store.load_render_state(job_id)["status"] == "completed"

    result = json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(output)]))
    video, audio = result["streams"]
    assert (video["codec_name"], video["r_frame_rate"], video["pix_fmt"], video["color_space"]) == (
        "h264", "30/1", "yuv420p", "bt709")
    assert (audio["codec_name"], audio["channels"], audio["sample_rate"]) == ("aac", 2, "48000")
    assert (output.parent / "chapters.txt").read_text(encoding="utf-8").splitlines() == [
        "00:00 곡 1?", "00:03 곡 2?"]
    with wave.open(str(output.parent / "final_audio_mix.wav")) as mix:
        assert mix.getnframes() == 206400
        mix.setpos(144000)
        assert mix.readframes(14400) == bytes(14400 * 4)
