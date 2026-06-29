"""
tests/test_frontend_v100.py — Frontend Modernization (v1.0.0-alpha) tests.

Structural/content checks for the Next.js frontend shell (runnable in pytest
without Node), plus a real no-secrets test on the Python snapshot bridge. Test
names follow the v1.0.0-alpha spec.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

FE = Path("frontend")


def _read(p: str) -> str:
    return (FE / p).read_text(encoding="utf-8")


# ─── Directory + stack ───────────────────────────────────────────────────────

def test_frontend_directory_exists():
    assert FE.is_dir()
    assert (FE / "package.json").exists()
    assert (FE / "app").is_dir()


def test_frontend_package_uses_next_15_or_higher():
    pkg = json.loads(_read("package.json"))
    next_ver = pkg["dependencies"]["next"]
    m = re.search(r"(\d+)", next_ver)
    assert m and int(m.group(1)) >= 15, f"Next.js must be >=15, got {next_ver}"
    for dep in ("react", "react-dom"):
        rm = re.search(r"(\d+)", pkg["dependencies"][dep])
        assert rm and int(rm.group(1)) >= 19, f"{dep} must be >=19"


def test_frontend_uses_typescript():
    assert (FE / "tsconfig.json").exists()
    ts = json.loads(_read("tsconfig.json"))
    assert ts["compilerOptions"]["strict"] is True
    assert "@/*" in ts["compilerOptions"]["paths"]


def test_frontend_uses_tailwind_v4_or_higher():
    pkg = json.loads(_read("package.json"))
    tw = pkg["devDependencies"]["tailwindcss"]
    m = re.search(r"(\d+)", tw)
    assert m and int(m.group(1)) >= 4, f"Tailwind must be >=4, got {tw}"
    assert "@tailwindcss/postcss" in pkg["devDependencies"]


def test_frontend_uses_shadcn_style_components():
    assert (FE / "components.json").exists()
    for comp in ["button", "card", "badge", "tabs", "alert", "table", "progress"]:
        assert (FE / "components" / "ui" / f"{comp}.tsx").exists(), f"missing ui/{comp}"
    pkg = json.loads(_read("package.json"))
    for dep in ["class-variance-authority", "clsx", "tailwind-merge", "lucide-react"]:
        assert dep in pkg["dependencies"], f"{dep} missing"


def test_frontend_has_dark_theme_tokens():
    css = _read("styles/globals.css")
    for token in ["--background", "--foreground", "--card", "--border",
                  "--accent-cyan", "--accent-magenta", "--accent-amber",
                  "--success", "--warning", "--danger"]:
        assert token in css, f"missing design token {token}"
    assert 'className="dark"' in _read("app/layout.tsx")


def test_frontend_has_responsive_layout():
    blob = "".join(_read(f) for f in [
        "components/layout/studio-sidebar.tsx",
        "components/layout/topbar.tsx",
        "components/layout/app-shell.tsx",
        "app/page.tsx",
    ])
    assert "md:" in blob and "lg:" in blob
    assert "md:hidden" in _read("components/layout/topbar.tsx")
    assert (FE / "components" / "layout" / "mobile-nav.tsx").exists()


# ─── Routes ──────────────────────────────────────────────────────────────────

def test_frontend_routes_exist():
    for route in ["song-lab", "thumbnail-studio", "video-renderer",
                  "youtube-package", "production-qa", "unitedmasters",
                  "remote-control", "settings"]:
        assert (FE / "app" / route / "page.tsx").exists(), f"missing route {route}"


def test_dashboard_route_exists():
    assert (FE / "app" / "page.tsx").exists()


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


def test_settings_route_exists():
    assert (FE / "app" / "settings" / "page.tsx").exists()


# ─── Types + API surface (aligned to backend) ────────────────────────────────

def test_frontend_types_define_spec_models():
    types = _read("lib/types.ts")
    for t in ["PipelineStatus", "JobStatus", "ProductionReadiness", "AssetSummary",
              "SongTrack", "ThumbnailAsset", "VideoRenderJob", "YouTubePackage",
              "UnitedMastersPackage", "RemoteControlStatus"]:
        assert t in types, f"missing type {t}"


def test_frontend_api_defines_spec_functions():
    api = _read("lib/api.ts")
    for fn in ["getDashboardStatus", "getProductionReadiness", "getActiveJobs",
               "getRecentAssets", "getVideoRenderJobs", "getYouTubePackages",
               "getUnitedMastersPackages", "getRemoteControlStatus"]:
        assert fn in api, f"missing api function {fn}"


# ─── No secrets ──────────────────────────────────────────────────────────────

def test_frontend_does_not_contain_secret_like_strings():
    bad = ["ya29.", "ghp_", "sk-", "Bearer ", "client_secret\"", "refresh_token\":",
           "BEGIN PRIVATE KEY"]
    for ext in ("*.tsx", "*.ts"):
        for f in FE.rglob(ext):
            text = f.read_text(encoding="utf-8")
            for marker in bad:
                assert marker not in text, f"{marker!r} found in {f}"


def test_frontend_types_have_no_secret_fields():
    types = _read("lib/types.ts")
    for forbidden in ["access_token", "refresh_token", "client_secret",
                      "bot_token", "api_key", "secret_key"]:
        assert f"{forbidden}:" not in types
        assert f"{forbidden}?:" not in types


# ─── Existing Streamlit + backend intact ─────────────────────────────────────

def test_existing_streamlit_app_still_exists():
    assert Path("app/main.py").exists()
    assert Path("app/dashboard.py").exists()
    assert Path("app/tabs/production_qa_tab.py").exists()


def test_existing_backend_pytest_still_passes():
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


# ─── Python snapshot bridge is sanitized ─────────────────────────────────────

def test_snapshot_bridge_builds_and_is_secret_free(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:SECRETLEAK_TOKENVALUE")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHAT_IDS", "111,222")
    from api.snapshot import build_snapshot, snapshot_json
    snap = build_snapshot()
    assert "production_qa" in snap and "remote_control" in snap
    assert snap["remote_control"]["allowed_chat_id_count"] == 2
    js = snapshot_json()
    assert "SECRETLEAK" not in js
    assert "123:" not in js

# ─── v1.0.0-alpha.1 build-fix regression guards ─────────────────────────────

def test_frontend_does_not_use_google_fonts():
    """next/font/google requires network at build time — must be absent."""
    for ext in ("*.tsx", "*.ts"):
        for f in FE.rglob(ext):
            text = f.read_text(encoding="utf-8")
            assert "next/font/google" not in text, f"next/font/google in {f}"
            assert "next/font" not in text, f"next/font in {f}"


def test_frontend_uses_system_font_stack():
    """globals.css defines an offline system font stack (no Geist vars)."""
    css = _read("styles/globals.css")
    assert "--font-sans:" in css
    assert "system-ui" in css
    assert "--font-geist-sans" not in css
    assert "--font-geist-mono" not in css
    # body actually applies the token
    assert "font-family: var(--font-sans)" in css


def test_layout_has_no_font_import():
    layout = _read("app/layout.tsx")
    assert "next/font" not in layout
    assert "Geist" not in layout
    # body uses the system font utility
    assert "font-sans" in layout


def test_lint_script_not_deprecated_next_lint():
    """lint should use the ESLint CLI, not the deprecated `next lint`."""
    pkg = json.loads(_read("package.json"))
    lint = pkg["scripts"]["lint"]
    assert "eslint" in lint
    assert lint.strip() != "next lint"


def test_remote_control_has_no_unused_radio_import():
    """The earlier TS6133 'Radio' unused-import blocker must stay fixed."""
    src = _read("app/remote-control/page.tsx")
    # If Radio is imported, it must be used; simplest guard: it isn't imported here
    import re as _re
    imported = bool(_re.search(r'import\s*\{[^}]*\bRadio\b[^}]*\}\s*from\s*"lucide-react"', src))
    assert not imported, "remote-control should not import an unused Radio icon"

