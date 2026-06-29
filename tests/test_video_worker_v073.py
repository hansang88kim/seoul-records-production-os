"""
tests/test_video_worker_v073.py — Video Render Worker + Visualizer Controls tests.

No real FFmpeg renders. Worker subprocess is mocked.
"""
from __future__ import annotations
import json
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def jobs_tmp(monkeypatch, tmp_path):
    import services.video.render_job_store as rjs
    monkeypatch.setattr(rjs, "_jobs_dir", lambda: tmp_path / "jobs")
    yield


@pytest.fixture
def render_setup(monkeypatch, tmp_path):
    try:
        from PIL import Image  # noqa
    except ImportError:
        pytest.skip("PIL not available")
    import services.video.playlist_builder as pb
    outputs = tmp_path / "outputs"
    (outputs / "p" / "songs").mkdir(parents=True)
    for n in ["a.mp3", "b.mp3"]:
        (outputs / "p" / "songs" / n).write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 4000)
    monkeypatch.setattr(pb, "_outputs_root", lambda: outputs)
    monkeypatch.setattr(pb, "_mp3_duration", lambda p: 210.0)

    from services.video.overlay_assets import build_overlay_asset_library
    from services.video.visualizer import visualizer_config
    from services.video import render_plan as rp
    from services.thumbnail import asset_types as AT

    tracks = pb.scan_mp3_files()
    plan = pb.build_playlist_plan(tracks, 60, True)
    sp = str(tmp_path / "session")
    lib = build_overlay_asset_library(sp, plan, "#ff4d6d", "구독")
    viz = visualizer_config("citypop_glow", "#ff4d6d", height=200,
                            y_position=820, width_percent=80)
    bg = {"path": str(tmp_path / "bg.png"), "asset_type": AT.VIDEO_PLAYBACK_BACKGROUND_16X9}
    plans = rp.build_render_plan(sp, plan, bg, lib, viz,
                                 enable_now_playing=True, enable_cta=True, enable_visualizer=True)
    plans["overlay_plan"]["visualizer_frame"] = {"lock_to_visualizer_position": True}
    out_dir = str(tmp_path / "render")
    concat = rp.build_mp3_concat_list(out_dir, plan)
    return {"plan": plan, "plans": plans, "concat": concat, "out_dir": out_dir,
            "bg": str(tmp_path / "bg.png"), "rp": rp, "viz": viz}


# ─── Background worker ───────────────────────────────────────────────────────

def test_full_render_uses_background_worker(render_setup, monkeypatch):
    """launch_render_job starts a detached worker and returns a job state."""
    from services.video import render_job_store as rjs
    from unittest import mock
    rp = render_setup["rp"]
    cmd = rp.build_full_render_command(
        render_setup["concat"], render_setup["bg"], render_setup["out_dir"],
        render_setup["plan"]["total_seconds"],
        render_plan=render_setup["plans"]["render_plan"],
        overlay_plan=render_setup["plans"]["overlay_plan"],
    )
    with mock.patch("subprocess.Popen", return_value=mock.Mock(pid=4321)):
        job = rjs.launch_render_job(render_setup["out_dir"], cmd["command"],
                                    render_setup["plan"]["total_seconds"], cmd["output"])
    assert job["render_job_id"]
    assert job["pid"] == 4321


def test_preview_can_run_inline(render_setup):
    """Preview command is a normal command dict — runnable inline (no worker)."""
    rp = render_setup["rp"]
    cmd = rp.build_preview_command(
        render_setup["concat"], render_setup["bg"], render_setup["out_dir"], 30,
        render_plan=render_setup["plans"]["render_plan"],
        overlay_plan=render_setup["plans"]["overlay_plan"],
    )
    assert "ffmpeg" in cmd["command"]
    assert cmd["output"].endswith("preview_30s.mp4")
    # Preview does NOT include -progress (that's for the worker/full render)
    assert "-progress" not in cmd["command"]


def test_render_state_json_created(render_setup):
    from services.video.render_job_store import create_render_job, load_render_state, _jobs_dir
    rp = render_setup["rp"]
    cmd = rp.build_full_render_command(
        render_setup["concat"], render_setup["bg"], render_setup["out_dir"],
        3600, render_plan=render_setup["plans"]["render_plan"],
        overlay_plan=render_setup["plans"]["overlay_plan"],
    )
    state = create_render_job(render_setup["out_dir"], cmd["command"], 3600, cmd["output"])
    jid = state["render_job_id"]
    # render_state.json exists
    assert (_jobs_dir() / jid / "render_state.json").exists()
    # command_sanitized.txt exists
    assert (_jobs_dir() / jid / "command_sanitized.txt").exists()
    loaded = load_render_state(jid)
    assert loaded["status"] == "queued"
    assert loaded["total_seconds"] == 3600


def test_ffmpeg_progress_jsonl_written(render_setup):
    from services.video.render_job_store import create_render_job, append_progress, _jobs_dir
    state = create_render_job(render_setup["out_dir"], ["ffmpeg"], 3600, "/out.mp4")
    jid = state["render_job_id"]
    append_progress(jid, {"out_time_ms": "5000000", "speed": "2.5x", "progress": "continue"})
    append_progress(jid, {"out_time_ms": "10000000", "speed": "2.4x", "progress": "continue"})
    p = _jobs_dir() / jid / "ffmpeg_progress.jsonl"
    assert p.exists()
    lines = p.read_text().strip().splitlines()
    assert len(lines) == 2
    rec = json.loads(lines[0])
    assert rec["speed"] == "2.5x"


def test_render_progress_panel_reads_state(render_setup):
    """Progress can be read back and reflects updates (what the panel renders)."""
    from services.video.render_job_store import (
        create_render_job, update_render_state, load_render_state,
    )
    state = create_render_job(render_setup["out_dir"], ["ffmpeg"], 3600, "/out.mp4")
    jid = state["render_job_id"]
    update_render_state(jid, status="running", progress_percent=42.0,
                        current_time_sec=1512.0, speed="2.5x", elapsed_sec=600.0)
    loaded = load_render_state(jid)
    assert loaded["status"] == "running"
    assert loaded["progress_percent"] == 42.0
    assert loaded["current_time_sec"] == 1512.0


def test_full_render_command_has_progress_option(render_setup):
    rp = render_setup["rp"]
    cmd = rp.build_full_render_command(
        render_setup["concat"], render_setup["bg"], render_setup["out_dir"],
        3600, render_plan=render_setup["plans"]["render_plan"],
        overlay_plan=render_setup["plans"]["overlay_plan"],
    )
    assert "-progress" in cmd["command"]
    idx = cmd["command"].index("-progress")
    assert cmd["command"][idx + 1] == "pipe:1"


# ─── Visualizer position controls ────────────────────────────────────────────

def test_visualizer_y_position_saved():
    from services.video.visualizer import visualizer_config
    cfg = visualizer_config("citypop_glow", "#ff4d6d", height=200, y_position=700)
    assert cfg["y_position"] == 700
    assert cfg["height"] == 200


def test_visualizer_y_position_reflected_in_filter_complex(render_setup):
    rp = render_setup["rp"]
    cmd = rp.build_full_render_command(
        render_setup["concat"], render_setup["bg"], render_setup["out_dir"],
        3600, render_plan=render_setup["plans"]["render_plan"],
        overlay_plan=render_setup["plans"]["overlay_plan"],
    )
    fc = cmd["command"][cmd["command"].index("-filter_complex") + 1]
    # y_position=820 from the fixture must appear in the visualizer overlay
    assert "y=820" in fc


def test_visualizer_height_reflected_in_filter_complex(render_setup):
    rp = render_setup["rp"]
    cmd = rp.build_full_render_command(
        render_setup["concat"], render_setup["bg"], render_setup["out_dir"],
        3600, render_plan=render_setup["plans"]["render_plan"],
        overlay_plan=render_setup["plans"]["overlay_plan"],
    )
    fc = cmd["command"][cmd["command"].index("-filter_complex") + 1]
    # height=200 and width 80% of 1920 = 1536 → showwaves=s=1536x200
    assert "x200:" in fc or "x200[" in fc


def test_visualizer_width_percent_reflected(render_setup):
    rp = render_setup["rp"]
    cmd = rp.build_full_render_command(
        render_setup["concat"], render_setup["bg"], render_setup["out_dir"],
        3600, render_plan=render_setup["plans"]["render_plan"],
        overlay_plan=render_setup["plans"]["overlay_plan"],
    )
    fc = cmd["command"][cmd["command"].index("-filter_complex") + 1]
    # 80% of 1920 = 1536
    assert "1536x" in fc


def test_visualizer_frame_locked_to_visualizer_position(render_setup):
    """When locked, the frame Y is aligned to the visualizer band (not a fixed pos)."""
    from services.video.filter_complex_builder import build_video_filter_complex
    fc = build_video_filter_complex(
        render_setup["plans"]["render_plan"], render_setup["plans"]["overlay_plan"],
    )
    graph = fc["filter_complex"]
    # visualizer at y=820, height 200; frame should be near that, NOT at the old
    # fixed CANVAS_H-220 = 860 default
    import re
    # find the vframe overlay y
    m = re.search(r"\[vframe\]overlay=x=0:y=(\d+)", graph)
    assert m is not None
    frame_y = int(m.group(1))
    # Locked frame_y should be close to the visualizer y=820 (within the frame padding)
    assert 760 <= frame_y <= 840


def test_visualizer_helper_accepts_audio_input_index():
    """The deprecated standalone helper accepts an audio_input_index param."""
    import warnings
    from services.video.visualizer import visualizer_config, build_visualizer_filter
    cfg = visualizer_config("minimal_wave")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        flt = build_visualizer_filter(cfg, 1920, audio_input_index=1)
    assert "[1:a]" in flt
    # And it can produce [0:a] if explicitly asked (back-compat), but default is 1
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        flt0 = build_visualizer_filter(cfg, 1920, audio_input_index=0)
    assert "[0:a]" in flt0


def test_visualizer_helper_is_deprecated():
    import warnings
    from services.video.visualizer import visualizer_config, build_visualizer_filter
    cfg = visualizer_config()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        build_visualizer_filter(cfg)
        assert any(issubclass(x.category, DeprecationWarning) for x in w)


# ─── Independence ────────────────────────────────────────────────────────────

def test_music_and_thumbnail_unaffected_v073():
    from providers.ai.base import MOCK_SONGS
    from services.thumbnail.asset_exporter import export_all_required_assets  # noqa
    assert len(MOCK_SONGS) >= 2
