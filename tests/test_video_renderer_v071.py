"""
tests/test_video_renderer_v071.py — MP3-first Video Renderer + Canva Overlay tests.

No real long FFmpeg renders. No fake WAV. Mock/stub only.
"""
from __future__ import annotations
import json
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def studio_tmp(monkeypatch, tmp_path):
    import services.thumbnail.session_store as ss
    monkeypatch.setattr(ss, "_studio_root", lambda: tmp_path / "thumb")
    yield


@pytest.fixture
def mp3_outputs(monkeypatch, tmp_path):
    """Create fake MP3 files under outputs/ and point the scanner at them."""
    import services.video.playlist_builder as pb
    outputs = tmp_path / "outputs"
    (outputs / "song_projects" / "proj1" / "songs").mkdir(parents=True)
    (outputs / "jobs" / "job1").mkdir(parents=True)
    mp3a = outputs / "song_projects" / "proj1" / "songs" / "밤이_지나면.mp3"
    mp3b = outputs / "song_projects" / "proj1" / "songs" / "늦은_대답.mp3"
    mp3c = outputs / "jobs" / "job1" / "selected_preview.mp3"
    for m in (mp3a, mp3b, mp3c):
        m.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 4000)  # minimal mp3-ish
    monkeypatch.setattr(pb, "_outputs_root", lambda: outputs)
    # Force a deterministic duration
    monkeypatch.setattr(pb, "_mp3_duration", lambda p: 210.0)  # 3:30 each
    return outputs, [str(mp3a), str(mp3b), str(mp3c)]


# ─── MP3-first input ─────────────────────────────────────────────────────────

def test_video_renderer_accepts_mp3_without_wav(mp3_outputs):
    """The renderer works from MP3 alone — no WAV required."""
    from services.video.playlist_builder import scan_mp3_files, build_playlist_plan
    tracks = scan_mp3_files()
    assert len(tracks) >= 2
    # None of them are WAV
    assert all(t["path"].endswith(".mp3") for t in tracks)
    plan = build_playlist_plan(tracks, target_minutes=60, repeat_until_target=True)
    assert plan["entries"]


def test_video_renderer_scans_mp3_files(mp3_outputs):
    from services.video.playlist_builder import scan_mp3_files
    tracks = scan_mp3_files()
    names = {t["name"] for t in tracks}
    assert "밤이_지나면.mp3" in names
    assert "selected_preview.mp3" in names
    # selected_preview is tagged
    sp = next(t for t in tracks if t["name"] == "selected_preview.mp3")
    assert sp["source"] == "selected_preview"


# ─── Background selection (prefers clean playback) ───────────────────────────

def test_video_renderer_prefers_clean_playback_background(tmp_path):
    from services.thumbnail import session_store as ss, asset_exporter as ae
    from services.thumbnail.video_renderer_rules import select_video_background
    from services.thumbnail import asset_types as AT
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL not available")
    sess = ss.create_session("korea", "n", "T", 1)
    bg = tmp_path / "bg.png"
    Image.new("RGB", (1600, 900), (40, 50, 80)).save(bg)
    ae.export_all_required_assets(sess["session_id"], str(bg), "T", "S", "Seoul Records", "#f00")
    sel = select_video_background(sess["session_id"])
    assert sel["asset_type"] == AT.VIDEO_PLAYBACK_BACKGROUND_16X9
    assert sel["is_clean_playback"] is True


def test_video_renderer_warns_when_using_youtube_thumbnail(tmp_path):
    from services.thumbnail import session_store as ss, asset_exporter as ae
    from services.thumbnail.video_renderer_rules import select_video_background
    from services.thumbnail import asset_types as AT
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL not available")
    sess = ss.create_session("korea", "n", "T", 1)
    bg = tmp_path / "bg.png"
    Image.new("RGB", (1600, 900), (40, 50, 80)).save(bg)
    # Only the thumbnail exists
    yt = ae.export_youtube_thumbnail(sess["session_id"], str(bg), "T", "S", "Seoul Records", "#f00")
    ae.write_asset_manifest(sess["session_id"],
                            [ae._make_asset_entry(sess["session_id"], AT.YOUTUBE_THUMBNAIL_16X9, yt)])
    sel = select_video_background(sess["session_id"])
    assert sel["asset_type"] == AT.YOUTUBE_THUMBNAIL_16X9
    assert sel["warning"] is not None
    assert "썸네일" in sel["warning"] or "thumbnail" in sel["warning"].lower()


# ─── Playlist target duration ────────────────────────────────────────────────

def test_playlist_builder_target_duration_60min(mp3_outputs):
    from services.video.playlist_builder import scan_mp3_files, build_playlist_plan
    tracks = scan_mp3_files()
    plan = build_playlist_plan(tracks, target_minutes=60, repeat_until_target=True)
    # Total should reach at least 60 minutes (3600s) via repeat
    assert plan["total_seconds"] >= 3600
    assert plan["target_seconds"] == 3600
    assert plan["repeat"] is True
    # Chapters exist
    assert len(plan["chapters"]) >= 1


def test_playlist_target_65_and_70(mp3_outputs):
    from services.video.playlist_builder import scan_mp3_files, build_playlist_plan
    tracks = scan_mp3_files()
    for minutes in (65, 70):
        plan = build_playlist_plan(tracks, target_minutes=minutes, repeat_until_target=True)
        assert plan["total_seconds"] >= minutes * 60
        assert plan["target_seconds"] == minutes * 60


# ─── Preview render ──────────────────────────────────────────────────────────

def test_preview_render_command_created(mp3_outputs, tmp_path):
    from services.video.playlist_builder import scan_mp3_files, build_playlist_plan
    from services.video.render_plan import build_mp3_concat_list, build_preview_command
    tracks = scan_mp3_files()
    plan = build_playlist_plan(tracks, 60, True)
    out_dir = str(tmp_path / "render")
    concat = build_mp3_concat_list(out_dir, plan)
    cmd = build_preview_command(concat, "/bg.png", out_dir, seconds=30)
    assert any("ffmpeg" in c for c in cmd["command"])  # full path OK
    assert "-t" in cmd["command"]
    assert "30" in cmd["command"]
    assert cmd["output"].endswith("preview_30s.mp4")
    # Concat list references MP3 (no WAV)
    assert Path(concat).exists()
    content = Path(concat).read_text(encoding="utf-8")
    assert ".mp3" in content
    assert ".wav" not in content


# ─── Canva overlay asset library ─────────────────────────────────────────────

def test_canva_asset_library_exists(mp3_outputs, tmp_path):
    from services.video.playlist_builder import scan_mp3_files, build_playlist_plan
    from services.video.overlay_assets import build_overlay_asset_library
    from services.thumbnail import asset_types as AT
    try:
        from PIL import Image  # noqa
    except ImportError:
        pytest.skip("PIL not available")
    tracks = scan_mp3_files()
    plan = build_playlist_plan(tracks, 60, True)
    sp = str(tmp_path / "session")
    lib = build_overlay_asset_library(sp, plan, "#ff4d6d", "구독+좋아요")
    assert AT.NOW_PLAYING_CARD_ASSET in lib
    assert AT.CTA_STICKER_ASSET in lib
    assert AT.VISUALIZER_FRAME_ASSET in lib


def test_now_playing_uses_png_overlay(mp3_outputs, tmp_path):
    from services.video.overlay_assets import make_now_playing_card
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL not available")
    sp = str(tmp_path / "session")
    path = make_now_playing_card(sp, 1, "밤이 지나면", "#ff4d6d")
    assert path is not None
    assert path.endswith(".png")
    assert Path(path).exists()


def test_cta_uses_png_overlay(tmp_path):
    from services.video.overlay_assets import make_cta_sticker
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL not available")
    sp = str(tmp_path / "session")
    path = make_cta_sticker(sp, "구독 + 좋아요", "#ff4d6d")
    assert path is not None
    assert path.endswith(".png")
    assert Path(path).exists()


def test_visualizer_frame_uses_canva_png(tmp_path):
    from services.video.overlay_assets import make_visualizer_frame
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL not available")
    sp = str(tmp_path / "session")
    path = make_visualizer_frame(sp, "#ff4d6d")
    assert path is not None
    assert path.endswith(".png")
    assert Path(path).exists()


# ─── Dynamic visualizer from audio ───────────────────────────────────────────

def test_dynamic_visualizer_generated_from_audio():
    import warnings
    from services.video.visualizer import visualizer_config, build_visualizer_filter
    cfg = visualizer_config("citypop_glow", "#ff4d6d", 160, 0.85, "bottom")
    assert cfg["audio_reactive"] is True
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        flt = build_visualizer_filter(cfg, 1920)  # default audio input = 1 ([1:a])
    # Uses the real audio input — default is now [1:a] (renderer convention)
    assert "[1:a]" in flt
    assert "showwaves" in flt or "showfreqs" in flt


def test_visualizer_styles_all_valid():
    import warnings
    from services.video.visualizer import VISUALIZER_STYLES, build_visualizer_filter, visualizer_config
    for style in VISUALIZER_STYLES:
        cfg = visualizer_config(style)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            flt = build_visualizer_filter(cfg)
        assert "[1:a]" in flt  # default audio input index
        assert "[viz]" in flt


# ─── Overlay plan layer order ────────────────────────────────────────────────

def test_overlay_plan_layer_order(mp3_outputs, tmp_path):
    from services.video.playlist_builder import scan_mp3_files, build_playlist_plan
    from services.video.overlay_assets import build_overlay_asset_library
    from services.video.visualizer import visualizer_config
    from services.video.render_plan import build_render_plan
    from services.thumbnail import asset_types as AT
    try:
        from PIL import Image  # noqa
    except ImportError:
        pytest.skip("PIL not available")
    tracks = scan_mp3_files()
    plan = build_playlist_plan(tracks, 60, True)
    sp = str(tmp_path / "session")
    lib = build_overlay_asset_library(sp, plan, "#f00", "구독")
    viz = visualizer_config()
    plans = build_render_plan(
        sp, plan, {"path": "/bg.png", "asset_type": AT.VIDEO_PLAYBACK_BACKGROUND_16X9},
        lib, viz, enable_now_playing=True, enable_cta=True, enable_visualizer=True,
    )
    layers = plans["overlay_plan"]["layer_order"]
    # Background must be first (bottom)
    assert layers[0] == "background"
    # Visualizer before now_playing before cta
    assert layers.index(AT.DYNAMIC_VISUALIZER_OVERLAY) < layers.index(AT.NOW_PLAYING_CARD_ASSET)
    assert layers.index(AT.NOW_PLAYING_CARD_ASSET) < layers.index(AT.CTA_STICKER_ASSET)


def test_overlay_plan_uses_png_not_drawtext(mp3_outputs, tmp_path):
    """Now Playing and CTA must be flagged as PNG overlays, not drawtext."""
    from services.video.playlist_builder import scan_mp3_files, build_playlist_plan
    from services.video.overlay_assets import build_overlay_asset_library
    from services.video.visualizer import visualizer_config
    from services.video.render_plan import build_render_plan
    from services.thumbnail import asset_types as AT
    try:
        from PIL import Image  # noqa
    except ImportError:
        pytest.skip("PIL not available")
    tracks = scan_mp3_files()
    plan = build_playlist_plan(tracks, 60, True)
    sp = str(tmp_path / "session")
    lib = build_overlay_asset_library(sp, plan, "#f00", "구독")
    plans = build_render_plan(sp, plan, {"path": "/bg.png"}, lib, visualizer_config())
    assert plans["overlay_plan"]["now_playing"]["uses_png"] is True
    assert plans["overlay_plan"]["cta_sticker"]["uses_png"] is True


# ─── No fake WAV ─────────────────────────────────────────────────────────────

def test_no_fake_wav_created(mp3_outputs, tmp_path):
    """Audio path is MP3; no WAV is created by default and no fake WAV ever."""
    from services.video.playlist_builder import scan_mp3_files, build_playlist_plan
    from services.video.render_plan import (
        build_mp3_concat_list, build_audio_mix_command, build_render_plan
    )
    from services.video.overlay_assets import build_overlay_asset_library
    from services.video.visualizer import visualizer_config
    try:
        from PIL import Image  # noqa
    except ImportError:
        pytest.skip("PIL not available")
    tracks = scan_mp3_files()
    plan = build_playlist_plan(tracks, 60, True)
    out_dir = str(tmp_path / "render")
    concat = build_mp3_concat_list(out_dir, plan)
    # Default: no audio mix file at all
    mix = build_audio_mix_command(concat, out_dir, make_mp3_mix=False)
    assert mix["output"] is None
    # Optional mix is MP3, never WAV
    mix2 = build_audio_mix_command(concat, out_dir, make_mp3_mix=True)
    assert mix2["output"].endswith(".mp3")
    assert not mix2["output"].endswith(".wav")
    # render plan flags
    sp = str(tmp_path / "session")
    lib = build_overlay_asset_library(sp, plan, "#f00", "구독")
    plans = build_render_plan(sp, plan, {"path": "/bg.png"}, lib, visualizer_config())
    assert plans["render_plan"]["audio_source"] == "mp3"
    assert plans["render_plan"]["no_fake_wav"] is True
    # No .wav anywhere in the concat list
    assert ".wav" not in Path(concat).read_text(encoding="utf-8")


def test_center_title_off_by_default(mp3_outputs, tmp_path):
    from services.video.playlist_builder import scan_mp3_files, build_playlist_plan
    from services.video.overlay_assets import build_overlay_asset_library
    from services.video.visualizer import visualizer_config
    from services.video.render_plan import build_render_plan
    try:
        from PIL import Image  # noqa
    except ImportError:
        pytest.skip("PIL not available")
    tracks = scan_mp3_files()
    plan = build_playlist_plan(tracks, 60, True)
    sp = str(tmp_path / "session")
    lib = build_overlay_asset_library(sp, plan, "#f00", "구독")
    plans = build_render_plan(sp, plan, {"path": "/bg.png"}, lib, visualizer_config())
    assert plans["overlay_plan"]["center_title"]["enabled"] is False


# ─── Output files plan ───────────────────────────────────────────────────────

def test_render_outputs_saved(mp3_outputs, tmp_path):
    from services.video.playlist_builder import scan_mp3_files, build_playlist_plan
    from services.video.overlay_assets import build_overlay_asset_library
    from services.video.visualizer import visualizer_config
    from services.video.render_plan import build_render_plan, save_plans
    try:
        from PIL import Image  # noqa
    except ImportError:
        pytest.skip("PIL not available")
    tracks = scan_mp3_files()
    plan = build_playlist_plan(tracks, 60, True)
    out_dir = str(tmp_path / "render")
    sp = str(tmp_path / "session")
    lib = build_overlay_asset_library(sp, plan, "#f00", "구독")
    plans = build_render_plan(sp, plan, {"path": "/bg.png"}, lib, visualizer_config())
    paths = save_plans(out_dir, plans, plan)
    for key in ["render_plan", "overlay_plan", "playlist_plan", "chapters"]:
        assert Path(paths[key]).exists()


# ─── Independence ────────────────────────────────────────────────────────────

def test_music_and_thumbnail_unaffected_v071():
    from providers.ai.base import MOCK_SONGS
    from services.thumbnail.prompt_generator import generate_flow_prompt
    assert len(MOCK_SONGS) >= 2
    assert generate_flow_prompt("korea", "n", 0)["main_prompt"]
