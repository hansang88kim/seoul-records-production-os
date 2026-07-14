"""
tests/conftest.py — keep the suite OFFLINE & DETERMINISTIC.

v1.0.0-alpha.109: several modules import app.config, which runs load_dotenv() and
puts real OPENAI/GEMINI keys into the environment. After the alpha.109 LLM fix,
that would make seo_description / concept_suggester / description translation
issue LIVE API calls during tests (slow, costly, flaky, non-deterministic).

This autouse fixture disables real LLM calls by default. Tests that specifically
exercise an LLM path monkeypatch these to return a value in their own body,
which overrides this default.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _disable_real_llm_calls(monkeypatch):
    try:
        import services.youtube.description_translator as DT
        for name in ("call_llm_raw", "_openai_chat", "_gemini_chat",
                     "_call_openai", "_call_gemini"):
            monkeypatch.setattr(DT, name, lambda *a, **k: None, raising=False)
    except Exception:
        pass
    yield
