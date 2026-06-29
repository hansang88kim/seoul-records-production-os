"""
tests/test_asset_separation.py — v0.7.0 Output Asset Separation tests.

Verifies the 3 deliverables stay separated:
  YouTube Thumbnail (광고판) / Video Background (무대) / Streaming Cover (앨범 자켓)

No real Canva API calls. No long FFmpeg renders.
"""
from __future__ import annotations
import os
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def studio_tmp(monkeypatch, tmp_path):
    import services.thumbnail.session_store as ss
    monkeypatch.setattr(ss, "_studio_root", lambda: tmp_path)
    yield


@pytest.fixture
def session_with_bg(tmp_path):
    """Create a session + a fake background image."""
    from services.thumbnail import session_store as ss
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("PIL not available")
    sess = ss.create_session("korea", "night", "Korea CityPop Vol.3", 3, "Rainy Neon")
    bg = tmp_path / "bg.png"
    Image.new("RGB", (1600, 900), (40, 50, 80)).save(bg)
    return sess["session_id"], str(bg)


# ─── Asset types exist ───────────────────────────────────────────────────────

def test_youtube_thumbnail_asset_type_exists():
    from services.thumbnail import asset_types as AT
    assert AT.YOUTUBE_THUMBNAIL_16X9 == "youtube_thumbnail_16x9"
    assert AT.YOUTUBE_THUMBNAIL_16X9 in AT.ASSET_TYPES


def test_video_playback_background_asset_type_exists():
    from services.thumbnail import asset_types as AT
    assert AT.VIDEO_PLAYBACK_BACKGROUND_16X9 == "video_playback_background_16x9"
    assert AT.VIDEO_PLAYBACK_BACKGROUND_16X9 in AT.ASSET_TYPES


def test_streaming_cover_1x1_asset_type_exists():
    from services.thumbnail import asset_types as AT
    assert AT.STREAMING_COVER_1X1 == "streaming_cover_1x1"
    assert AT.STREAMING_COVER_1X1 in AT.ASSET_TYPES


# ─── YouTube thumbnail content flags ─────────────────────────────────────────

def test_youtube_thumbnail_contains_playlist_title_flag():
    from services.thumbnail import asset_types as AT
    flags = AT.default_content_flags(AT.YOUTUBE_THUMBNAIL_16X9)
    assert flags["contains_playlist_title"] is True


def test_youtube_thumbnail_does_not_contain_waveform_flag():
    from services.thumbnail import asset_types as AT
    flags = AT.default_content_flags(AT.YOUTUBE_THUMBNAIL_16X9)
    assert flags["contains_waveform"] is False


def test_youtube_thumbnail_does_not_contain_cta_flag():
    from services.thumbnail import asset_types as AT
    flags = AT.default_content_flags(AT.YOUTUBE_THUMBNAIL_16X9)
    assert flags["contains_cta_sticker"] is False
    assert flags["contains_song_title"] is False


# ─── Video background flags ──────────────────────────────────────────────────

def test_video_background_does_not_contain_center_playlist_title_by_default():
    from services.thumbnail import asset_types as AT
    flags = AT.default_content_flags(AT.VIDEO_PLAYBACK_BACKGROUND_16X9)
    assert flags["contains_playlist_title"] is False
    assert flags["contains_waveform"] is False
    assert flags["contains_cta_sticker"] is False


# ─── Video renderer background selection ─────────────────────────────────────

def test_video_renderer_prefers_video_playback_background(session_with_bg):
    from services.thumbnail import asset_exporter as ae
    from services.thumbnail.video_renderer_rules import select_video_background
    from services.thumbnail import asset_types as AT
    sid, bg = session_with_bg
    ae.export_all_required_assets(sid, bg, "T", "S", "Seoul Records", "#ff0000")
    sel = select_video_background(sid)
    assert sel["asset_type"] == AT.VIDEO_PLAYBACK_BACKGROUND_16X9
    assert sel["is_clean_playback"] is True
    assert sel["warning"] is None


def test_video_renderer_warns_when_using_youtube_thumbnail_as_background(session_with_bg):
    from services.thumbnail import asset_exporter as ae
    from services.thumbnail.video_renderer_rules import select_video_background
    from services.thumbnail import asset_types as AT
    sid, bg = session_with_bg
    # Export ONLY the youtube thumbnail (no clean background)
    yt = ae.export_youtube_thumbnail(sid, bg, "T", "S", "Seoul Records", "#ff0000")
    entry = ae._make_asset_entry(sid, AT.YOUTUBE_THUMBNAIL_16X9, yt)
    ae.write_asset_manifest(sid, [entry])
    sel = select_video_background(sid)
    assert sel["asset_type"] == AT.YOUTUBE_THUMBNAIL_16X9
    assert sel["is_clean_playback"] is False
    assert sel["warning"] is not None
    assert "playback" in sel["warning"].lower()


# ─── Streaming cover ─────────────────────────────────────────────────────────

def test_streaming_cover_generated_from_thumbnail(session_with_bg):
    from services.thumbnail import asset_exporter as ae
    sid, bg = session_with_bg
    yt = ae.export_youtube_thumbnail(sid, bg, "T", "S", "Seoul Records", "#ff0000")
    cover = ae.export_streaming_cover(sid, yt, bg, "T", "S", "Seoul Records", "#ff0000")
    assert cover is not None
    assert Path(cover).exists()


def test_streaming_cover_is_1x1(session_with_bg):
    from services.thumbnail import asset_exporter as ae
    from PIL import Image
    sid, bg = session_with_bg
    yt = ae.export_youtube_thumbnail(sid, bg, "T", "S", "Seoul Records", "#ff0000")
    cover = ae.export_streaming_cover(sid, yt, bg, "T", "S", "Seoul Records", "#ff0000")
    im = Image.open(cover)
    assert im.size[0] == im.size[1]  # square


def test_streaming_cover_preserves_playlist_title_metadata():
    from services.thumbnail import asset_types as AT
    flags = AT.default_content_flags(AT.STREAMING_COVER_1X1)
    assert flags["contains_playlist_title"] is True


def test_streaming_cover_has_no_waveform_cta_song_title_flags():
    from services.thumbnail import asset_types as AT
    flags = AT.default_content_flags(AT.STREAMING_COVER_1X1)
    assert flags["contains_waveform"] is False
    assert flags["contains_cta_sticker"] is False
    assert flags["contains_song_title"] is False


# ─── Asset manifest separation ───────────────────────────────────────────────

def test_asset_manifest_separates_thumbnail_video_background_streaming_cover(session_with_bg):
    from services.thumbnail import asset_exporter as ae
    from services.thumbnail import asset_types as AT
    sid, bg = session_with_bg
    ae.export_all_required_assets(sid, bg, "T", "S", "Seoul Records", "#ff0000")
    manifest = ae.load_asset_manifest(sid)
    types = {a["asset_type"] for a in manifest}
    assert AT.YOUTUBE_THUMBNAIL_16X9 in types
    assert AT.VIDEO_PLAYBACK_BACKGROUND_16X9 in types
    assert AT.STREAMING_COVER_1X1 in types
    # Each is a distinct entry with its own path
    paths = [a["path"] for a in manifest]
    assert len(paths) == len(set(paths))  # no duplicate paths


def test_thumbnail_studio_export_all_required_assets(session_with_bg):
    from services.thumbnail import asset_exporter as ae
    from services.thumbnail import asset_types as AT
    sid, bg = session_with_bg
    results = ae.export_all_required_assets(sid, bg, "T", "S", "Seoul Records", "#ff0000")
    for atype in AT.REQUIRED_OUTPUT_TYPES:
        assert atype in results
        assert Path(results[atype]).exists()
    assert "manifest" in results


# ─── Crop tool ───────────────────────────────────────────────────────────────

def test_crop_tool_supports_center_crop(session_with_bg):
    from services.thumbnail import asset_exporter as ae
    from PIL import Image
    sid, bg = session_with_bg
    sq = ae.crop_to_square(bg, 800, "center_crop")
    assert sq is not None
    assert sq.size == (800, 800)


def test_crop_tool_supports_fit_with_blur(session_with_bg):
    from services.thumbnail import asset_exporter as ae
    from PIL import Image
    sid, bg = session_with_bg
    sq = ae.crop_to_square(bg, 800, "fit_blur")
    assert sq is not None
    assert sq.size == (800, 800)


# ─── Video renderer defaults ─────────────────────────────────────────────────

def test_video_renderer_does_not_enable_center_playlist_title_by_default():
    from services.thumbnail.video_renderer_rules import VIDEO_DEFAULTS, build_video_overlay_plan
    assert VIDEO_DEFAULTS["center_playlist_title"] is False
    plan = build_video_overlay_plan()
    assert plan["center_playlist_title"] is False


def test_video_renderer_uses_overlay_assets_for_now_playing_cta_waveform():
    from services.thumbnail.video_renderer_rules import build_video_overlay_plan
    from services.thumbnail import asset_types as AT
    plan = build_video_overlay_plan(now_playing=True, waveform=True, cta_sticker=True)
    overlays = plan["overlays"]
    assert overlays[AT.NOW_PLAYING_CARD_ASSET] is True
    assert overlays[AT.DYNAMIC_VISUALIZER_OVERLAY] is True
    assert overlays[AT.CTA_STICKER_ASSET] is True


# ─── Independence preserved ──────────────────────────────────────────────────

def test_music_generation_codepath_unchanged_v07():
    from providers.ai.base import MOCK_SONGS, get_batch_vocal
    assert len(MOCK_SONGS) >= 2
    assert callable(get_batch_vocal)
