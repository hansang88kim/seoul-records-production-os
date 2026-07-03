"""
tests/test_midjourney_provider.py — Midjourney via Apiframe v2 (v1.0.0-alpha.32).

Covers the Midjourney image engine, rewritten for Apiframe v2
(https://api.apiframe.ai/v2 — X-API-Key auth, POST /images/generate,
GET /jobs/:id):
  * provider fails cleanly without an API key (no network)
  * submit → poll(QUEUED/PROCESSING) → poll(COMPLETED) happy path, files written
  * --no translation of the negative prompt; midjourneyParams.aspect_ratio sent
  * failed job and timeout surface clean errors WITHOUT the API key
  * verify_apiframe_key() (GET /v2/me) — used by the sidebar connect flow
  * factory routing: get_image_provider(engine="midjourney") — key/no-key
  * generate_images(engine=...) passes the engine through to the factory
  * dependency check reports readiness WITHOUT exposing the key

NO real Apiframe calls — every network touch is mocked, and the factory
returns the mock whenever APIFRAME_API_KEY is absent (always true in CI).
"""
from __future__ import annotations

import json
from unittest import mock

import pytest

import services.thumbnail.session_store as ss
from services.thumbnail import image_provider as ip
from services.thumbnail import image_gen_deps as deps
from services.thumbnail import midjourney_provider as mj


_FAKE_KEY = "afk_test_key_SECRET_9f8e7d"
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24  # minimal PNG-magic payload


@pytest.fixture(autouse=True)
def studio_tmp(monkeypatch, tmp_path):
    """Redirect the studio root to a temp folder and clear any real keys."""
    monkeypatch.setattr(ss, "_studio_root", lambda: tmp_path / "studio")
    for var in ip._API_KEY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("APIFRAME_API_KEY", raising=False)
    monkeypatch.setattr(mj, "_POLL_INTERVAL_SEC", 0)
    yield


def _resp(status_code=200, payload=None, content=b""):
    r = mock.Mock()
    r.status_code = status_code
    r.text = json.dumps(payload) if payload is not None else ""
    r.json = mock.Mock(return_value=payload if payload is not None else {})
    r.content = content
    return r


# ─── No key → clean failure, no network ──────────────────────────────────────

def test_mj_provider_no_key_returns_error_without_network():
    prov = mj.MidjourneyApiframeProvider(api_key=None)
    with mock.patch("requests.post") as post:
        r = prov.generate("seoul night drive", "/tmp/never.png")
    assert r["ok"] is False
    assert "API key" in r["error"] or "APIFRAME" in r["error"]
    post.assert_not_called()


# ─── Happy path: submit → QUEUED/PROCESSING → COMPLETED ──────────────────────

def test_mj_happy_path_polls_and_downloads(tmp_path):
    prov = mj.MidjourneyApiframeProvider(api_key=_FAKE_KEY)
    out = tmp_path / "cand" / "c1_16x9.png"

    posts, gets = [], []

    def fake_post(url, headers=None, json=None, timeout=None):
        posts.append({"url": url, "json": json, "headers": headers})
        assert url == f"{mj.APIFRAME_BASE_URL}/images/generate"
        return _resp(202, {"jobId": "job-abc-123", "status": "QUEUED"})

    def fake_get(url, headers=None, timeout=None):
        gets.append(url)
        assert url == f"{mj.APIFRAME_BASE_URL}/jobs/job-abc-123"
        if len(gets) == 1:
            return _resp(200, {"status": "PROCESSING", "progress": 40, "result": None})
        return _resp(200, {
            "status": "COMPLETED", "progress": 100,
            "result": {
                "images": [f"https://cdn2.apiframe.ai/images/job-abc-123-{i}.png" for i in range(1, 5)],
                "gridUrl": "https://cdn2.apiframe.ai/images/job-abc-123-grid.png",
            },
        })

    def fake_download(url, timeout=None):
        return _resp(200, content=_PNG)

    with mock.patch("requests.post", side_effect=fake_post), \
         mock.patch("requests.get", side_effect=lambda url, headers=None, timeout=None:
                     fake_get(url, headers, timeout) if "/jobs/" in url else fake_download(url, timeout)):
        r = prov.generate("neon rainy Seoul street, 1990s anime",
                          str(out), negative_prompt="text, watermark",
                          aspect="16:9")

    assert r["ok"] is True, r
    assert r["provider"] == "midjourney-apiframe"
    assert r["task_id"] == "job-abc-123"
    assert out.exists()

    # Submit payload: X-API-Key header + midjourneyParams.aspect_ratio + --no negatives
    submit = posts[0]
    assert submit["headers"]["X-API-Key"] == _FAKE_KEY
    assert submit["json"]["model"] == "midjourney"
    assert submit["json"]["midjourneyParams"]["aspect_ratio"] == "16:9"
    assert "--no text, watermark" in submit["json"]["prompt"]

    # The other 3 quadrants saved as _alt2.._alt4 next to the primary
    for n in (2, 3, 4):
        assert out.with_name(f"c1_16x9_alt{n}.png").exists()


def test_mj_no_negative_prompt_has_no_no_flag(tmp_path):
    prov = mj.MidjourneyApiframeProvider(api_key=_FAKE_KEY)
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["prompt"] = json["prompt"]
        return _resp(202, {"jobId": "t1", "status": "QUEUED"})

    def fake_get(url, headers=None, timeout=None):
        return _resp(200, {"status": "COMPLETED", "result": {"images": ["https://cdn2.apiframe.ai/images/1.png"]}})

    def fake_dl(url, timeout=None):
        return _resp(200, content=_PNG)

    with mock.patch("requests.post", side_effect=fake_post), \
         mock.patch("requests.get", side_effect=lambda url, headers=None, timeout=None:
                     fake_get(url) if "/jobs/" in url else fake_dl(url)):
        r = prov.generate("clean prompt", str(tmp_path / "o.png"), aspect="1:1")

    assert r["ok"] is True
    assert "--no" not in captured["prompt"]


# ─── Failure paths ────────────────────────────────────────────────────────────

def test_mj_failed_job_surfaces_error_without_key(tmp_path):
    prov = mj.MidjourneyApiframeProvider(api_key=_FAKE_KEY)

    def fake_post(url, headers=None, json=None, timeout=None):
        return _resp(202, {"jobId": "t-fail", "status": "QUEUED"})

    def fake_get(url, headers=None, timeout=None):
        return _resp(200, {"status": "FAILED", "error": f"banned prompt (key={_FAKE_KEY})"})

    with mock.patch("requests.post", side_effect=fake_post), \
         mock.patch("requests.get", side_effect=fake_get):
        r = prov.generate("bad", str(tmp_path / "x.png"))

    assert r["ok"] is False
    assert "failed" in r["error"]
    assert _FAKE_KEY not in r["error"]  # key must be masked


def test_mj_imagine_http_error_no_key_leak(tmp_path):
    prov = mj.MidjourneyApiframeProvider(api_key=_FAKE_KEY)

    def fake_post(url, headers=None, json=None, timeout=None):
        return _resp(401, {"error": f"invalid key {_FAKE_KEY}"})

    with mock.patch("requests.post", side_effect=fake_post):
        r = prov.generate("p", str(tmp_path / "x.png"))

    assert r["ok"] is False
    assert "HTTP 401" in r["error"]
    assert _FAKE_KEY not in r["error"]


def test_mj_v1_style_key_gets_clean_error(tmp_path):
    """Regression: a v1 key (no 'afk_' prefix) hitting v2 must surface the
    server's error text cleanly, not crash — this is exactly what happened
    in production before this rewrite."""
    prov = mj.MidjourneyApiframeProvider(api_key="v1-style-key-no-prefix")

    def fake_post(url, headers=None, json=None, timeout=None):
        return _resp(400, {"error": "Your API key starts with 'v1' which means you are on Apiframe v1."})

    with mock.patch("requests.post", side_effect=fake_post):
        r = prov.generate("p", str(tmp_path / "x.png"))

    assert r["ok"] is False
    assert "HTTP 400" in r["error"]


def test_mj_timeout_returns_clean_error(monkeypatch, tmp_path):
    monkeypatch.setenv("SEOUL_MJ_TIMEOUT", "30")  # min clamp is 30

    # Freeze-step time: each time.time() call advances past the deadline fast.
    ticks = iter([0, 0, 100, 100, 100])
    monkeypatch.setattr(mj.time, "time", lambda: next(ticks, 100))

    prov = mj.MidjourneyApiframeProvider(api_key=_FAKE_KEY)

    def fake_post(url, headers=None, json=None, timeout=None):
        return _resp(202, {"jobId": "t-slow", "status": "QUEUED"})

    def fake_get(url, headers=None, timeout=None):
        return _resp(200, {"status": "PROCESSING", "progress": 10})

    with mock.patch("requests.post", side_effect=fake_post), \
         mock.patch("requests.get", side_effect=fake_get):
        r = prov.generate("slow", str(tmp_path / "x.png"))

    assert r["ok"] is False
    assert "timed out" in r["error"]


def test_mj_imagine_no_job_id_is_error(tmp_path):
    prov = mj.MidjourneyApiframeProvider(api_key=_FAKE_KEY)
    with mock.patch("requests.post", return_value=_resp(202, {"message": "queued?"})):
        r = prov.generate("p", str(tmp_path / "x.png"))
    assert r["ok"] is False
    assert "jobId" in r["error"]


# ─── Capacity-error retry (v1.0.0-alpha.33) ──────────────────────────────────

def test_mj_retries_on_capacity_error_then_succeeds(monkeypatch, tmp_path):
    monkeypatch.setattr(mj, "_CAPACITY_BACKOFF_SEC", (0, 0, 0))
    prov = mj.MidjourneyApiframeProvider(api_key=_FAKE_KEY)
    submit_calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        submit_calls.append(1)
        return _resp(202, {"jobId": f"job-{len(submit_calls)}", "status": "QUEUED"})

    def fake_get(url, headers=None, timeout=None):
        if len(submit_calls) == 1:
            return _resp(200, {"status": "FAILED", "error": "No available capacity — please retry shortly"})
        return _resp(200, {"status": "COMPLETED", "result": {"images": ["https://cdn2.apiframe.ai/images/ok.png"]}})

    def fake_dl(url, timeout=None):
        return _resp(200, content=_PNG)

    with mock.patch("requests.post", side_effect=fake_post), \
         mock.patch("requests.get", side_effect=lambda url, headers=None, timeout=None:
                     fake_get(url) if "/jobs/" in url else fake_dl(url)):
        r = prov.generate("p", str(tmp_path / "x.png"))

    assert r["ok"] is True
    assert len(submit_calls) == 2  # first attempt failed with capacity, second succeeded


def test_mj_gives_up_after_max_capacity_retries(monkeypatch, tmp_path):
    monkeypatch.setattr(mj, "_CAPACITY_BACKOFF_SEC", (0, 0, 0))
    monkeypatch.setenv("SEOUL_MJ_CAPACITY_RETRIES", "1")  # 2 total attempts
    prov = mj.MidjourneyApiframeProvider(api_key=_FAKE_KEY)
    submit_calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        submit_calls.append(1)
        return _resp(202, {"jobId": "job-x", "status": "QUEUED"})

    def fake_get(url, headers=None, timeout=None):
        return _resp(200, {"status": "FAILED", "error": "No available capacity"})

    with mock.patch("requests.post", side_effect=fake_post), \
         mock.patch("requests.get", side_effect=fake_get):
        r = prov.generate("p", str(tmp_path / "x.png"))

    assert r["ok"] is False
    assert "capacity" in r["error"].lower()
    assert len(submit_calls) == 2  # 1 initial + 1 retry, then gives up


def test_mj_non_capacity_error_does_not_retry(monkeypatch, tmp_path):
    monkeypatch.setattr(mj, "_CAPACITY_BACKOFF_SEC", (0, 0, 0))
    prov = mj.MidjourneyApiframeProvider(api_key=_FAKE_KEY)
    submit_calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        submit_calls.append(1)
        return _resp(401, {"error": "invalid key"})

    with mock.patch("requests.post", side_effect=fake_post):
        r = prov.generate("p", str(tmp_path / "x.png"))

    assert r["ok"] is False
    assert len(submit_calls) == 1  # no retry on a non-transient error


def test_is_capacity_error_detects_known_markers():
    assert mj._is_capacity_error("No available capacity — please retry shortly")
    assert mj._is_capacity_error("imagine HTTP 503: queue is temporarily unavailable")
    assert not mj._is_capacity_error("invalid API key")
    assert not mj._is_capacity_error("")


# ─── verify_apiframe_key (GET /v2/me — sidebar connect flow) ────────────────

def test_verify_apiframe_key_success():
    def fake_get(url, headers=None, timeout=None):
        assert url == f"{mj.APIFRAME_BASE_URL}/me"
        assert headers["X-API-Key"] == _FAKE_KEY
        return _resp(200, {"user": {"email": "a@b.com", "role": "ADMIN"},
                           "team": {"plan": "free", "credits": 50}})

    with mock.patch("requests.get", side_effect=fake_get):
        ok, msg = mj.verify_apiframe_key(_FAKE_KEY)
    assert ok is True
    assert "50" in msg


def test_verify_apiframe_key_401():
    with mock.patch("requests.get", return_value=_resp(401, {"error": "invalid"})):
        ok, msg = mj.verify_apiframe_key(_FAKE_KEY)
    assert ok is False
    assert _FAKE_KEY not in msg


def test_verify_apiframe_key_v1_key_hint():
    with mock.patch("requests.get", return_value=_resp(400, {"error": "wrong version"})):
        ok, msg = mj.verify_apiframe_key("not-an-afk-key")
    assert ok is False
    assert "v2" in msg or "afk_" in msg


# ─── Factory routing ─────────────────────────────────────────────────────────

def test_factory_midjourney_without_key_returns_mock():
    prov = ip.get_image_provider(use_real=True, engine="midjourney")
    assert isinstance(prov, ip.MockImageGenProvider)


def test_factory_midjourney_with_key_returns_mj_provider(monkeypatch):
    monkeypatch.setenv("APIFRAME_API_KEY", _FAKE_KEY)
    prov = ip.get_image_provider(use_real=True, engine="midjourney")
    assert prov.name == "midjourney-apiframe"
    assert prov.is_real is True


def test_factory_midjourney_use_real_false_returns_mock(monkeypatch):
    monkeypatch.setenv("APIFRAME_API_KEY", _FAKE_KEY)
    prov = ip.get_image_provider(use_real=False, engine="midjourney")
    assert isinstance(prov, ip.MockImageGenProvider)


def test_factory_default_engine_is_gemini_backcompat():
    # Old call sites without `engine` must behave exactly as before.
    prov = ip.get_image_provider(use_real=False)
    assert isinstance(prov, ip.MockImageGenProvider)


# ─── session_store pass-through ──────────────────────────────────────────────

def test_generate_images_passes_engine_to_factory(monkeypatch):
    seen = {}
    real_factory = ip.get_image_provider

    def spy(use_real=False, model=None, engine="gemini"):
        seen["engine"] = engine
        return real_factory(use_real=False)  # always mock under test

    monkeypatch.setattr(ip, "get_image_provider", spy)
    sess = ss.create_session("kr", "rainy night", "CityPop", 1, "")
    prompts = [{"main_prompt": "p", "negative_prompt": "", "scene": "s",
                "country": "kr", "theme": "t"}]
    ss.generate_images(sess["session_id"], prompts, use_real=True, engine="midjourney")
    assert seen["engine"] == "midjourney"


# ─── Dependency check ────────────────────────────────────────────────────────

def test_mj_dependency_check_no_key():
    d = deps.check_midjourney_dependencies()
    assert d["ready"] is False
    assert d["api_key_present"] is False
    assert "APIFRAME_API_KEY" in d["key_env_vars"]


def test_mj_dependency_check_with_key_never_exposes_value(monkeypatch):
    monkeypatch.setenv("APIFRAME_API_KEY", _FAKE_KEY)
    d = deps.check_midjourney_dependencies()
    assert d["ready"] is True
    assert _FAKE_KEY not in str(d)


def test_get_apiframe_key_reads_env(monkeypatch):
    monkeypatch.setenv("APIFRAME_API_KEY", "  padded_key  ")
    assert mj.get_apiframe_key() == "padded_key"
    monkeypatch.delenv("APIFRAME_API_KEY")
    assert mj.get_apiframe_key() is None
