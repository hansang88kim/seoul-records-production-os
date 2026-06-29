"""
tests/test_frontend_v100.py — Frontend Modernization (v1.0.0-alpha) tests.

These verify the Next.js frontend shell is present and correctly configured, and
that the Python snapshot bridge is sanitized. They are structural/content checks
(runnable in pytest without Node) plus a real no-secrets test on the API bridge.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

import pytest

FE = Path("frontend")


def _read(p: str) -> str:
    return (FE / p).read_text(encoding="utf-8")


# ─── Stack: Next 15 / TS / Tailwind v4 / shadcn ──────────────────────────────

def test_frontend_package_uses_next_15_or_higher():
    pkg = json.loads(_read("package.json"))
    next_ver = pkg["dependencies"]["next"]
    m = re.search(r"(\d+)", next_ver)
    assert m and int(m.group(1)) >= 15, f"Next.js must be >=15, got {next_ver}"


def test_frontend_uses_typescript():
    assert (FE / "tsconfig.json").exists()
    ts = json.loads(_read("tsconfig.json"))
    assert ts["compilerOptions"]["strict"] is True
    # path alias @/*
    assert "@/*" in ts["compilerOptions"]["paths"]


def test_frontend_uses_tailwind_v4_or_higher():
    pkg = json.loads(_read("package.json"))
    tw = pkg["devDependencies"]["tailwindcss"]
    m = re.search(r"(\d+)", tw)
    assert m and int(m.group(1)) >= 4, f"Tailwind must be >=4, got {tw}"
    # v4 uses the dedicated postcss plugin
    assert "@tailwindcss/postcss" in pkg["devDependencies"]


def test_frontend_uses_shadcn_components():
    # components.json exists and the ui components are present
    assert (FE / "components.json").exists()
    for comp in ["button", "card", "badge", "tabs", "alert", "table", "progress"]:
        assert (FE / "components" / "ui" / f"{comp}.tsx").exists(), f"missing ui/{comp}"


def test_frontend_has_dark_theme_tokens():
    css = _read("app/globals.css")
    # design tokens + dark default
    for token in ["--background", "--foreground", "--card", "--border",
                  "--accent-cyan", "--accent-magenta", "--accent-amber",
                  "--success", "--warning", "--danger"]:
        assert token in css, f"missing design token {token}"
    layout = _read("app/layout.tsx")
    assert 'className="dark"' in layout  # dark is the default


def test_frontend_has_responsive_layout():
    # responsive breakpoints used across the shell
    shell_files = ["components/layout/studio-sidebar.tsx",
                   "components/layout/topbar.tsx",
                   "components/layout/app-shell.tsx",
                   "app/page.tsx"]
    blob = "".join(_read(f) for f in shell_files)
    assert "md:" in blob and "lg:" in blob
    # mobile drawer in topbar
    assert "md:hidden" in _read("components/layout/topbar.tsx")


# ─── Routes exist ────────────────────────────────────────────────────────────

def test_dashboard_route_exists():
    assert (FE / "app" / "page.tsx").exists()


@pytest.mark.parametrize("route", [
    "song-lab", "thumbnail-studio", "video-renderer", "youtube-package",
    "production-qa", "unitedmasters", "remote-control",
])
def test_section_routes_exist(route):
    assert (FE / "app" / route / "page.tsx").exists(), f"missing route {route}"


def test_song_lab_route_exists():
    assert (FE / "app" / "song-lab" / "page.tsx").exists()


def test_thumbnail_studio_route_exists():
    assert (FE / "app" / "thumbnail-studio" / "page.tsx").exists()


def test_video_renderer_route_exists():
    assert (FE / "app" / "video-renderer" / "page.tsx").exists()


def test_youtube_package_route_exists():
    assert (FE / "app" / "youtube-package" / "page.tsx").exists()


def test_production_qa_route_exists():
    assert (FE / "app" / "production-qa" / "page.tsx").exists()


def test_unitedmasters_route_exists():
    assert (FE / "app" / "unitedmasters" / "page.tsx").exists()


def test_remote_control_route_exists():
    assert (FE / "app" / "remote-control" / "page.tsx").exists()


# ─── No secrets rendered ─────────────────────────────────────────────────────

def test_frontend_does_not_render_secrets():
    """No hardcoded secret values anywhere in the frontend source."""
    bad = ["ya29.", "ghp_", "client_secret\"", "refresh_token\":",
           "BEGIN PRIVATE KEY", "sk-"]
    for tsx in FE.rglob("*.tsx"):
        text = tsx.read_text(encoding="utf-8")
        for marker in bad:
            assert marker not in text, f"{marker} found in {tsx}"
    for ts in FE.rglob("*.ts"):
        text = ts.read_text(encoding="utf-8")
        for marker in bad:
            assert marker not in text, f"{marker} found in {ts}"


def test_types_align_with_backend_no_secret_fields():
    """The shared types must not DECLARE token/secret fields (comments OK)."""
    types = _read("lib/types.ts")
    # Look for actual field declarations like `access_token:` or `cookie:`
    for forbidden in ["access_token", "refresh_token", "client_secret",
                      "bot_token", "api_key", "secret_key"]:
        assert f"{forbidden}:" not in types, f"{forbidden} should not be a frontend field"
        assert f"{forbidden}?:" not in types, f"{forbidden} should not be a frontend field"


# ─── Python snapshot bridge is sanitized ─────────────────────────────────────

def test_snapshot_bridge_builds_and_is_secret_free(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:SECRETLEAK_ya29.TOKENVALUE")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "111,222")
    from api.snapshot import build_snapshot, snapshot_json
    snap = build_snapshot()
    # Right shape
    assert "production_qa" in snap and "remote_control" in snap
    assert snap["remote_control"]["allowed_chat_id_count"] == 2
    # No secret leaks
    js = snapshot_json()
    assert "SECRETLEAK" not in js
    assert "ya29.TOKENVALUE" not in js
    assert "123:" not in js


def test_snapshot_remote_control_exposes_only_booleans(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "abc:DEF")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "999")
    from api.snapshot import build_snapshot
    rc = build_snapshot()["remote_control"]
    assert isinstance(rc["telegram_enabled"], bool)
    assert isinstance(rc["allowed_chat_id_count"], int)
    # raw token / chat id strings absent
    assert "DEF" not in json.dumps(rc)


# ─── Existing backend unaffected ─────────────────────────────────────────────

def test_backend_existing_pytest_still_passes():
    """Sanity import of core services (full suite runs separately)."""
    from providers.ai.base import MOCK_SONGS
    from services.video.render_plan import build_full_render_command
    from services.youtube.youtube_package_service import create_package
    from services.unitedmasters.package_service import create_package as um_create
    from services.production.production_checklist import build_checklist
    from services.remote_control.supervisor import health_and_maybe_restart
    assert len(MOCK_SONGS) >= 2
    assert all(callable(f) for f in [build_full_render_command, create_package,
                                     um_create, build_checklist,
                                     health_and_maybe_restart])
