"""
tests/test_youtube_thumbnail_hint_correction_v056.py — v1.0.0-alpha.56

Real-world disproof from the person's own retry: they completed YouTube
channel phone verification, clicked "썸네일만 재시도" on the SAME video,
and got the IDENTICAL HTTP 403 again. That's direct evidence that channel
phone verification is NOT (solely) the blocker alpha.55's hint claimed it
was — thumbnails.set returning a persistent 403 despite full scopes and a
verified channel matches a widely-reported pattern most consistent with
an APP-level (OAuth client audit/verification) restriction instead.

This corrects the hint to stop confidently asserting "인증하면 풀린다"
and instead present both possibilities, leading with the practical
workaround (manual thumbnail set in YouTube Studio) since automated
retries have proven ineffective for this exact case. It also adds a
direct Studio edit link to the partial_success UI so the workaround is
one click away instead of requiring the person to navigate there
manually.
"""
from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

try:
    from googleapiclient.errors import HttpError
    _HAS_GOOGLEAPICLIENT = True
except Exception:
    _HAS_GOOGLEAPICLIENT = False


def _make_http_error(status: int, message: str):
    import json as _json

    class _Resp:
        def __init__(self, status):
            self.status = status
            self.reason = "Forbidden"

    body = _json.dumps({"error": {"message": message}}).encode("utf-8")
    return HttpError(_Resp(status), body, uri="https://x")


@pytest.mark.skipif(not _HAS_GOOGLEAPICLIENT, reason="googleapiclient not installed")
def test_hint_no_longer_asserts_verification_as_the_fix(monkeypatch, tmp_path):
    """The hint must not confidently claim phone verification resolves
    this — it must present it as one possibility among others, since a
    real retry after verification reproduced the identical error."""
    from services.youtube.youtube_api_client import RealYouTubeApiClient
    client = RealYouTubeApiClient.__new__(RealYouTubeApiClient)

    class _FakeThumbnails:
        def set(self, videoId, media_body):
            class _Req:
                def execute(self_):
                    raise _make_http_error(
                        403, "The authenticated user doesn't have "
                             "permissions to upload and set custom "
                             "video thumbnails.")
            return _Req()

    class _FakeService:
        def thumbnails(self):
            return _FakeThumbnails()

    monkeypatch.setattr(client, "_build_service", lambda: _FakeService())
    thumb = tmp_path / "t.png"
    thumb.write_bytes(b"\x89PNG" + b"\x00" * 20)

    res = client.set_thumbnail("VID123", str(thumb))
    err = res["error"]
    assert res["thumbnail_set"] is False
    # Still mentions channel verification as A possibility...
    assert "채널 인증" in err or "전화번호" in err
    # ...but must NOT present it as the confirmed/sole explanation, and
    # must surface the more likely structural (app audit) cause + the
    # practical workaround.
    assert "심사" in err or "Audit" in err or "audit" in err.lower()
    assert "수동" in err
    assert "직접 설정" in err or "직접" in err


@pytest.mark.skipif(not _HAS_GOOGLEAPICLIENT, reason="googleapiclient not installed")
def test_old_overconfident_wording_is_gone():
    """The specific alpha.55 wording that asserted verification as THE
    cause ('완료되지 않은 채널은 ... 막습니다') must not appear anymore —
    it was empirically disproven."""
    src = Path("services/youtube/youtube_api_client.py").read_text(encoding="utf-8")
    assert "완료되지 않은 채널은 API로도 커스텀 썸네일 설정을 막습니다" not in src


def test_partial_success_ui_has_direct_studio_edit_link():
    src = Path("app/tabs/youtube_package.py").read_text(encoding="utf-8")
    assert "studio.youtube.com/video/" in src
    assert "/edit" in src


def test_studio_link_uses_the_actual_video_id_variable():
    src = Path("app/tabs/youtube_package.py").read_text(encoding="utf-8")
    # Must be an f-string interpolating the real video_id, not a fixed
    # placeholder — otherwise every partial_success would link nowhere.
    assert "https://studio.youtube.com/video/{vid}/edit" in src
