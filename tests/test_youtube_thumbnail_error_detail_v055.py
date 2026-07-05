"""
tests/test_youtube_thumbnail_error_detail_v055.py — v1.0.0-alpha.55

Real problem reported: video actually uploaded fine (private, OAuth was
genuinely working all along) but the SEPARATE thumbnail-set API call
failed — and set_thumbnail() swallowed the entire real exception,
returning only the generic "thumbnail set failed" with zero diagnostic
value. This is the exact same silent-swallowing anti-pattern already
fixed for OAuth in alpha.51/54, found here in a different code path.

set_thumbnail() now surfaces the real HTTP status + message from
YouTube's error body (via googleapiclient's HttpError.reason), and adds
a specific hint for the single most common real-world cause: a YouTube
channel that hasn't completed phone/channel verification cannot set
custom thumbnails AT ALL (via API or the website), regardless of how
valid the image file itself is — which is exactly why the user's
pre-flight "thumbnail under 2MB" check could pass while the actual
thumbnails.set call still failed.
"""
from __future__ import annotations

import pytest

try:
    from googleapiclient.errors import HttpError
    import httplib2
    _HAS_GOOGLEAPICLIENT = True
except Exception:
    _HAS_GOOGLEAPICLIENT = False


def _make_http_error(status: int, message: str, reason_phrase: str = "Forbidden"):
    """Build a real googleapiclient HttpError carrying a YouTube-shaped
    JSON error body, exactly like what the real API returns."""
    import json as _json

    class _Resp:
        def __init__(self, status, reason):
            self.status = status
            self.reason = reason

    body = _json.dumps({"error": {"message": message, "errors": [
        {"reason": "forbidden", "message": message}]}}).encode("utf-8")
    return HttpError(_Resp(status, reason_phrase), body, uri="https://x")


@pytest.mark.skipif(not _HAS_GOOGLEAPICLIENT, reason="googleapiclient not installed")
def test_set_thumbnail_surfaces_real_http_error_detail(monkeypatch, tmp_path):
    from services.youtube.youtube_api_client import RealYouTubeApiClient

    client = RealYouTubeApiClient.__new__(RealYouTubeApiClient)  # skip __init__/creds

    class _FakeThumbnails:
        def set(self, videoId, media_body):
            class _Req:
                def execute(self_):
                    raise _make_http_error(
                        400, "The image is invalid.")
            return _Req()

    class _FakeService:
        def thumbnails(self):
            return _FakeThumbnails()

    monkeypatch.setattr(client, "_build_service", lambda: _FakeService())
    thumb = tmp_path / "t.png"
    thumb.write_bytes(b"\x89PNG" + b"\x00" * 20)

    res = client.set_thumbnail("VID123", str(thumb))
    assert res["thumbnail_set"] is False
    assert "400" in res["error"]
    assert "invalid" in res["error"].lower()


@pytest.mark.skipif(not _HAS_GOOGLEAPICLIENT, reason="googleapiclient not installed")
def test_set_thumbnail_gives_channel_verification_hint_on_known_403(monkeypatch, tmp_path):
    """
    The single most common real-world cause: a channel that hasn't
    completed phone/channel verification is blocked from setting custom
    thumbnails entirely — this is a very well-known YouTube constraint
    that has nothing to do with file size/format, and users need a
    concrete pointer (not just "403 forbidden") to fix it.
    """
    from services.youtube.youtube_api_client import RealYouTubeApiClient
    client = RealYouTubeApiClient.__new__(RealYouTubeApiClient)

    class _FakeThumbnails:
        def set(self, videoId, media_body):
            class _Req:
                def execute(self_):
                    raise _make_http_error(
                        403, "The user is not eligible to set custom "
                             "thumbnails for videos on this channel because "
                             "the channel is not verified.")
            return _Req()

    class _FakeService:
        def thumbnails(self):
            return _FakeThumbnails()

    monkeypatch.setattr(client, "_build_service", lambda: _FakeService())
    thumb = tmp_path / "t.png"
    thumb.write_bytes(b"\x89PNG" + b"\x00" * 20)

    res = client.set_thumbnail("VID123", str(thumb))
    assert res["thumbnail_set"] is False
    assert "403" in res["error"]
    assert "채널 인증" in res["error"] or "전화번호" in res["error"]


@pytest.mark.skipif(not _HAS_GOOGLEAPICLIENT, reason="googleapiclient not installed")
def test_set_thumbnail_non_http_exception_still_gives_type_and_message(monkeypatch, tmp_path):
    from services.youtube.youtube_api_client import RealYouTubeApiClient
    client = RealYouTubeApiClient.__new__(RealYouTubeApiClient)

    class _FakeThumbnails:
        def set(self, videoId, media_body):
            class _Req:
                def execute(self_):
                    raise ConnectionResetError("connection reset by peer")
            return _Req()

    class _FakeService:
        def thumbnails(self):
            return _FakeThumbnails()

    monkeypatch.setattr(client, "_build_service", lambda: _FakeService())
    thumb = tmp_path / "t.png"
    thumb.write_bytes(b"\x89PNG" + b"\x00" * 20)

    res = client.set_thumbnail("VID123", str(thumb))
    assert res["thumbnail_set"] is False
    assert "ConnectionResetError" in res["error"]
    assert res["error"] != "thumbnail set failed"  # old generic message is gone


# ─── worker: real reason flows through to job state + UI ────────────────────

def _payload():
    from services.youtube.upload_payload_service import build_upload_payload
    return build_upload_payload("T", "d", ["citypop"], privacy_status="private")


@pytest.fixture(autouse=True)
def isolate_dirs(monkeypatch, tmp_path):
    import services.youtube.upload_job_store as ujs
    monkeypatch.setattr(ujs, "_jobs_dir", lambda: tmp_path / "youtube_upload" / "jobs")
    yield


def test_worker_stores_real_thumbnail_error_on_state(tmp_path):
    from services.youtube.upload_job_store import create_upload_job, load_upload_state
    from workers.youtube_upload_worker import run_upload_job

    video = tmp_path / "v.mp4"; video.write_bytes(b"\x00" * 1000)
    thumb = tmp_path / "t.png"; thumb.write_bytes(b"\x89PNG" + b"\x00" * 50)
    s = create_upload_job("pkg1", str(video), str(thumb), "T", _payload())
    jid = s["upload_job_id"]

    run_upload_job(jid, use_mock=True, mock_kwargs={"fail_thumbnail": True})
    state = load_upload_state(jid)
    assert state["status"] == "partial_success"
    assert state.get("thumbnail_error")  # not empty
    assert "mock thumbnail failure" in state["thumbnail_error"]


def test_worker_clears_thumbnail_error_after_successful_retry(tmp_path):
    from services.youtube.upload_job_store import create_upload_job, load_upload_state
    from workers.youtube_upload_worker import run_upload_job, run_thumbnail_retry

    video = tmp_path / "v.mp4"; video.write_bytes(b"\x00" * 1000)
    thumb = tmp_path / "t.png"; thumb.write_bytes(b"\x89PNG" + b"\x00" * 50)
    s = create_upload_job("pkg1", str(video), str(thumb), "T", _payload())
    jid = s["upload_job_id"]

    run_upload_job(jid, use_mock=True, mock_kwargs={"fail_thumbnail": True})
    assert load_upload_state(jid)["thumbnail_error"]

    run_thumbnail_retry(jid, use_mock=True, mock_kwargs={"fail_thumbnail": False})
    state = load_upload_state(jid)
    assert state["status"] == "completed"
    assert state.get("thumbnail_error", "") == ""


def test_ui_displays_the_real_thumbnail_error_reason():
    from pathlib import Path
    src = Path("app/tabs/youtube_package.py").read_text(encoding="utf-8")
    assert "thumbnail_error" in src
    assert "사유" in src
