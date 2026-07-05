"""
tests/test_youtube_package_v080.py — YouTube Package Studio tests.

No real YouTube API calls. Mock client only. Existing tabs must be unaffected.
"""
from __future__ import annotations
import json
import pytest
from pathlib import Path


@pytest.fixture
def yt_outputs(monkeypatch, tmp_path):
    """Create fake outputs (video/thumbnail/chapters) and point scanners at them."""
    try:
        from PIL import Image  # noqa
    except ImportError:
        pytest.skip("PIL not available")
    from PIL import Image
    import services.youtube.asset_scanner as AS

    outputs = tmp_path / "outputs"
    vr = outputs / "video_renderer" / "jobs" / "job1"
    vr.mkdir(parents=True)
    ts = outputs / "thumbnail_studio" / "sess1" / "exports"
    ts.mkdir(parents=True)

    # final_video.mp4
    video = vr / "final_video.mp4"
    video.write_bytes(b"\x00" * 1024)
    # chapters.txt
    chapters = vr / "chapters.txt"
    chapters.write_text("00:00 밤이 지나면\n03:30 늦은 대답\n07:00 서울의 밤", encoding="utf-8")
    # youtube_thumbnail_16x9.png
    thumb = ts / "youtube_thumbnail_16x9.png"
    Image.new("RGB", (1920, 1080), (40, 50, 80)).save(thumb)

    monkeypatch.setattr(AS, "_outputs_root", lambda: outputs)
    return {"outputs": outputs, "video": str(video),
            "thumb": str(thumb), "chapters": str(chapters)}


@pytest.fixture
def pkg_root(monkeypatch, tmp_path):
    import services.youtube.youtube_package_service as YPS
    monkeypatch.setattr(YPS, "_packages_root", lambda: tmp_path / "yt_packages")
    yield tmp_path / "yt_packages"


# ─── Tab exists ──────────────────────────────────────────────────────────────

def test_youtube_package_tab_exists():
    from app.tabs.youtube_package import render_youtube_package
    assert callable(render_youtube_package)


# ─── Asset scanning ──────────────────────────────────────────────────────────

def test_video_scan_finds_final_video_mp4(yt_outputs):
    from services.youtube.asset_scanner import scan_final_videos
    videos = scan_final_videos()
    assert any(v["name"] == "final_video.mp4" for v in videos)


def test_thumbnail_scan_finds_youtube_thumbnail(yt_outputs):
    from services.youtube.asset_scanner import scan_youtube_thumbnails
    thumbs = scan_youtube_thumbnails()
    assert any(t["name"] == "youtube_thumbnail_16x9.png" for t in thumbs)


def test_chapters_scan_finds_chapters(yt_outputs):
    from services.youtube.asset_scanner import scan_chapters
    chs = scan_chapters()
    assert any(c["name"] == "chapters.txt" for c in chs)


# ─── Metadata generator ──────────────────────────────────────────────────────

def test_metadata_generator_creates_title():
    from services.youtube.metadata_generator import generate_title
    title = generate_title("", "Korea", 1, 60, "Rainy Night Drive")
    assert "CityPop" in title
    assert "Vol.1" in title
    assert len(title) <= 100


def test_metadata_generator_creates_description(yt_outputs):
    # Legacy English auto-description path (alpha.59 kept it behind
    # use_djhana_template=False; the default is now the DJ HANA frame).
    from services.youtube.metadata_generator import generate_all_metadata
    meta = generate_all_metadata("", "Korea", 1, "Night Drive",
                                 yt_outputs["chapters"], 60,
                                 use_djhana_template=False)
    desc = meta["description"]
    assert "About this mix" in desc
    assert "Seoul Records" in desc
    assert "Listen while" in desc


def test_metadata_generator_includes_chapters(yt_outputs):
    from services.youtube.metadata_generator import generate_all_metadata
    meta = generate_all_metadata("", "Korea", 1, "", yt_outputs["chapters"], 60,
                                 use_djhana_template=False)
    # Chapters preserved with exact timestamps + Korean (no mojibake)
    assert "00:00 밤이 지나면" in meta["description"]
    assert "03:30 늦은 대답" in meta["chapters_section"]
    assert len(meta["chapters"]) == 3


def test_metadata_generator_creates_tags():
    from services.youtube.metadata_generator import generate_tags
    tags = generate_tags("Korea", "night drive", 1)
    assert "citypop" in tags
    assert len(tags) <= 30
    # No '#' in plain tags
    assert all(not t.startswith("#") for t in tags)


def test_pinned_comment_created():
    from services.youtube.metadata_generator import generate_pinned_comment
    pc = generate_pinned_comment("Korea", 1)
    assert "Seoul Records" in pc
    # Mentions the next volume
    assert "Vol.2" in pc


def test_chapters_no_mojibake(yt_outputs):
    """Korean chapter titles must round-trip without corruption."""
    from services.youtube.metadata_generator import parse_chapters_txt
    chs = parse_chapters_txt(yt_outputs["chapters"])
    titles = [c["title"] for c in chs]
    assert "밤이 지나면" in titles
    assert "서울의 밤" in titles


def test_filename_cleaned_title_fallback():
    from services.youtube.metadata_generator import _clean_filename_title
    assert _clean_filename_title("밤이_지나면.mp3") == "밤이 지나면"


# ─── Thumbnail validation ────────────────────────────────────────────────────

def test_thumbnail_validator_accepts_16x9_png(yt_outputs, tmp_path):
    from services.youtube.thumbnail_validator import validate_thumbnail, STATUS_READY
    out = tmp_path / "val"
    result = validate_thumbnail(yt_outputs["thumb"], str(out))
    assert result["status"] == STATUS_READY
    assert result["aspect_ok"] is True
    assert result["width"] == 1920 and result["height"] == 1080


def test_thumbnail_compresses_over_2mb(tmp_path):
    """A >2MB thumbnail produces a compressed upload-ready copy (original kept)."""
    from PIL import Image
    import random
    from services.youtube.thumbnail_validator import validate_thumbnail, STATUS_COMPRESSED
    # Create a noisy image that will be large as PNG
    big = tmp_path / "youtube_thumbnail_16x9.png"
    img = Image.new("RGB", (1920, 1080))
    px = img.load()
    random.seed(1)
    for y in range(0, 1080, 1):
        for x in range(0, 1920, 1):
            px[x, y] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    img.save(big, "PNG")
    assert big.stat().st_size > 2 * 1024 * 1024  # ensure it's actually >2MB

    out = tmp_path / "val"
    result = validate_thumbnail(str(big), str(out))
    assert result["status"] == STATUS_COMPRESSED
    # Upload-ready copy is under 2MB
    assert result["upload_ready_size_mb"] <= 2.0
    # Original NOT overwritten
    assert big.stat().st_size > 2 * 1024 * 1024
    # Upload-ready is a separate file
    assert Path(result["upload_ready_path"]).exists()
    assert Path(result["upload_ready_path"]).name == "thumbnail_upload_ready.jpg"


def test_thumbnail_upload_ready_created(yt_outputs, tmp_path):
    from services.youtube.thumbnail_validator import validate_thumbnail
    out = tmp_path / "val"
    result = validate_thumbnail(yt_outputs["thumb"], str(out))
    assert result["upload_ready_path"] is not None
    assert Path(result["upload_ready_path"]).exists()


def test_thumbnail_missing_status(tmp_path):
    from services.youtube.thumbnail_validator import validate_thumbnail, STATUS_MISSING
    result = validate_thumbnail("/does/not/exist.png", str(tmp_path))
    assert result["status"] == STATUS_MISSING


# ─── Package creation ────────────────────────────────────────────────────────

def test_package_manifest_created(yt_outputs, pkg_root):
    from services.youtube.youtube_package_service import create_package
    manifest = create_package(yt_outputs["video"], yt_outputs["thumb"],
                              yt_outputs["chapters"], country="Korea", volume=1)
    pkg_dir = Path(manifest["package_dir"])
    assert (pkg_dir / "package_manifest.json").exists()
    # Required manifest fields
    for field in ["package_id", "created_at", "video_path", "title",
                  "tags", "hashtags", "privacy_status_default", "upload_mode",
                  "status", "warnings"]:
        assert field in manifest


def test_all_metadata_files_written(yt_outputs, pkg_root):
    from services.youtube.youtube_package_service import create_package
    manifest = create_package(yt_outputs["video"], yt_outputs["thumb"],
                              yt_outputs["chapters"], country="Korea", volume=1)
    pkg_dir = Path(manifest["package_dir"])
    for fname in ["title.txt", "description.txt", "tags.txt", "hashtags.txt",
                  "pinned_comment.txt", "chapters_youtube.txt",
                  "upload_checklist.md", "youtube_upload_payload.json",
                  "selected_video_reference.json"]:
        assert (pkg_dir / fname).exists(), f"missing {fname}"


def test_upload_payload_created(yt_outputs, pkg_root):
    from services.youtube.youtube_package_service import create_package
    manifest = create_package(yt_outputs["video"], yt_outputs["thumb"],
                              yt_outputs["chapters"], country="Korea")
    payload_path = Path(manifest["package_dir"]) / "youtube_upload_payload.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert "snippet" in payload
    assert "status" in payload
    assert payload["status"]["privacyStatus"] == "private"


def test_manual_upload_package_created(yt_outputs, pkg_root):
    from services.youtube.youtube_package_service import create_package, build_manual_package_zip
    manifest = create_package(yt_outputs["video"], yt_outputs["thumb"],
                              yt_outputs["chapters"])
    zip_path = build_manual_package_zip(manifest["package_dir"])
    assert zip_path is not None
    assert Path(zip_path).exists()
    assert zip_path.endswith("manual_upload_package.zip")


def test_chapters_youtube_preserves_timestamps(yt_outputs, pkg_root):
    from services.youtube.youtube_package_service import create_package
    manifest = create_package(yt_outputs["video"], yt_outputs["thumb"],
                              yt_outputs["chapters"], country="Korea")
    ch = (Path(manifest["package_dir"]) / "chapters_youtube.txt").read_text(encoding="utf-8")
    assert "00:00" in ch
    assert "밤이 지나면" in ch  # Korean preserved


# ─── Upload modes ────────────────────────────────────────────────────────────

def test_default_upload_mode_is_manual_package_only():
    from services.youtube.youtube_package_service import DEFAULT_UPLOAD_MODE, UPLOAD_MODE_MANUAL
    assert DEFAULT_UPLOAD_MODE == UPLOAD_MODE_MANUAL


def test_private_upload_default_if_api_mode():
    from services.youtube.upload_payload_service import build_upload_payload, DEFAULT_PRIVACY
    assert DEFAULT_PRIVACY == "private"
    payload = build_upload_payload("T", "D", ["tag"])
    assert payload["status"]["privacyStatus"] == "private"


def test_api_upload_not_called_in_tests(yt_outputs, pkg_root):
    """Creating a package must NOT trigger any upload (mock or real)."""
    from services.youtube.youtube_package_service import create_package
    from services.youtube import youtube_api_client as YAC
    from unittest import mock
    # Spy on the mock client to ensure it's never instantiated during packaging
    with mock.patch.object(YAC.MockYouTubeClient, "upload_video") as up:
        create_package(yt_outputs["video"], yt_outputs["thumb"], yt_outputs["chapters"])
        assert up.call_count == 0


def test_mock_client_uploads_private_by_default():
    from services.youtube.youtube_api_client import MockYouTubeClient
    client = MockYouTubeClient()
    from services.youtube.upload_payload_service import build_upload_payload
    payload = build_upload_payload("T", "D", [])
    result = client.upload_video("/v.mp4", payload, privacy_status="private")
    assert result["privacy_status"] == "private"
    assert result["mock"] is True


# ─── Secret handling ─────────────────────────────────────────────────────────

def test_oauth_token_not_logged(tmp_path):
    """save_upload_result must strip any token from the saved file."""
    from services.youtube.youtube_api_client import save_upload_result
    result = {
        "video_id": "X", "url": "https://youtu.be/X",
        "access_token": "ya29.SECRET_TOKEN", "refresh_token": "RT_SECRET",
    }
    path = save_upload_result(str(tmp_path), result)
    content = Path(path).read_text(encoding="utf-8")
    assert "ya29.SECRET_TOKEN" not in content
    assert "RT_SECRET" not in content
    assert "***REDACTED***" in content


def test_authorization_header_redacted():
    from services.youtube.youtube_api_client import redact_authorization_header, REDACTED
    headers = {"Authorization": "Bearer ya29.SECRET", "Content-Type": "application/json"}
    safe = redact_authorization_header(headers)
    assert safe["Authorization"] == REDACTED
    assert safe["Content-Type"] == "application/json"


def test_sanitize_strips_nested_secrets():
    from services.youtube.youtube_api_client import sanitize_for_log
    data = {"ok": "visible", "creds": {"api_key": "SECRET123", "user": "me"}}
    safe = sanitize_for_log(data)
    assert safe["ok"] == "visible"
    assert safe["creds"]["api_key"] == "***REDACTED***"
    assert safe["creds"]["user"] == "me"


# ─── Existing tabs unaffected ────────────────────────────────────────────────

def test_existing_music_generation_unaffected():
    from providers.ai.base import MOCK_SONGS, build_system_prompt  # noqa
    assert len(MOCK_SONGS) >= 2


def test_existing_thumbnail_studio_unaffected():
    from services.thumbnail.prompt_generator import generate_flow_prompt
    from services.thumbnail.asset_exporter import export_youtube_thumbnail  # noqa
    assert generate_flow_prompt("korea", "n", 0)["main_prompt"]


def test_existing_video_renderer_unaffected():
    from services.video.playlist_builder import build_playlist_plan
    from services.video.render_plan import build_full_render_command  # noqa
    from services.video.filter_complex_builder import build_video_filter_complex  # noqa
    plan = build_playlist_plan(
        [{"path": "/a.mp3", "name": "a.mp3", "duration_sec": 210}], 60, True)
    assert plan["entries"]
