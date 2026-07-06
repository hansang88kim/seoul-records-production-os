"""
tests/test_midjourney_linkr_provider_v073.py — Midjourney via LinkrAPI
(v1.0.0-alpha.73).

Covers services/thumbnail/midjourney_linkr_provider.py:
  * prompt shaping (--ar / --no), U1..U4 index mapping
  * lenient response parsing (task_id / status / image_url across casings)
  * no-key → clean failure with NO network
  * happy path (v1.0.0-alpha.75, NO upscale): imagine → fetch(starting→
    completed) → download grid quadrant, file written, key never leaked
  * 3-way status branch: failed/error → immediate stop; moderated → clear
    policy message; pending/processing/queued keep polling
  * imagine timeout surfaces a bounded error
  * [LINKR-DIAG] raw-response dump masks the key
  * no /action endpoint is ever called (upscale removed)
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

def test_build_prompt_appends_ar_style_and_no(monkeypatch):
    # Pin style params so the assertion is deterministic.
    monkeypatch.setenv("SEOUL_MJ_LINKR_STYLE_PARAMS", "--style raw --stylize 120")
    assert lk._build_prompt("rainy seoul", "text, watermark", "16:9") == \
        "rainy seoul --ar 16:9 --style raw --stylize 120 --no text, watermark"
    assert lk._build_prompt("cover", "", "1:1") == "cover --ar 1:1 --style raw --stylize 120"
    assert lk._build_prompt("x", "  ", "9:16") == "x --ar 9:16 --style raw --stylize 120"


def test_build_prompt_style_params_disablable(monkeypatch):
    monkeypatch.setenv("SEOUL_MJ_LINKR_STYLE_PARAMS", "")
    assert lk._build_prompt("rainy seoul", "text", "16:9") == "rainy seoul --ar 16:9 --no text"


def test_style_params_default_is_citypop_stylize(monkeypatch):
    monkeypatch.delenv("SEOUL_MJ_LINKR_STYLE_PARAMS", raising=False)
    sp = lk._mj_style_params()
    assert "--style raw" in sp and "--stylize" in sp


def test_to_mj_no_strips_no_prefix_and_dedups():
    # The exact shape prompt_generator.NEGATIVE_PROMPT produces.
    src = "no text, no letters, no words, no watermark, no logo, no logo"
    assert lk._to_mj_no(src) == "text, letters, words, watermark, logo"
    assert lk._to_mj_no("not cartoon, no text") == "cartoon, text"
    assert lk._to_mj_no("") == ""
    # already-clean terms (no "no " prefix) pass through unchanged
    assert lk._to_mj_no("text, watermark") == "text, watermark"


def test_build_prompt_converts_natural_language_negatives(monkeypatch):
    monkeypatch.setenv("SEOUL_MJ_LINKR_STYLE_PARAMS", "")
    full = lk._build_prompt("seoul night", "no text, no letters, no watermark, no logo", "16:9")
    # never double-negate: no "--no no ..." in the output
    assert "--no no " not in full
    assert full.endswith("--no text, letters, watermark, logo")


def test_extract_grid_images_returns_quadrant_urls():
    # v1.0.0-alpha.75: upscale removed — we use the pre-split grid quadrants.
    data = {"images": [f"{_IMG_URL}?{i}" for i in range(4)], "grid_url": "g"}
    assert lk._extract_grid_images(data) == [f"{_IMG_URL}?{i}" for i in range(4)]
    assert lk._extract_grid_images({}) == []


def test_diag_dump_masks_key_and_logs(caplog):
    import logging
    with caplog.at_level(logging.WARNING):
        lk._diag_dump("fetch poll", {"status": "completed", "note": _FAKE_KEY}, _FAKE_KEY)
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "[LINKR-DIAG]" in joined
    assert "fetch poll" in joined and '"status": "completed"' in joined
    assert _FAKE_KEY not in joined  # key masked
    assert "***" in joined


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


# ─── Happy path (v1.0.0-alpha.75: imagine → poll → download, NO upscale) ─────

def test_happy_path_imagine_poll_download_no_action(tmp_path):
    prov = lk.MidjourneyLinkrProvider(api_key=_FAKE_KEY)
    out = tmp_path / "cand.png"
    quad = [f"https://cdn.linkrapi.com/g_{i}.png" for i in range(1, 5)]

    posts = [_resp(200, {"status": "SUCCESS", "task_id": "tsk_grid"})]  # imagine ONLY
    gets = [
        _resp(200, {"status": "starting"}),                        # grid poll 1
        _resp(200, {"status": "completed", "images": quad}),       # grid poll 2 (done)
        _resp(200, content=_PNG),                                  # download images[0]
    ]
    with mock.patch("requests.post", side_effect=posts) as mpost, \
         mock.patch("requests.get", side_effect=gets):
        r = prov.generate("rainy seoul --citypop", str(out),
                          negative_prompt="text, watermark", index=0, aspect="16:9")

    assert r["ok"] is True, r
    assert r["task_id"] == "tsk_grid"
    assert out.exists()
    imagine_body = mpost.call_args_list[0].kwargs["json"]
    assert "--ar 16:9" in imagine_body["prompt"]
    assert "--no text, watermark" in imagine_body["prompt"]
    # NO /action POST at all — upscale removed.
    assert mpost.call_count == 1
    assert not any("/action" in str(c.args) for c in mpost.call_args_list)


def test_index_selects_second_grid_quadrant(tmp_path):
    prov = lk.MidjourneyLinkrProvider(api_key=_FAKE_KEY)
    quad = ["https://cdn/x_1.png", "https://cdn/x_2.png", "https://cdn/x_3.png", "https://cdn/x_4.png"]
    posts = [_resp(200, {"task_id": "g"})]
    gets = [
        _resp(200, {"status": "completed", "images": quad}),
        _resp(200, content=_PNG),
    ]
    with mock.patch("requests.post", side_effect=posts), \
         mock.patch("requests.get", side_effect=gets) as mget:
        prov.generate("x", str(tmp_path / "o.png"), index=1)
    # the download GET (2nd get) fetched quadrant index 1
    assert mget.call_args_list[1].args[0] == "https://cdn/x_2.png"


def test_uses_top_level_image_url_when_no_images_array(tmp_path):
    """Completed grid with only image_url (no images[]) → download it."""
    prov = lk.MidjourneyLinkrProvider(api_key=_FAKE_KEY)
    posts = [_resp(200, {"task_id": "g"})]
    gets = [
        _resp(200, {"status": "completed", "image_url": _IMG_URL}),  # no images[]
        _resp(200, content=_PNG),
    ]
    with mock.patch("requests.post", side_effect=posts), \
         mock.patch("requests.get", side_effect=gets) as mget:
        r = prov.generate("x", str(tmp_path / "o.png"))
    assert r["ok"] is True
    assert mget.call_args_list[1].args[0] == _IMG_URL


def test_completed_but_no_image_url_fails_cleanly(tmp_path):
    prov = lk.MidjourneyLinkrProvider(api_key=_FAKE_KEY)
    posts = [_resp(200, {"task_id": "g"})]
    gets = [_resp(200, {"status": "completed"})]  # no images, no image_url
    with mock.patch("requests.post", side_effect=posts), \
         mock.patch("requests.get", side_effect=gets):
        r = prov.generate("x", str(tmp_path / "o.png"))
    assert r["ok"] is False
    assert "이미지 URL" in r["error"]


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


_SUBSCRIBE_BANNER = (
    'Midjourney: {"type": "rich", "title": "Thank you for subscribing to Midjourney!", '
    '"description": "You are now subscribed to the Basic plan..."}'
)


def test_subscription_banner_is_retried_then_succeeds(tmp_path, monkeypatch):
    """The one-time 'Thank you for subscribing' banner (status=failed) must be
    treated as transient and retried — the second cycle produces a real image."""
    monkeypatch.setattr(lk, "_transient_retries", lambda: 2)
    monkeypatch.setattr(lk, "_TRANSIENT_BACKOFF_SEC", (0, 0, 0))
    prov = lk.MidjourneyLinkrProvider(api_key=_FAKE_KEY)

    posts = [
        _resp(200, {"task_id": "g1"}),   # attempt 1 imagine
        _resp(200, {"task_id": "g2"}),   # attempt 2 imagine
    ]
    gets = [
        _resp(200, {"status": "failed", "error": _SUBSCRIBE_BANNER}),   # attempt 1 grid → transient
        _resp(200, {"status": "completed", "image_url": _IMG_URL}),     # attempt 2 grid done
        _resp(200, content=_PNG),                                       # download
    ]
    with mock.patch("requests.post", side_effect=posts), \
         mock.patch("requests.get", side_effect=gets):
        r = prov.generate("seoul", str(tmp_path / "o.png"))
    assert r["ok"] is True, r
    assert (tmp_path / "o.png").exists()


def test_subscription_banner_exhausted_gives_onboarding_hint(tmp_path, monkeypatch):
    monkeypatch.setattr(lk, "_transient_retries", lambda: 1)  # 2 total attempts
    monkeypatch.setattr(lk, "_TRANSIENT_BACKOFF_SEC", (0, 0, 0))
    prov = lk.MidjourneyLinkrProvider(api_key=_FAKE_KEY)
    posts = [_resp(200, {"task_id": "g1"}), _resp(200, {"task_id": "g2"})]
    gets = [
        _resp(200, {"status": "failed", "error": _SUBSCRIBE_BANNER}),
        _resp(200, {"status": "failed", "error": _SUBSCRIBE_BANNER}),
    ]
    with mock.patch("requests.post", side_effect=posts), \
         mock.patch("requests.get", side_effect=gets):
        r = prov.generate("seoul", str(tmp_path / "o.png"))
    assert r["ok"] is False
    assert "Discord" in r["error"] and "/imagine" in r["error"]


def test_is_transient_failure_detection():
    assert lk._is_transient_failure("Thank you for subscribing to Midjourney!")
    assert lk._is_transient_failure("...you are now subscribed to the Basic plan")
    assert not lk._is_transient_failure("banana slipped on the floor")


def test_hard_failure_is_not_retried(tmp_path, monkeypatch):
    """A genuine failure (not the onboarding banner) must NOT be retried."""
    monkeypatch.setattr(lk, "_transient_retries", lambda: 3)
    prov = lk.MidjourneyLinkrProvider(api_key=_FAKE_KEY)
    posts = [_resp(200, {"task_id": "g1"})]
    gets = [_resp(200, {"status": "failed", "error": "internal error 500"})]
    with mock.patch("requests.post", side_effect=posts) as mpost, \
         mock.patch("requests.get", side_effect=gets):
        r = prov.generate("seoul", str(tmp_path / "o.png"))
    assert r["ok"] is False
    assert "internal error 500" in r["error"]
    # only ONE imagine POST — no retry on a hard failure
    assert mpost.call_count == 1


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
    posts = [_resp(200, {"task_id": "g"})]
    gets = [
        _resp(200, {"status": "queued"}),
        _resp(200, {"status": "processing"}),
        _resp(200, {"status": "pending"}),
        _resp(200, {"status": "done", "image_url": _IMG_URL}),  # complete (broad marker)
        _resp(200, content=_PNG),
    ]
    with mock.patch("requests.post", side_effect=posts), \
         mock.patch("requests.get", side_effect=gets):
        r = prov.generate("x", str(tmp_path / "o.png"))
    assert r["ok"] is True
    assert (tmp_path / "o.png").exists()


# ─── Timeout ─────────────────────────────────────────────────────────────────

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


# ─── No /action endpoint is ever called (upscale removed) ───────────────────

def test_no_action_endpoint_is_ever_called(tmp_path):
    prov = lk.MidjourneyLinkrProvider(api_key=_FAKE_KEY)
    quad = ["https://cdn/x_1.png", "https://cdn/x_2.png"]
    posts = [_resp(200, {"task_id": "g"})]
    gets = [_resp(200, {"status": "completed", "images": quad}), _resp(200, content=_PNG)]
    with mock.patch("requests.post", side_effect=posts) as mpost, \
         mock.patch("requests.get", side_effect=gets) as mget:
        prov.generate("x", str(tmp_path / "o.png"))
    all_urls = [str(c.args[0]) for c in mpost.call_args_list] + [str(c.args[0]) for c in mget.call_args_list]
    assert not any("/action" in u for u in all_urls)


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


# ─── UI + credential wiring (v1.0.0-alpha.73 commit 2) ──────────────────────

def test_deps_helper_reports_readiness_without_exposing_key(monkeypatch):
    from services.thumbnail.image_gen_deps import check_midjourney_linkr_dependencies
    monkeypatch.delenv("LINKRAPI_API_KEY", raising=False)
    d = check_midjourney_linkr_dependencies()
    assert d["ready"] is False and d["api_key_present"] is False
    monkeypatch.setenv("LINKRAPI_API_KEY", _FAKE_KEY)
    d = check_midjourney_linkr_dependencies()
    assert d["ready"] is True
    assert d["key_env_vars"] == ["LINKRAPI_API_KEY"]
    # the key VALUE must never appear anywhere in the report
    assert _FAKE_KEY not in json.dumps(d)


def test_verify_linkrapi_key_shape_checks_without_network():
    from services.thumbnail.midjourney_linkr_provider import verify_linkrapi_key
    with mock.patch("requests.get") as get:
        ok_empty, _ = verify_linkrapi_key("")
        ok_wrong, _ = verify_linkrapi_key("afk_not_a_linkr_key")
    assert ok_empty is False and ok_wrong is False
    get.assert_not_called()  # both rejected before any network call


def test_thumbnail_studio_ui_exposes_linkrapi_engine():
    from pathlib import Path
    src = Path("app/tabs/thumbnail_studio.py").read_text(encoding="utf-8")
    assert "Midjourney (LinkrAPI)" in src
    assert '"key": "midjourney_linkr"' in src
    assert "check_midjourney_linkr_dependencies" in src
    assert "1~3분" in src  # slow-generation notice


def test_sidebar_has_linkrapi_credential_field():
    from pathlib import Path
    src = Path("app/main.py").read_text(encoding="utf-8")
    assert "LINKRAPI_API_KEY" in src
    assert "_verify_linkrapi" in src
    assert "verify_linkrapi_key" in src
