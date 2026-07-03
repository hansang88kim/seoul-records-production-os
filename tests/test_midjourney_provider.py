"""
tests/test_midjourney_provider.py — Midjourney via Apiframe (v1.0.0-alpha.30).

Covers the new Midjourney image engine:
  * provider fails cleanly without an API key (no network)
  * imagine → fetch(processing) → fetch(image_urls) happy path, files written
  * --no translation of the negative prompt; aspect_ratio in the payload
  * failed task and timeout surface clean errors WITHOUT the API key
  * factory routing: get_image_provider(engine="midjourney") — key/no-key
  * generate_images(engine=...) passes the engine through to the factory
  * dependency check reports readiness WITHOUT exposing the key

NO real Apiframe calls — every network touch is mocked, and the factory
returns the mock whenever APIFRAME_API_KEY is absent (always true in CI).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

import pytest

import services.thumbnail.session_store as ss
from services.thumbnail import image_provider as ip
from services.thumbnail import image_gen_deps as deps
from services.thumbnail import midjourney_provider as mj


_FAKE_KEY = "apiframe_test_key_SECRET_9f8e7d"
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24  # minimal PNG-magic payload


@pytest.fixture(autouse=True)
def studio_tmp(monkeypatch, tmp_path):
    """Redirect the studio root to a temp folder and clear any real keys."""
    monkeypatch.setattr(ss, "_studio_root", lambda: tmp_path / "studio")
    for var in ip._API_KEY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("APIFRAME_API_KEY", raising=False)
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


# ─── Happy path: imagine → processing → finished ─────────────────────────────

def test_mj_happy_path_polls_and_downloads(monkeypatch, tmp_path):
    monkeypatch.setattr(mj, "_POLL_INTERVAL_SEC", 0)
    prov = mj.MidjourneyApiframeProvider(api_key=_FAKE_KEY)
    out = tmp_path / "cand" / "c1_16x9.png"

    posts = []

    def fake_post(url, headers=None, json=None, timeout=None):
        posts.append({"url": url, "json": json, "headers": headers})
        if url.endswith("/imagine"):
            return _resp(200, {"task_id": "task-abc-123"})
        # fetch: first call processing, then finished with 4 urls
        n_fetch = sum(1 for p in posts if p["url"].endswith("/fetch"))
        if n_fetch == 1:
            return _resp(200, {"task_id": "task-abc-123", "status": "processing",
                               "percentage": "40"})
        return _resp(200, {
            "task_id": "task-abc-123", "task_type": "imagine",
            "original_image_url": "https://cdn.example/grid.png",
            "image_urls": [f"https://cdn.example/img{i}.png" for i in range(1, 5)],
        })

    def fake_get(url, timeout=None):
        return _resp(200, content=_PNG)

    with mock.patch("requests.post", side_effect=fake_post), \
         mock.patch("requests.get", side_effect=fake_get):
        r = prov.generate("neon rainy Seoul street, 1990s anime",
                          str(out), negative_prompt="text, watermark",
                          aspect="16:9")

    assert r["ok"] is True, r
    assert r["provider"] == "midjourney-apiframe"
    assert r["task_id"] == "task-abc-123"
    assert out.exists()

    # Imagine payload: aspect_ratio field + --no negatives in the prompt
    imagine = next(p for p in posts if p["url"].endswith("/imagine"))
    assert imagine["json"]["aspect_ratio"] == "16:9"
    assert "--no text, watermark" in imagine["json"]["prompt"]
    assert imagine["headers"]["Authorization"] == _FAKE_KEY

    # The other 3 quadrants saved as _alt2.._alt4 next to the primary
    for n in (2, 3, 4):
        assert out.with_name(f"c1_16x9_alt{n}.png").exists()


def test_mj_no_negative_prompt_has_no_no_flag(monkeypatch, tmp_path):
    monkeypatch.setattr(mj, "_POLL_INTERVAL_SEC", 0)
    prov = mj.MidjourneyApiframeProvider(api_key=_FAKE_KEY)
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        if url.endswith("/imagine"):
            captured["prompt"] = json["prompt"]
            return _resp(200, {"task_id": "t1"})
        return _resp(200, {"image_urls": ["https://cdn.example/1.png"]})

    with mock.patch("requests.post", side_effect=fake_post), \
         mock.patch("requests.get", return_value=_resp(200, content=_PNG)):
        r = prov.generate("clean prompt", str(tmp_path / "o.png"), aspect="1:1")

    assert r["ok"] is True
    assert "--no" not in captured["prompt"]


# ─── Failure paths ────────────────────────────────────────────────────────────

def test_mj_failed_task_surfaces_error_without_key(monkeypatch, tmp_path):
    monkeypatch.setattr(mj, "_POLL_INTERVAL_SEC", 0)
    prov = mj.MidjourneyApiframeProvider(api_key=_FAKE_KEY)

    def fake_post(url, headers=None, json=None, timeout=None):
        if url.endswith("/imagine"):
            return _resp(200, {"task_id": "t-fail"})
        return _resp(200, {"task_id": "t-fail", "status": "failed",
                           "error": f"banned prompt (key={_FAKE_KEY})"})

    with mock.patch("requests.post", side_effect=fake_post):
        r = prov.generate("bad", str(tmp_path / "x.png"))

    assert r["ok"] is False
    assert "failed" in r["error"]
    assert _FAKE_KEY not in r["error"]  # key must be masked


def test_mj_imagine_http_error_no_key_leak(tmp_path):
    prov = mj.MidjourneyApiframeProvider(api_key=_FAKE_KEY)

    def fake_post(url, headers=None, json=None, timeout=None):
        return _resp(401, {"errors": [{"msg": f"invalid key {_FAKE_KEY}"}]})

    with mock.patch("requests.post", side_effect=fake_post):
        r = prov.generate("p", str(tmp_path / "x.png"))

    assert r["ok"] is False
    assert "HTTP 401" in r["error"]
    assert _FAKE_KEY not in r["error"]


def test_mj_timeout_returns_clean_error(monkeypatch, tmp_path):
    monkeypatch.setattr(mj, "_POLL_INTERVAL_SEC", 0)
    monkeypatch.setenv("SEOUL_MJ_TIMEOUT", "30")  # min clamp is 30

    # Freeze-step time: each time.time() call advances past the deadline fast.
    ticks = iter([0, 0, 100, 100, 100])
    monkeypatch.setattr(mj.time, "time", lambda: next(ticks, 100))

    prov = mj.MidjourneyApiframeProvider(api_key=_FAKE_KEY)

    def fake_post(url, headers=None, json=None, timeout=None):
        if url.endswith("/imagine"):
            return _resp(200, {"task_id": "t-slow"})
        return _resp(200, {"status": "processing", "percentage": "10"})

    with mock.patch("requests.post", side_effect=fake_post):
        r = prov.generate("slow", str(tmp_path / "x.png"))

    assert r["ok"] is False
    assert "timed out" in r["error"]


def test_mj_imagine_no_task_id_is_error(tmp_path):
    prov = mj.MidjourneyApiframeProvider(api_key=_FAKE_KEY)
    with mock.patch("requests.post", return_value=_resp(200, {"message": "queued?"})):
        r = prov.generate("p", str(tmp_path / "x.png"))
    assert r["ok"] is False
    assert "task_id" in r["error"]


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

def test_mj_dependency_check_no_key(monkeypatch):
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
