"""
tests/test_thumbnail_image_gen_v100.py — real-image generation (v1.0.0-alpha.4).

Covers the new image-generation path:
  * MockImageGenProvider writes real PNG files (no network, no cost)
  * get_image_provider falls back to mock without an API key (never calls out)
  * generate_images creates images + links them to candidates
  * project-bound sessions save images into <project>/thumbnails/ (separate from
    <project>/songs/ audio)
  * the existing select/brand pipeline works on generated images
  * dependency check reports readiness WITHOUT exposing the key

NO real Gemini/Imagen calls — the provider factory returns the mock whenever an
API key or the SDK is absent, which is always the case under test.
"""
from __future__ import annotations

import os
import pytest
from pathlib import Path

import services.thumbnail.session_store as ss
from services.thumbnail.prompt_generator import generate_prompt_batch
from services.thumbnail import image_provider as ip
from services.thumbnail import image_gen_deps as deps


@pytest.fixture(autouse=True)
def studio_tmp(monkeypatch, tmp_path):
    """Redirect the studio root to a temp folder and clear any real API key."""
    monkeypatch.setattr(ss, "_studio_root", lambda: tmp_path / "studio")
    for var in ip._API_KEY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    yield


def _png_magic(path: str) -> bool:
    with open(path, "rb") as f:
        return f.read(8) == b"\x89PNG\r\n\x1a\n"


# ─── Mock provider ───────────────────────────────────────────────────────────

def test_mock_provider_writes_real_png(tmp_path):
    prov = ip.MockImageGenProvider()
    out = tmp_path / "m.png"
    res = prov.generate("a citypop night street", str(out), index=0,
                        meta={"scene": "rainy crosswalk", "country": "일본", "theme": "rainy night"})
    assert res["ok"] is True
    assert res["provider"] == "mock"
    assert out.exists() and _png_magic(str(out))


def test_mock_provider_is_not_real():
    assert ip.MockImageGenProvider().is_real is False


# ─── Factory safety (never call the real API without a key) ───────────────────

def test_factory_use_real_false_returns_mock():
    prov = ip.get_image_provider(use_real=False)
    assert isinstance(prov, ip.MockImageGenProvider)


def test_factory_use_real_true_without_key_returns_mock(monkeypatch):
    for var in ip._API_KEY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    prov = ip.get_image_provider(use_real=True)
    assert isinstance(prov, ip.MockImageGenProvider)
    assert prov.is_real is False


def test_gemini_provider_no_key_returns_error_without_network(monkeypatch):
    for var in ip._API_KEY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    prov = ip.GeminiImageProvider(api_key=None)
    res = prov.generate("prompt", str(Path(os.devnull)))
    assert res["ok"] is False
    assert "api key" in res["error"].lower()


def test_gemini_rest_provider_no_key_returns_error_without_network(monkeypatch):
    for var in ip._API_KEY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    prov = ip.GeminiRestImageProvider(api_key=None)
    res = prov.generate("prompt", str(Path(os.devnull)))
    assert res["ok"] is False
    assert "api key" in res["error"].lower()


def test_factory_with_key_returns_real_provider_no_call(monkeypatch):
    # A key present -> factory returns a REAL provider; only the type is checked,
    # .generate is never called (that would hit the network).
    for var in ip._API_KEY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("SEOUL_IMAGE_BACKEND", raising=False)
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "fake-key-not-used")
    prov = ip.get_image_provider(use_real=True)
    assert isinstance(prov, ip.GeminiRestImageProvider)
    assert prov.is_real is True


def test_sidebar_key_var_recognized_and_ready(monkeypatch):
    # The key entered in the app's sidebar (GOOGLE_GEMINI_API_KEY) is picked up
    # and makes the real path "ready" without any SDK install (REST backend).
    for var in ip._API_KEY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("SEOUL_IMAGE_BACKEND", raising=False)
    assert ip.get_api_key() is None
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "sidebar-key")
    assert ip.get_api_key() == "sidebar-key"
    rep = deps.check_image_gen_dependencies()
    assert rep["api_key_present"] is True
    assert rep["ready"] is True
    assert "sidebar-key" not in str(rep)


# ─── generate_images end-to-end (mock) ───────────────────────────────────────

def test_generate_images_creates_files_and_candidates():
    sess = ss.create_session("일본", "rainy night drive", "CityPop Vol.5", volume=5)
    prompts = generate_prompt_batch("일본", "rainy night drive", count=5)
    cands = ss.generate_images(sess["session_id"], prompts, use_real=False)
    assert len(cands) == 5
    for c in cands:
        assert c["status"] == "image_generated"
        assert c["gen_provider"] == "mock"
        assert c["uploaded_image_path"]
        assert Path(c["uploaded_image_path"]).exists()
        assert _png_magic(c["uploaded_image_path"])


def test_generate_images_standalone_saves_in_session():
    sess = ss.create_session("korea", "neon", "Seoul Vol.1")
    prompts = generate_prompt_batch("korea", "neon", count=2)
    cands = ss.generate_images(sess["session_id"], prompts, use_real=False)
    # Standalone (no project) -> images live under the session candidates/images
    for c in cands:
        assert "candidates" in c["uploaded_image_path"]


# ─── Project-bound: images go to <project>/thumbnails/, audio stays in songs/ ─

def test_generate_images_project_bound_saves_into_thumbnails(tmp_path):
    # Simulate a Song-Lab project folder with a songs/ subfolder + one mp3.
    project = tmp_path / "song_projects" / "일본-시티팝-Vol.01"
    (project / "songs").mkdir(parents=True)
    (project / "songs" / "track.mp3").write_bytes(b"ID3mock")

    sess = ss.create_session("일본", "city night", "일본 시티팝 Vol.01",
                             volume=1, project_folder=str(project))
    prompts = generate_prompt_batch("일본", "city night", count=3)
    cands = ss.generate_images(sess["session_id"], prompts, use_real=False)

    thumbs = project / "thumbnails"
    assert thumbs.exists()
    pngs = list(thumbs.glob("*.png"))
    assert len(pngs) == 3
    # Audio and images are in SEPARATE folders under the same project.
    assert (project / "songs" / "track.mp3").exists()
    for c in cands:
        assert str(thumbs) in c["uploaded_image_path"]
        assert "/songs/" not in c["uploaded_image_path"].replace("\\", "/")


def test_image_target_dir_creates_project_thumbnails(tmp_path):
    project = tmp_path / "song_projects" / "p1"
    (project / "songs").mkdir(parents=True)
    sess = ss.create_session("korea", "x", "P1", project_folder=str(project))
    target = ss.image_target_dir(sess["session_id"])
    assert target == project / "thumbnails"
    assert target.exists()


# ─── Selection -> branding pipeline works on generated images ─────────────────

def test_generated_image_selectable_for_branding():
    sess = ss.create_session("japan", "sunset", "Vol.2")
    sid = sess["session_id"]
    prompts = generate_prompt_batch("japan", "sunset", count=3)
    ss.generate_images(sid, prompts, use_real=False)

    ss.select_for_branding(sid, "cand_002", True)
    selected = ss.get_selected_candidates(sid)
    assert len(selected) == 1
    assert selected[0]["candidate_id"] == "cand_002"
    assert Path(selected[0]["uploaded_image_path"]).exists()


# ─── Dependency / key check (never exposes the key) ──────────────────────────

def test_dependency_check_structure_no_key(monkeypatch):
    for var in ip._API_KEY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    rep = deps.check_image_gen_dependencies()
    for key in ("sdk_installed", "api_key_present", "ready", "model",
                "install_hint", "key_hint"):
        assert key in rep
    assert rep["api_key_present"] is False
    assert rep["ready"] is False
    # The report must never contain an actual key value.
    monkeypatch.setenv("GEMINI_API_KEY", "sk-secret-shouldnotleak-123")
    rep2 = deps.check_image_gen_dependencies()
    assert rep2["api_key_present"] is True
    assert "sk-secret-shouldnotleak-123" not in str(rep2)


def test_get_api_key_reads_env(monkeypatch):
    for var in ip._API_KEY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    assert ip.get_api_key() is None
    monkeypatch.setenv("GEMINI_API_KEY", "  key123  ")
    assert ip.get_api_key() == "key123"


# ─── Prompt remains country/theme aware (feeds the provider) ─────────────────

def test_prompt_batch_reflects_country_and_theme():
    prompts = generate_prompt_batch("일본", "midnight harbor", count=4)
    assert len(prompts) == 4
    for p in prompts:
        assert "midnight harbor" in p["main_prompt"]
        assert p["country"] == "일본"
