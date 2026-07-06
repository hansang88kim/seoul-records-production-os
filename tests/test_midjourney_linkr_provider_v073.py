"""
tests/test_midjourney_linkr_provider_v073.py — Midjourney via LinkrAPI
(v1.0.0-alpha.73).

Covers services/thumbnail/midjourney_linkr_provider.py:
  * prompt shaping (--ar / --no), U1..U4 index mapping
  * lenient response parsing (task_id / status / image_url across casings)
  * no-key → clean failure with NO network
  * happy path: imagine → fetch(pending→completed) → action U1 →
    fetch(processing→completed) → download, file written, key never leaked
  * 3-way status branch: failed/error → immediate stop; moderated → clear
    policy message; pending/processing/queued keep polling
  * staged timeouts (imagine vs upscale) surface a bounded error
  * inline-completion action path (action returns the image directly)
  * factory routing: get_image_provider(engine="midjourney_linkr"/"linkrapi")
  * the API key is NEVER present in any surfaced error string

NO real LinkrAPI calls — every requests.get/post is mocked, and the factory
returns the mock whenever LINKRAPI_API_KEY is absent (always true in CI).
"""
from __future__ import annotations

import json
from unittest import mock

import pytest

from services.thumbnail import image_provider as ip
from services.thumbnail import midjourney_linkr_provider as lk


_FAKE_KEY = "lkr_test_key_SECRET_9f8e7d"
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
_IMG_URL = "https://cdn.discordapp.com/attachments/x/y/final.png"


@pytest.fixture(autouse=True)
def _fast_and_clean(monkeypatch):
    """Zero poll interval (no real sleeping) and no real key in the env."""
    monkeypatch.setattr(lk, "_poll_interval", lambda: 0)
    monkeypatch.delenv("LINKRAPI_API_KEY", raising=False)
    monkeypatch.delenv("LINKRAPI_BASE_URL", raising=False)
    yield


def _resp(status_code=200, payload=None, content=b""):
    r = mock.Mock()
    r.status_code = status_code
    r.text = json.dumps(payload) if payload is not None else ""
    r.json = mock.Mock(return_value=payload if payload is not None else {})
    r.content = content
    return r


# ─── Pure helpers ────────────────────────────────────────────────────────────

def test_build_prompt_appends_ar_and_no():
    assert lk._build_prompt("rainy seoul", "text, watermark", "16:9") == \
        "rainy seoul --ar 16:9 --no text, watermark"
    assert lk._build_prompt("cover", "", "1:1") == "cover --ar 1:1"
    assert lk._build_prompt("x", "  ", "9:16") == "x --ar 9:16"


def test_upscale_action_maps_index_to_u1_u4_clamped():
    assert lk._upscale_action_for_index(0) == "U1"
    assert lk._upscale_action_for_index(1) == "U2"
    assert lk._upscale_action_for_index(3) == "U4"
    assert lk._upscale_action_for_index(9) == "U4"   # clamp high
    assert lk._upscale_action_for_index(-5) == "U1"  # clamp low


def test_extract_task_id_across_casings_and_nesting():
    assert lk._extract_task_id({"task_id": "a"}) == "a"
    assert lk._extract_task_id({"taskId": "b"}) == "b"
    assert lk._extract_task_id({"id": "c"}) == "c"
    assert lk._extract_task_id({"data": {"task_id": "d"}}) == "d"
    assert lk._extract_task_id({}) is None


def test_extract_status_lowercases_and_nests():
    assert lk._extract_status({"status": "Completed"}) == "completed"
    assert lk._extract_status({"state": "PROCESSING"}) == "processing"
    assert lk._extract_status({"result": {"status": "Failed"}}) == "failed"
    assert lk._extract_status({}) == ""


def test_extract_image_url_across_shapes():
    assert lk._extract_image_url({"image_url": _IMG_URL}) == _IMG_URL
    assert lk._extract_image_url({"imageUrl": _IMG_URL}) == _IMG_URL
    assert lk._extract_image_url({"images": [_IMG_URL]}) == _IMG_URL
    assert lk._extract_image_url({"result": {"images": [{"url": _IMG_URL}]}}) == _IMG_URL
    assert lk._extract_image_url({"nope": "not-a-url"}) is None


# ─── No key → clean failure, no network ──────────────────────────────────────

def test_no_key_returns_error_without_network(tmp_path):
    prov = lk.MidjourneyLinkrProvider(api_key=None)
    with mock.patch("requests.post") as post, mock.patch("requests.get") as get:
        r = prov.generate("seoul night", str(tmp_path / "never.png"))
    assert r["ok"] is False
    assert "LINKRAPI" in r["error"] or "API key" in r["error"]
    post.assert_not_called()
    get.assert_not_called()


# ─── Happy path ──────────────────────────────────────────────────────────────

def test_happy_path_imagine_poll_upscale_poll_download(tmp_path):
    prov = lk.MidjourneyLinkrProvider(api_key=_FAKE_KEY)
    out = tmp_path / "cand.png"

    posts = [
        _resp(200, {"task_id": "tsk_grid"}),        # imagine
        _resp(200, {"task_id": "tsk_upscale"}),     # action U1
    ]
    gets = [
        _resp(200, {"status": "pending"}),                         # grid poll 1
        _resp(200, {"status": "completed", "actions": ["U1"]}),    # grid poll 2
        _resp(200, {"status": "processing"}),                      # upscale poll 1
        _resp(200, {"status": "completed", "image_url": _IMG_URL}),# upscale poll 2
        _resp(200, content=_PNG),                                  # download
    ]
    with mock.patch("requests.post", side_effect=posts) as mpost, \
         mock.patch("requests.get", side_effect=gets):
        r = prov.generate("rainy seoul --citypop", str(out),
                          negative_prompt="text, watermark", index=0, aspect="16:9")

    assert r["ok"] is True, r
    assert r["task_id"] == "tsk_grid"
    assert out.exists()
    # imagine body carried the shaped prompt with --ar and --no
    imagine_body = mpost.call_args_list[0].kwargs["json"]
    assert "--ar 16:9" in imagine_body["prompt"]
    assert "--no text, watermark" in imagine_body["prompt"]
    # action body carried the grid task_id and U1
    action_body = mpost.call_args_list[1].kwargs["json"]
    assert action_body == {"task_id": "tsk_grid", "action": "U1"}


def test_index_selects_u2(tmp_path):
    prov = lk.MidjourneyLinkrProvider(api_key=_FAKE_KEY)
    posts = [_resp(200, {"task_id": "g"}), _resp(200, {"task_id": "u"})]
    gets = [
        _resp(200, {"status": "completed"}),
        _resp(200, {"status": "completed", "image_url": _IMG_URL}),
        _resp(200, content=_PNG),
    ]
    with mock.patch("requests.post", side_effect=posts) as mpost, \
         mock.patch("requests.get", side_effect=gets):
        prov.generate("x", str(tmp_path / "o.png"), index=1)
    assert mpost.call_args_list[1].kwargs["json"]["action"] == "U2"


# ─── 3-way status branch ─────────────────────────────────────────────────────

def test_failed_status_stops_immediately(tmp_path):
    prov = lk.MidjourneyLinkrProvider(api_key=_FAKE_KEY)
    posts = [_resp(200, {"task_id": "g"})]
    gets = [_resp(200, {"status": "failed", "error": "banana slipped"})]
    with mock.patch("requests.post", side_effect=posts), \
         mock.patch("requests.get", side_effect=gets):
        r = prov.generate("x", str(tmp_path / "o.png"))
    assert r["ok"] is False
    assert "failed" in r["error"].lower()
    assert "banana slipped" in r["error"]


def test_moderated_status_gives_clear_policy_message(tmp_path):
    prov = lk.MidjourneyLinkrProvider(api_key=_FAKE_KEY)
    posts = [_resp(200, {"task_id": "g"})]
    gets = [_resp(200, {"status": "moderated", "message": "banned word"})]
    with mock.patch("requests.post", side_effect=posts), \
         mock.patch("requests.get", side_effect=gets):
        r = prov.generate("x", str(tmp_path / "o.png"))
    assert r["ok"] is False
    assert "정책 위반" in r["error"]


def test_pending_processing_queued_keep_polling_then_complete(tmp_path):
    prov = lk.MidjourneyLinkrProvider(api_key=_FAKE_KEY)
    posts = [_resp(200, {"task_id": "g"}), _resp(200, {"task_id": "u"})]
    gets = [
        _resp(200, {"status": "queued"}),
        _resp(200, {"status": "processing"}),
        _resp(200, {"status": "pending"}),
        _resp(200, {"status": "done"}),                             # grid complete (broad marker)
        _resp(200, {"status": "success", "image_url": _IMG_URL}),   # upscale complete (broad marker)
        _resp(200, content=_PNG),
    ]
    with mock.patch("requests.post", side_effect=posts), \
         mock.patch("requests.get", side_effect=gets):
        r = prov.generate("x", str(tmp_path / "o.png"))
    assert r["ok"] is True
    assert (tmp_path / "o.png").exists()


# ─── Timeout (staged) ────────────────────────────────────────────────────────

def test_imagine_timeout_is_bounded_and_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(lk, "_imagine_timeout", lambda: 0)  # deadline immediately hit
    prov = lk.MidjourneyLinkrProvider(api_key=_FAKE_KEY)
    posts = [_resp(200, {"task_id": "g"})]
    gets = [_resp(200, {"status": "processing"})]
    with mock.patch("requests.post", side_effect=posts), \
         mock.patch("requests.get", side_effect=gets):
        r = prov.generate("x", str(tmp_path / "o.png"))
    assert r["ok"] is False
    assert "imagine timed out" in r["error"]


def test_upscale_timeout_distinct_from_imagine(tmp_path, monkeypatch):
    monkeypatch.setattr(lk, "_upscale_timeout", lambda: 0)
    prov = lk.MidjourneyLinkrProvider(api_key=_FAKE_KEY)
    posts = [_resp(200, {"task_id": "g"}), _resp(200, {"task_id": "u"})]
    gets = [
        _resp(200, {"status": "completed"}),   # grid done
        _resp(200, {"status": "processing"}),  # upscale never completes → timeout
    ]
    with mock.patch("requests.post", side_effect=posts), \
         mock.patch("requests.get", side_effect=gets):
        r = prov.generate("x", str(tmp_path / "o.png"))
    assert r["ok"] is False
    assert "upscale timed out" in r["error"]


# ─── Inline-completion action path ───────────────────────────────────────────

def test_action_inline_completion_skips_second_poll(tmp_path):
    """Some proxies complete the upscale inline in the /action response."""
    prov = lk.MidjourneyLinkrProvider(api_key=_FAKE_KEY)
    posts = [
        _resp(200, {"task_id": "g"}),
        _resp(200, {"image_url": _IMG_URL}),  # action returns image directly, no new task_id
    ]
    gets = [
        _resp(200, {"status": "completed"}),  # grid poll
        _resp(200, content=_PNG),             # download (no upscale poll)
    ]
    with mock.patch("requests.post", side_effect=posts), \
         mock.patch("requests.get", side_effect=gets) as mget:
        r = prov.generate("x", str(tmp_path / "o.png"))
    assert r["ok"] is True
    # exactly 2 GETs: one grid poll + one download (no upscale poll)
    assert mget.call_count == 2


# ─── Key never leaked ────────────────────────────────────────────────────────

def test_api_key_never_in_error_text(tmp_path):
    prov = lk.MidjourneyLinkrProvider(api_key=_FAKE_KEY)
    # imagine returns an HTTP error whose body echoes the key (simulate a leak risk)
    posts = [_resp(400, {"error": f"bad key {_FAKE_KEY}"})]
    with mock.patch("requests.post", side_effect=posts), \
         mock.patch("requests.get"):
        r = prov.generate("x", str(tmp_path / "o.png"))
    assert r["ok"] is False
    assert _FAKE_KEY not in r["error"]
    assert "***" in r["error"]


def test_auth_header_uses_bearer(tmp_path):
    prov = lk.MidjourneyLinkrProvider(api_key=_FAKE_KEY)
    assert prov._headers()["Authorization"] == f"Bearer {_FAKE_KEY}"


# ─── Factory routing ─────────────────────────────────────────────────────────

def test_factory_midjourney_linkr_no_key_falls_back_to_mock(monkeypatch):
    monkeypatch.delenv("LINKRAPI_API_KEY", raising=False)
    p = ip.get_image_provider(use_real=True, engine="midjourney_linkr")
    assert p.name == "mock"


def test_factory_midjourney_linkr_with_key(monkeypatch):
    monkeypatch.setenv("LINKRAPI_API_KEY", _FAKE_KEY)
    p = ip.get_image_provider(use_real=True, engine="midjourney_linkr")
    assert p.name == "midjourney-linkr"
    # alias "linkrapi" routes the same way
    assert ip.get_image_provider(use_real=True, engine="linkrapi").name == "midjourney-linkr"


def test_factory_use_real_false_is_always_mock(monkeypatch):
    monkeypatch.setenv("LINKRAPI_API_KEY", _FAKE_KEY)
    assert ip.get_image_provider(use_real=False, engine="midjourney_linkr").name == "mock"
