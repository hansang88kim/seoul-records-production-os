"""
tests/test_prompt_composer_v077.py — Korean-freeform → English prompt composition
and the hybrid build_prompt_batch (v1.0.0-alpha.77).

Covers:
  * compose_english_prompt: empty freeform → template (no network); freeform +
    no key → fallback_nokey (no network); freeform + LLM ok → composed English;
    freeform + LLM failure → fallback_error. The API key is never logged.
  * the LLM instruction weaves in the Korean text, country, mood, person, and
    the selected form's composition constraint.
  * _clean strips fences/quotes/newlines.
  * build_prompt_batch hybrid: no override → legacy varied batch; override →
    N candidates all carrying the single English prompt, other template fields
    (negative w/ FORM merge, palette, safe area) preserved.
  * for every form A~F the FORM_SPECS composition constraint is carried through.

NO real Gemini calls — requests is mocked; the factory/env is cleared so the
no-key path never reaches the network.
"""
from __future__ import annotations

from unittest import mock

import pytest

from services.thumbnail import prompt_composer as pc
from services.thumbnail.prompt_generator import build_prompt_batch, generate_prompt_batch
from services.thumbnail.form_prompt_builder import FORM_SPECS


_KEY_VARS = ("GOOGLE_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY")


@pytest.fixture(autouse=True)
def _no_key(monkeypatch):
    for v in _KEY_VARS:
        monkeypatch.delenv(v, raising=False)
    yield


def _gemini_resp(text):
    r = mock.Mock()
    r.status_code = 200
    r.json = mock.Mock(return_value={
        "candidates": [{"content": {"parts": [{"text": text}]}}]
    })
    return r


# ── compose_english_prompt ───────────────────────────────────────────────────

def test_empty_freeform_returns_template_no_network():
    with mock.patch("requests.post") as post:
        r = pc.compose_english_prompt("", "korea", "rainy night", True, "A")
    assert r["prompt_source"] == "template"
    assert r["freeform_ko"] == ""
    assert r["form"] == "A"
    assert r["form_composition"]           # FORM_SPECS composition present
    post.assert_not_called()               # no LLM call when freeform empty


def test_freeform_without_key_falls_back_no_network(monkeypatch):
    with mock.patch("requests.post") as post:
        r = pc.compose_english_prompt("비 오는 홍대 골목", "korea", "night", True, "A")
    assert r["prompt_source"] == "fallback_nokey"
    assert r["freeform_ko"] == "비 오는 홍대 골목"
    # fell back to the template main_prompt (still a real prompt)
    assert "city-pop" in r["main_prompt"].lower()
    post.assert_not_called()


def test_freeform_with_key_composes_via_gemini(monkeypatch):
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "AIza_secret_key")
    monkeypatch.setattr(pc, "_gemini_key", lambda: "AIza_secret_key")
    composed_text = "A rainy Hongdae alley at night, a woman in a beige trench coat holding a Walkman, neon reflections on wet asphalt, cinematic citypop"
    with mock.patch("requests.post", return_value=_gemini_resp(composed_text)) as post, \
         mock.patch("providers.ai.base.GeminiProvider.list_models", return_value=["gemini-2.5-flash"]):
        r = pc.compose_english_prompt("비 오는 홍대 골목, 트렌치코트, 워크맨", "korea", "night", True, "A")
    assert r["prompt_source"] == "llm"
    assert r["main_prompt"] == composed_text
    # the instruction embedded the Korean text + composition constraint
    sent = post.call_args.kwargs["json"]["contents"][0]["parts"][0]["text"]
    assert "비 오는 홍대 골목" in sent
    assert FORM_SPECS["A"]["composition_169"] in sent
    assert "no text" in sent.lower()


def test_freeform_llm_failure_falls_back(monkeypatch):
    monkeypatch.setattr(pc, "_gemini_key", lambda: "AIza_key")
    bad = mock.Mock(); bad.status_code = 500; bad.json = mock.Mock(return_value={})
    with mock.patch("requests.post", return_value=bad), \
         mock.patch("providers.ai.base.GeminiProvider.list_models", return_value=[]):
        r = pc.compose_english_prompt("비 오는 밤", "korea", "night", True, None)
    assert r["prompt_source"] == "fallback_error"
    assert r["main_prompt"]  # still the template fallback


def test_gemini_key_and_text_never_logged(monkeypatch, caplog):
    import logging
    monkeypatch.setattr(pc, "_gemini_key", lambda: "AIza_SECRET")
    with mock.patch("requests.post", side_effect=RuntimeError("boom AIza_SECRET")), \
         mock.patch("providers.ai.base.GeminiProvider.list_models", return_value=[]), \
         caplog.at_level(logging.WARNING):
        pc.compose_english_prompt("x", "korea", "night", True, None)
    assert "AIza_SECRET" not in caplog.text


def test_clean_strips_fences_quotes_and_newlines():
    assert pc._clean('```\n"A cat\non a mat"\n```') == "A cat on a mat"
    assert pc._clean("  plain text  ") == "plain text"


def test_person_flag_changes_instruction(monkeypatch):
    base = pc.compose_english_prompt("", "korea", "night", True, None)
    instr_person = pc._build_llm_instruction("여성", base, include_person=True)
    instr_bg = pc._build_llm_instruction("여성", base, include_person=False)
    assert "woman in her early twenties" in instr_person
    assert "Background only" in instr_bg


# ── 🎲 suggest_korean_prompt ─────────────────────────────────────────────────

def test_suggest_korean_no_key_uses_curated_fallback_no_network():
    with mock.patch("requests.post") as post:
        s = pc.suggest_korean_prompt("rainy night drive", "korea", include_person=True)
    assert isinstance(s, str) and s.strip()
    assert "rainy night drive" in s          # mood woven in
    # a curated person template mentions a woman ("여성")
    assert "여성" in s
    post.assert_not_called()


def test_suggest_korean_background_pool_when_no_person():
    with mock.patch("requests.post"):
        s = pc.suggest_korean_prompt("neon nostalgia", "japan", include_person=False)
    assert "여성" not in s                    # background pool has no person
    assert "neon nostalgia" in s


def test_suggest_korean_uses_gemini_when_key_present(monkeypatch):
    monkeypatch.setattr(pc, "_gemini_key", lambda: "AIza_key")
    with mock.patch("requests.post", return_value=_gemini_resp("서울 비 오는 밤, 트렌치코트 여성")) as post, \
         mock.patch("providers.ai.base.GeminiProvider.list_models", return_value=["gemini-2.5-flash"]):
        s = pc.suggest_korean_prompt("rainy night", "korea", include_person=True)
    assert s == "서울 비 오는 밤, 트렌치코트 여성"
    # instruction carried the mood + Korean-output directive
    sent = post.call_args.kwargs["json"]["contents"][0]["parts"][0]["text"]
    assert "rainy night" in sent
    assert "한국어" in sent


def test_suggest_korean_falls_back_when_gemini_fails(monkeypatch):
    monkeypatch.setattr(pc, "_gemini_key", lambda: "AIza_key")
    bad = mock.Mock(); bad.status_code = 500; bad.json = mock.Mock(return_value={})
    with mock.patch("requests.post", return_value=bad), \
         mock.patch("providers.ai.base.GeminiProvider.list_models", return_value=[]):
        s = pc.suggest_korean_prompt("rainy night", "korea", include_person=True)
    assert s.strip() and "rainy night" in s   # curated fallback still returns


# ── build_prompt_batch (hybrid) ──────────────────────────────────────────────

def test_build_prompt_batch_no_override_is_legacy_varied():
    got = build_prompt_batch("korea", "night", 3, True, "A")
    legacy = generate_prompt_batch("korea", "night", 3, True, "A")
    assert [p["main_prompt"] for p in got] == [p["main_prompt"] for p in legacy]
    assert len({p["main_prompt"] for p in got}) == 3  # varied scenes


def test_build_prompt_batch_override_is_single_source():
    got = build_prompt_batch("korea", "night", 4, True, "A",
                             english_override="MY CUSTOM ENGLISH PROMPT", freeform_ko="한글")
    assert len(got) == 4
    assert {p["main_prompt"] for p in got} == {"MY CUSTOM ENGLISH PROMPT"}
    for p in got:
        assert p["prompt_source"] == "freeform"
        assert p["freeform_ko"] == "한글"
        assert p["negative_prompt"]        # template negative preserved
        assert p["form"] == "A"
        assert p["color_palette"]          # palette preserved for branding
        assert p["title_safe_area"]


def test_build_prompt_batch_blank_override_treated_as_legacy():
    got = build_prompt_batch("korea", "night", 2, True, None, english_override="   ")
    assert len({p["main_prompt"] for p in got}) == 2  # blank override → legacy


@pytest.mark.parametrize("form", list("ABCDEF"))
def test_all_forms_composition_carried_into_override_negative(form):
    # override keeps the template's FORM-merged negative for each form
    got = build_prompt_batch("korea", "night", 1, True, form,
                             english_override="EN", freeform_ko="k")
    assert got[0]["form"] == form
    assert got[0]["negative_prompt"]
    # and the template path (compose fallback) embeds that form's composition
    base = pc.compose_english_prompt("", "korea", "night", True, form)
    assert base["form_composition"] == FORM_SPECS[form]["composition_169"]
