"""
tests/test_filter_complex_v072.py — overlay_plan → FFmpeg filter_complex tests.

Verifies the real preview/full commands include the visualizer + Canva PNG
overlays (Now Playing / CTA / frame), with correct audio input index and
schedules. No real FFmpeg renders.
"""
from __future__ import annotations
import pytest
from pathlib import Path


@pytest.fixture
def render_setup(monkeypatch, tmp_path):
    """Build a playlist + overlay library + plans and the concat list."""
    try:
        from PIL import Image  # noqa
    except ImportError:
        pytest.skip("PIL not available")

    import services.video.playlist_builder as pb
    outputs = tmp_path / "outputs"
    (outputs / "p" / "songs").mkdir(parents=True)
    for n in ["track_a.mp3", "track_b.mp3"]:
        (outputs / "p" / "songs" / n).write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 4000)
    monkeypatch.setattr(pb, "_outputs_root", lambda: outputs)
    monkeypatch.setattr(pb, "_mp3_duration", lambda p: 210.0)

    from services.video.overlay_assets import build_overlay_asset_library
    from services.video.visualizer import visualizer_config
    from services.video import render_plan as rp
    from services.thumbnail import asset_types as AT

    tracks = pb.scan_mp3_files()
    plan = pb.build_playlist_plan(tracks)
    sp = str(tmp_path / "session")
    lib = build_overlay_asset_library(sp, plan, "#ff4d6d", "구독")
    viz = visualizer_config("citypop_glow", "#ff4d6d")
    bg = {"path": str(tmp_path / "bg.png"), "asset_type": AT.VIDEO_PLAYBACK_BACKGROUND_16X9}
    plans = rp.build_render_plan(sp, plan, bg, lib, viz,
                                 enable_now_playing=True, enable_cta=True, enable_visualizer=True)
    out_dir = str(tmp_path / "render")
    concat = rp.build_mp3_concat_list(out_dir, plan)
    return {
        "plan": plan, "plans": plans, "concat": concat, "out_dir": out_dir,
        "bg": str(tmp_path / "bg.png"), "lib": lib, "rp": rp,
    }


def _cmd_str(cmd):
    return " ".join(cmd["command"])


# ─── Commands include filter_complex ─────────────────────────────────────────

def test_preview_command_includes_filter_complex(render_setup):
    rp = render_setup["rp"]
    cmd = rp.build_preview_command(
        render_setup["concat"], render_setup["bg"], render_setup["out_dir"], 30,
        render_plan=render_setup["plans"]["render_plan"],
        overlay_plan=render_setup["plans"]["overlay_plan"],
    )
    assert "-filter_complex" in cmd["command"]


def test_full_render_command_includes_filter_complex(render_setup):
    rp = render_setup["rp"]
    cmd = rp.build_full_render_command(
        render_setup["concat"], render_setup["bg"], render_setup["out_dir"],
        render_setup["plan"]["total_seconds"],
        render_plan=render_setup["plans"]["render_plan"],
        overlay_plan=render_setup["plans"]["overlay_plan"],
    )
    assert "-filter_complex" in cmd["command"]


# ─── Overlay inputs present ──────────────────────────────────────────────────

def test_preview_command_includes_now_playing_overlay_inputs(render_setup):
    rp = render_setup["rp"]
    cmd = rp.build_preview_command(
        render_setup["concat"], render_setup["bg"], render_setup["out_dir"], 30,
        render_plan=render_setup["plans"]["render_plan"],
        overlay_plan=render_setup["plans"]["overlay_plan"],
    )
    # Now Playing PNG path must appear as an -i input
    s = _cmd_str(cmd)
    assert "now_playing_001.png" in s


def test_preview_command_includes_cta_overlay_inputs(render_setup):
    rp = render_setup["rp"]
    cmd = rp.build_preview_command(
        render_setup["concat"], render_setup["bg"], render_setup["out_dir"], 30,
        render_plan=render_setup["plans"]["render_plan"],
        overlay_plan=render_setup["plans"]["overlay_plan"],
    )
    s = _cmd_str(cmd)
    assert "cta_sticker.png" in s


def test_preview_command_includes_visualizer_filter(render_setup):
    rp = render_setup["rp"]
    cmd = rp.build_preview_command(
        render_setup["concat"], render_setup["bg"], render_setup["out_dir"], 30,
        render_plan=render_setup["plans"]["render_plan"],
        overlay_plan=render_setup["plans"]["overlay_plan"],
    )
    fc = cmd["command"][cmd["command"].index("-filter_complex") + 1]
    assert "showwaves" in fc or "showfreqs" in fc


# ─── Visualizer uses AUDIO input, not background ─────────────────────────────

def test_visualizer_uses_audio_input_index_not_background_input(render_setup):
    rp = render_setup["rp"]
    cmd = rp.build_preview_command(
        render_setup["concat"], render_setup["bg"], render_setup["out_dir"], 30,
        render_plan=render_setup["plans"]["render_plan"],
        overlay_plan=render_setup["plans"]["overlay_plan"],
    )
    fc = cmd["command"][cmd["command"].index("-filter_complex") + 1]
    # The visualizer must read [1:a] (audio), NOT [0:a] (background)
    assert "[1:a]showwaves" in fc or "[1:a]showfreqs" in fc
    assert "[0:a]" not in fc  # background is video, never used as viz audio


# ─── CTA schedule every 5 min ────────────────────────────────────────────────

def test_cta_enable_expression_every_5_minutes():
    from services.video.filter_complex_builder import build_cta_enable_expr
    schedule = [
        {"start_sec": 300, "end_sec": 310},
        {"start_sec": 600, "end_sec": 610},
        {"start_sec": 900, "end_sec": 910},
    ]
    expr = build_cta_enable_expr(schedule)
    assert "between(t,300,310)" in expr
    assert "between(t,600,610)" in expr
    assert "between(t,900,910)" in expr
    assert "+" in expr  # multiple windows joined


def test_cta_schedule_generated_at_5min_intervals(render_setup):
    overlay_plan = render_setup["plans"]["overlay_plan"]
    schedule = overlay_plan["cta_sticker"]["schedule"]
    total = render_setup["plan"]["total_seconds"]

    # v1.0.0-alpha.121: 영상 길이는 업로드한 곡 길이의 합 — 5분마다 하나씩,
    # 총 길이를 넘지 않는 만큼만.
    assert len(schedule) == int((total - 1) // 300)
    assert schedule[0]["start_sec"] == 300
    for i, win in enumerate(schedule):
        assert win["start_sec"] == 300 * (i + 1)
        assert win["end_sec"] - win["start_sec"] == 12
        assert win["start_sec"] < total


# ─── Now Playing schedule from chapters ──────────────────────────────────────

def test_now_playing_enable_expression_from_chapters(render_setup):
    from services.video.filter_complex_builder import build_now_playing_enable_expr
    plan = render_setup["plan"]
    ch = plan["chapters"][0]
    expr = build_now_playing_enable_expr(ch["start_sec"], ch["end_sec"])
    assert f"between(t,{int(ch['start_sec'])},{int(ch['end_sec'])})" == expr


def test_now_playing_full_render_uses_chapter_windows(render_setup):
    rp = render_setup["rp"]
    cmd = rp.build_full_render_command(
        render_setup["concat"], render_setup["bg"], render_setup["out_dir"],
        render_setup["plan"]["total_seconds"],
        render_plan=render_setup["plans"]["render_plan"],
        overlay_plan=render_setup["plans"]["overlay_plan"],
    )
    fc = cmd["command"][cmd["command"].index("-filter_complex") + 1]
    # Should contain at least one now-playing enable window
    assert "between(t,0,210)" in fc  # first track 0-210s


# ─── Overlay assets are in ffmpeg inputs ─────────────────────────────────────

def test_overlay_assets_are_in_ffmpeg_inputs(render_setup):
    from services.video.filter_complex_builder import build_video_filter_complex
    fc = build_video_filter_complex(
        render_setup["plans"]["render_plan"],
        render_setup["plans"]["overlay_plan"], preview_seconds=30,
    )
    # Each overlay input has a path
    assert len(fc["overlay_inputs"]) >= 2  # frame + cta + now_playing
    for ov in fc["overlay_inputs"]:
        assert ov["path"]


def test_render_command_uses_overlay_plan_layer_order(render_setup):
    """The filter graph composes layers bottom→top per the layer order."""
    from services.video.filter_complex_builder import build_video_filter_complex
    fc = build_video_filter_complex(
        render_setup["plans"]["render_plan"],
        render_setup["plans"]["overlay_plan"], preview_seconds=30,
    )
    graph = fc["filter_complex"]
    # base comes first, vout last
    assert graph.index("[base]") < graph.index("[vout]")
    # visualizer composited before cta
    assert graph.index("v_viz") < graph.index("v_cta")


# ─── Canva uploaded asset used ───────────────────────────────────────────────

def test_canva_uploaded_cta_asset_used(tmp_path):
    """An uploaded CTA PNG must be used instead of the mock."""
    try:
        from PIL import Image  # noqa
    except ImportError:
        pytest.skip("PIL not available")
    from services.video.overlay_assets import build_overlay_asset_library_with_uploads
    from services.thumbnail import asset_types as AT

    plan = {"entries": [{"name": "a.mp3", "path": "/a.mp3", "duration_sec": 210,
                         "start_sec": 0, "end_sec": 210, "repeat_index": 0}],
            "chapters": [{"title": "a.mp3", "start_sec": 0, "end_sec": 210}]}
    sp = str(tmp_path / "session")
    # Upload a distinctive CTA PNG
    fake_cta = b"\x89PNG\r\n\x1a\n" + b"UPLOADED_CTA" + b"\x00" * 100
    lib = build_overlay_asset_library_with_uploads(
        sp, plan, "#ff4d6d", uploaded={"cta": fake_cta},
    )
    cta_path = lib[AT.CTA_STICKER_ASSET]
    assert Path(cta_path).exists()
    # The saved file is exactly the uploaded bytes (not a mock render)
    assert Path(cta_path).read_bytes() == fake_cta


def test_canva_uploaded_now_playing_used(tmp_path):
    try:
        from PIL import Image  # noqa
    except ImportError:
        pytest.skip("PIL not available")
    from services.video.overlay_assets import build_overlay_asset_library_with_uploads
    from services.thumbnail import asset_types as AT

    plan = {"entries": [
                {"name": "a.mp3", "path": "/a.mp3", "duration_sec": 210, "start_sec": 0, "end_sec": 210, "repeat_index": 0},
                {"name": "b.mp3", "path": "/b.mp3", "duration_sec": 210, "start_sec": 210, "end_sec": 420, "repeat_index": 0},
            ],
            "chapters": [
                {"title": "a.mp3", "start_sec": 0, "end_sec": 210},
                {"title": "b.mp3", "start_sec": 210, "end_sec": 420},
            ]}
    sp = str(tmp_path / "session")
    np1 = b"\x89PNG\r\n\x1a\nNP_ONE" + b"\x00" * 50
    np2 = b"\x89PNG\r\n\x1a\nNP_TWO" + b"\x00" * 50
    lib = build_overlay_asset_library_with_uploads(
        sp, plan, "#ff4d6d", uploaded={"now_playing": [np1, np2]},
    )
    cards = lib[AT.NOW_PLAYING_CARD_ASSET]
    assert len(cards) == 2
    assert Path(cards[0]["path"]).read_bytes() == np1
    assert Path(cards[1]["path"]).read_bytes() == np2


def test_preview_cta_now_forces_cta_visible(render_setup):
    """preview_cta_now=True makes the CTA enable cover the whole preview."""
    rp = render_setup["rp"]
    cmd = rp.build_preview_command(
        render_setup["concat"], render_setup["bg"], render_setup["out_dir"], 30,
        render_plan=render_setup["plans"]["render_plan"],
        overlay_plan=render_setup["plans"]["overlay_plan"],
        preview_cta_now=True,
    )
    fc = cmd["command"][cmd["command"].index("-filter_complex") + 1]
    # CTA enabled for the whole 30s preview
    assert "between(t,0,30)" in fc
