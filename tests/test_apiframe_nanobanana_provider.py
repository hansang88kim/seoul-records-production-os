"""
tests/test_apiframe_nanobanana_provider.py — Nano Banana 2 via Apiframe v2
(v1.0.0-alpha.34).

Reuses the same APIFRAME_API_KEY already connected for Midjourney — this
engine was added as a direct replacement for the Midjourney/Apiframe combo
after Apiframe's Midjourney account pool proved unreliable in production
(confirmed failing even in Apiframe's own Playground). Nano Banana 2 is
Google's officially licensed model, so this sidesteps that risk entirely
while reusing the same proven job-submit/poll/capacity-retry pattern.

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
from services.thumbnail import apiframe_nanobanana_provider as nb
from services.thumbnail import midjourney_provider as mj


_FAKE_KEY = "afk_test_key_SECRET_9f8e7d"
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


@pytest.fixture(autouse=True)
def studio_tmp(monkeypatch, tmp_path):
    monkeypatch.setattr(ss, "_studio_root", lambda: tmp_path / "studio")
    for var in ip._API_KEY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("APIFRAME_API_KEY", raising=False)
    monkeypatch.setattr(nb, "_POLL_INTERVAL_SEC", 0)
    monkeypatch.setattr(nb, "_CAPACITY_BACKOFF_SEC", (0, 0, 0))
    yield


def _resp(status_code=200, payload=None, content=b""):
    r = mock.Mock()
    r.status_code = status_code
    r.text = json.dumps(payload) if payload is not None else ""
    r.json = mock.Mock(return_value=payload if payload is not None else {})
    r.content = content
    return r


def test_nb_no_key_returns_error_without_network():
    prov = nb.ApiframeNanoBananaProvider(api_key=None)
    with mock.patch("requests.post") as post:
        r = prov.generate("seoul night drive", "/tmp/never.png")
    assert r["ok"] is False
    assert "API key" in r["error"] or "APIFRAME" in r["error"]
    post.assert_not_called()


def test_nb_happy_path_submits_polls_downloads(tmp_path):
    prov = nb.ApiframeNanoBananaProvider(api_key=_FAKE_KEY)
    out = tmp_path / "cand" / "c1_16x9.png"
    posts, gets = [], []

    def fake_post(url, headers=None, json=None, timeout=None):
        posts.append({"url": url, "json": json, "headers": headers})
        assert url == f"{nb.APIFRAME_BASE_URL}/images/generate"
        return _resp(202, {"jobId": "job-nb-1", "status": "QUEUED"})

    def fake_get(url, headers=None, timeout=None):
        gets.append(url)
        assert url == f"{nb.APIFRAME_BASE_URL}/jobs/job-nb-1"
        if len(gets) == 1:
            return _resp(200, {"status": "PROCESSING", "progress": 50})
        return _resp(200, {"status": "COMPLETED",
                           "result": {"images": ["https://cdn2.apiframe.ai/images/nb1.png"]}})

    def fake_dl(url, timeout=None):
        return _resp(200, content=_PNG)

    with mock.patch("requests.post", side_effect=fake_post), \
         mock.patch("requests.get", side_effect=lambda url, headers=None, timeout=None:
                     fake_get(url) if "/jobs/" in url else fake_dl(url)):
        r = prov.generate("rainy Seoul street", str(out), negative_prompt="text, watermark", aspect="16:9")

    assert r["ok"] is True, r
    assert r["provider"] == "nanobanana2-apiframe"
    assert r["task_id"] == "job-nb-1"
    assert out.exists()

    submit = posts[0]
    assert submit["headers"]["X-API-Key"] == _FAKE_KEY
    assert submit["json"]["model"] == "nano-banana-2"
    assert submit["json"]["nanoBananaParams"]["aspect_ratio"] == "16:9"
    # Negative prompt folded as "Avoid: ..." (Gemini has no dedicated field)
    assert "Avoid: text, watermark" in submit["json"]["prompt"]
    assert "--no" not in submit["json"]["prompt"]  # that's Midjourney syntax, not this


def test_nb_failed_job_masks_key(tmp_path):
    prov = nb.ApiframeNanoBananaProvider(api_key=_FAKE_KEY)

    def fake_post(url, headers=None, json=None, timeout=None):
        return _resp(202, {"jobId": "t-fail", "status": "QUEUED"})

    def fake_get(url, headers=None, timeout=None):
        return _resp(200, {"status": "FAILED", "error": f"content policy violation (key={_FAKE_KEY})"})

    with mock.patch("requests.post", side_effect=fake_post), \
         mock.patch("requests.get", side_effect=fake_get):
        r = prov.generate("bad prompt", str(tmp_path / "x.png"))

    assert r["ok"] is False
    assert _FAKE_KEY not in r["error"]


def test_nb_retries_on_capacity_error_then_succeeds(tmp_path):
    prov = nb.ApiframeNanoBananaProvider(api_key=_FAKE_KEY)
    submit_calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        submit_calls.append(1)
        return _resp(202, {"jobId": f"job-{len(submit_calls)}", "status": "QUEUED"})

    def fake_get(url, headers=None, timeout=None):
        if len(submit_calls) == 1:
            return _resp(200, {"status": "FAILED", "error": "No available capacity"})
        return _resp(200, {"status": "COMPLETED", "result": {"images": ["https://cdn2.apiframe.ai/images/ok.png"]}})

    def fake_dl(url, timeout=None):
        return _resp(200, content=_PNG)

    with mock.patch("requests.post", side_effect=fake_post), \
         mock.patch("requests.get", side_effect=lambda url, headers=None, timeout=None:
                     fake_get(url) if "/jobs/" in url else fake_dl(url)):
        r = prov.generate("p", str(tmp_path / "x.png"))

    assert r["ok"] is True
    assert len(submit_calls) == 2


def test_nb_non_capacity_error_does_not_retry(tmp_path):
    prov = nb.ApiframeNanoBananaProvider(api_key=_FAKE_KEY)
    submit_calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        submit_calls.append(1)
        return _resp(401, {"error": "invalid key"})

    with mock.patch("requests.post", side_effect=fake_post):
        r = prov.generate("p", str(tmp_path / "x.png"))

    assert r["ok"] is False
    assert len(submit_calls) == 1


# ─── Factory routing ─────────────────────────────────────────────────────────

def test_factory_apiframe_nanobanana_without_key_returns_mock():
    prov = ip.get_image_provider(use_real=True, engine="apiframe_nanobanana")
    assert isinstance(prov, ip.MockImageGenProvider)


def test_factory_apiframe_nanobanana_with_key_returns_provider(monkeypatch):
    monkeypatch.setenv("APIFRAME_API_KEY", _FAKE_KEY)
    prov = ip.get_image_provider(use_real=True, engine="apiframe_nanobanana")
    assert prov.name == "nanobanana2-apiframe"
    assert prov.is_real is True


def test_factory_default_engine_still_gemini_backcompat():
    prov = ip.get_image_provider(use_real=False)
    assert isinstance(prov, ip.MockImageGenProvider)


def test_generate_images_passes_apiframe_nanobanana_engine(monkeypatch):
    seen = {}
    real_factory = ip.get_image_provider

    def spy(use_real=False, model=None, engine="gemini"):
        seen["engine"] = engine
        return real_factory(use_real=False)

    monkeypatch.setattr(ip, "get_image_provider", spy)
    sess = ss.create_session("kr", "rainy night", "CityPop", 1, "")
    prompts = [{"main_prompt": "p", "negative_prompt": "", "scene": "s",
                "country": "kr", "theme": "t"}]
    ss.generate_images(sess["session_id"], prompts, use_real=True, engine="apiframe_nanobanana")
    assert seen["engine"] == "apiframe_nanobanana"


# ─── Dependency check ────────────────────────────────────────────────────────

def test_nb_dependency_check_no_key():
    d = deps.check_apiframe_nanobanana_dependencies()
    assert d["ready"] is False
    assert "APIFRAME_API_KEY" in d["key_env_vars"]


def test_nb_dependency_check_with_key_never_exposes_value(monkeypatch):
    monkeypatch.setenv("APIFRAME_API_KEY", _FAKE_KEY)
    d = deps.check_apiframe_nanobanana_dependencies()
    assert d["ready"] is True
    assert _FAKE_KEY not in str(d)
