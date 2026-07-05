"""
tests/test_history_library_pages.py — History / Library sidebar pages
(v1.0.0-alpha.38), smoke-tested with Streamlit's official AppTest harness
(streamlit.testing.v1) — a stronger guarantee than source-wiring checks
alone: this actually RUNS the page and asserts no exception was raised.
"""
from __future__ import annotations

import pytest

try:
    from streamlit.testing.v1 import AppTest
    _HAS_APPTEST = True
except Exception:
    _HAS_APPTEST = False


pytestmark = pytest.mark.skipif(not _HAS_APPTEST, reason="streamlit.testing.v1 not available")


def test_history_page_renders_without_exception(monkeypatch, tmp_path):
    monkeypatch.setattr("services.job_store._jobs_dir", lambda: tmp_path / "jobs")
    at = AppTest.from_file("app/main.py")
    at.session_state["nav_page"] = "history"
    at.run(timeout=30)
    assert not at.exception


def test_library_page_renders_without_exception(monkeypatch, tmp_path):
    monkeypatch.setattr("services.thumbnail.session_store._studio_root", lambda: tmp_path / "studio")
    at = AppTest.from_file("app/main.py")
    at.session_state["nav_page"] = "library"
    at.run(timeout=30)
    assert not at.exception
    # Two sub-tabs: songs + images
    assert len(at.tabs) == 2


def test_dashboard_page_still_renders_without_exception():
    at = AppTest.from_file("app/main.py")
    at.session_state["nav_page"] = "dashboard"
    at.run(timeout=30)
    assert not at.exception


def test_settings_page_still_renders_without_exception():
    at = AppTest.from_file("app/main.py")
    at.session_state["nav_page"] = "settings"
    at.run(timeout=30)
    assert not at.exception
