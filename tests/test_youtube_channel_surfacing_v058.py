"""
tests/test_youtube_channel_surfacing_v058.py — v1.0.0-alpha.58

Real root cause found this session: the user has multiple YouTube
channels under one Gmail (a personal channel "한상" + a Brand channel
"Seoul Records" with 6,240 subscribers). OAuth uploads always land on the
Gmail account's DEFAULT channel ("한상"), and the YouTube Data API gives
no parameter to target a Brand Account channel — so every upload silently
went to the wrong channel, which is only why the intended channel's
Studio looked empty AND why the uploadLimitExceeded eventually fired
(against the wrong channel).

We can't make the API target a Brand channel (that's a YouTube
limitation — the user must pick the right channel at OAuth consent time),
but we CAN surface which channel each upload actually landed on, so a
wrong-channel upload is caught immediately instead of days later. This
adds channel_title/channel_id to the upload result → job state → UI.

Also flips the default upload mode to "API 비공개 업로드" per user request.
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolate_dirs(monkeypatch, tmp_path):
    import services.youtube.upload_job_store as ujs
    monkeypatch.setattr(ujs, "_jobs_dir", lambda: tmp_path / "youtube_upload" / "jobs")
    yield


def _payload():
    from services.youtube.upload_payload_service import build_upload_payload
    return build_upload_payload("T", "d", ["citypop"], privacy_status="private")


def _make_job(tmp_path):
    from services.youtube.upload_job_store import create_upload_job
    video = tmp_path / "v.mp4"; video.write_bytes(b"\x00" * 1000)
    thumb = tmp_path / "t.png"; thumb.write_bytes(b"\x89PNG" + b"\x00" * 50)
    s = create_upload_job("pkg1", str(video), str(thumb), "T", _payload())
    return s["upload_job_id"]


def test_upload_result_includes_channel_from_real_api_response():
    """The real client must read snippet.channelTitle/channelId from the
    videos.insert response and return them."""
    from services.youtube.youtube_api_client import RealYouTubeApiClient
    client = RealYouTubeApiClient.__new__(RealYouTubeApiClient)
    client._credentials = {"token": "x"}

    class _FakeReq:
        def __init__(self):
            self._done = False

        def next_chunk(self):
            # One shot: return the final response immediately.
            return (None, {
                "id": "VID999",
                "snippet": {"channelId": "UC_personal_han",
                            "channelTitle": "한상"},
            })

    class _FakeVideos:
        def insert(self, part, body, media_body):
            return _FakeReq()

    class _FakeService:
        def videos(self):
            return _FakeVideos()

    import types
    client._build_service = types.MethodType(lambda self: _FakeService(), client)

    # MediaFileUpload is imported inside the method; patch it to a stub.
    import sys
    fake_http = types.ModuleType("googleapiclient.http")
    fake_http.MediaFileUpload = lambda *a, **k: object()
    sys.modules["googleapiclient.http"] = fake_http

    res = client.upload_video_private(_payload(), "/tmp/x.mp4")
    assert res["status"] == "uploaded"
    assert res["video_id"] == "VID999"
    assert res["channel_title"] == "한상"
    assert res["channel_id"] == "UC_personal_han"


def test_worker_persists_channel_to_state(tmp_path):
    from services.youtube.upload_job_store import load_upload_state
    from workers.youtube_upload_worker import run_upload_job

    jid = _make_job(tmp_path)
    run_upload_job(jid, use_mock=True)  # mock returns "Mock Channel"
    state = load_upload_state(jid)
    assert state.get("channel_title") == "Mock Channel"
    assert state.get("channel_id") == "UC_MOCK"


def test_worker_logs_which_channel(tmp_path):
    from services.youtube.upload_job_store import _job_path
    from workers.youtube_upload_worker import run_upload_job
    import json

    jid = _make_job(tmp_path)
    run_upload_job(jid, use_mock=True)
    log_path = _job_path(jid) / "upload_log.jsonl"
    text = log_path.read_text(encoding="utf-8")
    assert "채널: Mock Channel" in text


def test_ui_shows_channel_on_completed_and_partial():
    src = Path("app/tabs/youtube_package.py").read_text(encoding="utf-8")
    assert "channel_title" in src
    # Completed view must surface the channel and a confirmation nudge.
    assert "채널" in src
    assert "의도한 채널이 맞는지" in src


def test_default_upload_mode_is_api_private():
    src = Path("app/tabs/youtube_package.py").read_text(encoding="utf-8")
    # The radio must default to index=1 (API private), not manual.
    assert "index=1" in src
    assert "API 비공개 업로드 (기본)" in src
