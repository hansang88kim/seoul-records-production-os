"""
tests/test_openai_image_provider.py — GPT Image 2 via OpenAI (v1.0.0-alpha.35).

Reuses the same OPENAI_API_KEY already connected for ChatGPT/lyrics — no
separate credential. Unlike Midjourney/Nano-Banana-2 via Apiframe, OpenAI's
Images API is SYNCHRONOUS: no job/poll cycle, the base64 image comes back
directly in the POST response.

NO real OpenAI calls — every network touch is mocked, and the factory
returns the mock whenever OPENAI_API_KEY is absent (always true in CI).
"""
from __future__ import annotations

import base64
import json
from unittest import mock

import pytest

import services.thumbnail.session_store as ss
from services.thumbnail import image_provider as ip
from services.thumbnail import image_gen_deps as deps
from services.thumbnail import openai_image_provider as oi


_FAKE_KEY = "sk-test-key-SECRET-9f8e7d"
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
_PNG_B64 = base64.b64encode(_PNG).decode("ascii")


@pytest.fixture(autouse=True)
def studio_tmp(monkeypatch, tmp_path):
    monkeypatch.setattr(ss, "_studio_root", lambda: tmp_path / "studio")
    for var in ip._API_KEY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(oi, "_RETRY_BACKOFF_SEC", (0, 0, 0))
    yield


def _resp(status_code=200, payload=None, text=None):
    r = mock.Mock()
    r.status_code = status_code
    r.text = text if text is not None else (json.dumps(payload) if payload is not None else "")
    r.json = mock.Mock(return_value=payload if payload is not None else {})
    return r


# ─── No key → clean failure, no network ──────────────────────────────────────

def test_no_key_returns_error_without_network():
    prov = oi.OpenAIGptImageProvider(api_key=None)
    with mock.patch("requests.post") as post:
        r = prov.generate("seoul night drive", "/tmp/never.png")
    assert r["ok"] is False
    assert "API key" in r["error"] or "OPENAI" in r["error"]
    post.assert_not_called()


# ─── Happy path (synchronous — single request, no polling) ──────────────────

def test_happy_path_writes_file(tmp_path):
    prov = oi.OpenAIGptImageProvider(api_key=_FAKE_KEY)
    out = tmp_path / "cand" / "c1_16x9.png"
    posts = []

    def fake_post(url, headers=None, json=None, timeout=None):
        posts.append({"url": url, "json": json, "headers": headers})
        return _resp(200, {"data": [{"b64_json": _PNG_B64}], "usage": {"total_tokens": 100}})

    with mock.patch("requests.post", side_effect=fake_post):
        r = prov.generate("rainy Seoul street", str(out), negative_prompt="text, watermark", aspect="16:9")

    assert r["ok"] is True, r
    assert r["provider"] == "gpt-image-2-openai"
    assert out.exists()

    submit = posts[0]
    assert submit["url"] == oi.OPENAI_IMAGES_URL
    assert submit["headers"]["Authorization"] == f"Bearer {_FAKE_KEY}"
    assert submit["json"]["model"] == "gpt-image-2"
    assert submit["json"]["size"] == "1536x1024"  # closest landscape size for 16:9
    assert "Avoid: text, watermark" in submit["json"]["prompt"]


def test_square_aspect_uses_1024_size(tmp_path):
    prov = oi.OpenAIGptImageProvider(api_key=_FAKE_KEY)
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["size"] = json["size"]
        return _resp(200, {"data": [{"b64_json": _PNG_B64}]})

    with mock.patch("requests.post", side_effect=fake_post):
        r = prov.generate("p", str(tmp_path / "o.png"), aspect="1:1")

    assert r["ok"] is True
    assert captured["size"] == "1024x1024"


def test_portrait_aspect_uses_portrait_size(tmp_path):
    prov = oi.OpenAIGptImageProvider(api_key=_FAKE_KEY)
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["size"] = json["size"]
        return _resp(200, {"data": [{"b64_json": _PNG_B64}]})

    with mock.patch("requests.post", side_effect=fake_post):
        prov.generate("p", str(tmp_path / "o.png"), aspect="9:16")

    assert captured["size"] == "1024x1536"


# ─── Failure paths ────────────────────────────────────────────────────────────

def test_org_verification_403_gives_clean_actionable_error(tmp_path):
    prov = oi.OpenAIGptImageProvider(api_key=_FAKE_KEY)
    with mock.patch("requests.post", return_value=_resp(403, {"error": "forbidden"})):
        r = prov.generate("p", str(tmp_path / "x.png"))
    assert r["ok"] is False
    assert "Organization Verification" in r["error"]
    assert _FAKE_KEY not in r["error"]


def test_401_no_key_leak(tmp_path):
    prov = oi.OpenAIGptImageProvider(api_key=_FAKE_KEY)
    with mock.patch("requests.post", return_value=_resp(401, {"error": f"invalid key {_FAKE_KEY}"})):
        r = prov.generate("p", str(tmp_path / "x.png"))
    assert r["ok"] is False
    assert "HTTP 401" in r["error"]
    assert _FAKE_KEY not in r["error"]


def test_retries_on_429_then_succeeds(tmp_path):
    prov = oi.OpenAIGptImageProvider(api_key=_FAKE_KEY)
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(1)
        if len(calls) == 1:
            return _resp(429, {"error": "rate limited"})
        return _resp(200, {"data": [{"b64_json": _PNG_B64}]})

    with mock.patch("requests.post", side_effect=fake_post):
        r = prov.generate("p", str(tmp_path / "x.png"))

    assert r["ok"] is True
    assert len(calls) == 2


def test_gives_up_after_max_retries(monkeypatch, tmp_path):
    monkeypatch.setenv("SEOUL_GPTIMAGE_RETRIES", "1")  # 2 total attempts
    prov = oi.OpenAIGptImageProvider(api_key=_FAKE_KEY)
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(1)
        return _resp(500, {"error": "server error"})

    with mock.patch("requests.post", side_effect=fake_post):
        r = prov.generate("p", str(tmp_path / "x.png"))

    assert r["ok"] is False
    assert len(calls) == 2


def test_400_content_policy_does_not_retry(tmp_path):
    prov = oi.OpenAIGptImageProvider(api_key=_FAKE_KEY)
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(1)
        return _resp(400, {"error": "content policy violation"})

    with mock.patch("requests.post", side_effect=fake_post):
        r = prov.generate("p", str(tmp_path / "x.png"))

    assert r["ok"] is False
    assert len(calls) == 1  # 400 is not retryable


def test_no_negative_prompt_no_avoid_text(tmp_path):
    prov = oi.OpenAIGptImageProvider(api_key=_FAKE_KEY)
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["prompt"] = json["prompt"]
        return _resp(200, {"data": [{"b64_json": _PNG_B64}]})

    with mock.patch("requests.post", side_effect=fake_post):
        prov.generate("clean prompt", str(tmp_path / "o.png"))

    assert "Avoid" not in captured["prompt"]


# ─── Factory routing ─────────────────────────────────────────────────────────

def test_factory_gpt_image_without_key_returns_mock():
    prov = ip.get_image_provider(use_real=True, engine="gpt_image")
    assert isinstance(prov, ip.MockImageGenProvider)


def test_factory_gpt_image_with_key_returns_provider(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", _FAKE_KEY)
    prov = ip.get_image_provider(use_real=True, engine="gpt_image")
    assert prov.name == "gpt-image-2-openai"
    assert prov.is_real is True


def test_generate_images_passes_gpt_image_engine(monkeypatch):
    seen = {}
    real_factory = ip.get_image_provider

    def spy(use_real=False, model=None, engine="gemini"):
        seen["engine"] = engine
        return real_factory(use_real=False)

    monkeypatch.setattr(ip, "get_image_provider", spy)
    sess = ss.create_session("kr", "rainy night", "CityPop", 1, "")
    prompts = [{"main_prompt": "p", "negative_prompt": "", "scene": "s",
                "country": "kr", "theme": "t"}]
    ss.generate_images(sess["session_id"], prompts, use_real=True, engine="gpt_image")
    assert seen["engine"] == "gpt_image"


# ─── Dependency check ────────────────────────────────────────────────────────

def test_dependency_check_no_key():
    d = deps.check_gpt_image_dependencies()
    assert d["ready"] is False
    assert "OPENAI_API_KEY" in d["key_env_vars"]


def test_dependency_check_with_key_never_exposes_value(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", _FAKE_KEY)
    d = deps.check_gpt_image_dependencies()
    assert d["ready"] is True
    assert _FAKE_KEY not in str(d)


def test_get_openai_key_reads_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "  padded_key  ")
    assert oi.get_openai_key() == "padded_key"
    monkeypatch.delenv("OPENAI_API_KEY")
    assert oi.get_openai_key() is None


def test_closest_size_mapping():
    assert oi._closest_size("16:9") == "1536x1024"
    assert oi._closest_size("1:1") == "1024x1024"
    assert oi._closest_size("9:16") == "1024x1536"
    assert oi._closest_size("garbage") == "1024x1024"  # safe fallback
