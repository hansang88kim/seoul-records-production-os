"""
tests/test_youtube_upload_exception_detail_v057.py — v1.0.0-alpha.57

Real report: a failed upload job whose upload_result.json contained only
{"status": "failed", "errors": ["upload exception"]} — an opaque constant
with zero diagnostic value. This is the SAME silent-swallow anti-pattern
already fixed three times (authorize() in alpha.51/54, set_thumbnail() in
alpha.55), found here in the last place it still lived: the worker's
top-level upload try/except, which discarded the real exception `e` and
wrote the fixed string "upload exception".

This surfaces the real (redacted) exception type + message into the job
state/result/log and the UI, and adds a targeted hint for the most likely
real cause in context — a stale/invalid OAuth token after the user
swapped in a new client_secret.json (google.auth RefreshError /
invalid_grant), which requires deleting the old token and re-authing.
"""
from __future__ import annotations

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


def test_upload_exception_surfaces_real_type_and_message(tmp_path):
    import json
    from services.youtube.upload_job_store import load_upload_state, _job_path
    from workers.youtube_upload_worker import run_upload_job

    jid = _make_job(tmp_path)
    boom = RuntimeError("connection reset during resumable upload")
    run_upload_job(jid, use_mock=True, mock_kwargs={"raise_upload": boom})

    state = load_upload_state(jid)
    assert state["status"] == "failed"
    # The opaque constant must be gone; real detail must be present.
    assert "upload exception" not in state["last_message"]
    assert "RuntimeError" in state["last_message"]
    assert "connection reset" in state["last_message"]

    result = json.loads((_job_path(jid) / "upload_result.json").read_text(encoding="utf-8"))
    assert result["status"] == "failed"
    assert any("RuntimeError" in e for e in result["errors"])
    assert all(e != "upload exception" for e in result["errors"])


def test_upload_exception_invalid_grant_gets_reauth_hint(tmp_path):
    """The most likely real cause after swapping client_secret.json: the
    saved token no longer matches, so google-auth raises an
    invalid_grant / RefreshError. The failure message must tell the user
    to delete the token and re-auth, not just show a raw stack type."""
    from services.youtube.upload_job_store import load_upload_state
    from workers.youtube_upload_worker import run_upload_job

    jid = _make_job(tmp_path)
    boom = Exception("('invalid_grant: Token has been expired or revoked.', "
                     "{'error': 'invalid_grant'})")
    run_upload_job(jid, use_mock=True, mock_kwargs={"raise_upload": boom})

    state = load_upload_state(jid)
    assert state["status"] == "failed"
    assert "토큰" in state["last_message"]
    assert "인증" in state["last_message"] and ("삭제" in state["last_message"]
                                              or "다시" in state["last_message"])


def test_non_auth_upload_exception_has_no_spurious_reauth_hint(tmp_path):
    from services.youtube.upload_job_store import load_upload_state
    from workers.youtube_upload_worker import run_upload_job

    jid = _make_job(tmp_path)
    boom = OSError("disk full while buffering upload")
    run_upload_job(jid, use_mock=True, mock_kwargs={"raise_upload": boom})

    state = load_upload_state(jid)
    assert state["status"] == "failed"
    assert "OSError" in state["last_message"]
    assert "disk full" in state["last_message"]
    # Should NOT wrongly tell them to re-auth for a disk error.
    assert "토큰" not in state["last_message"]


def test_worker_source_no_longer_contains_opaque_constant():
    import inspect
    import workers.youtube_upload_worker as w
    src = inspect.getsource(w)
    # The literal fixed error string must be gone from the actual CODE.
    # It legitimately still appears inside the explanatory comment (which
    # documents why it was removed), so strip comment lines before
    # checking — what matters is that no code path writes it anymore.
    code_only = "\n".join(
        line for line in src.splitlines()
        if not line.lstrip().startswith("#"))
    assert '"upload exception"' not in code_only
    assert "'upload exception'" not in code_only


def test_successful_upload_still_works_unaffected(tmp_path):
    from services.youtube.upload_job_store import load_upload_state
    from workers.youtube_upload_worker import run_upload_job

    jid = _make_job(tmp_path)
    run_upload_job(jid, use_mock=True)  # no failure injected
    state = load_upload_state(jid)
    # completed (thumbnail mock succeeds) — definitely not failed.
    assert state["status"] in ("completed", "partial_success")
    assert state["status"] != "failed"
