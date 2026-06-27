"""
Tests for package cleanliness and structural correctness (v0.1.2).

NOTE: Tests marked @pytest.mark.package inspect source text, not the runtime
working tree. They will not fail due to __pycache__/.pytest_cache created
by pytest itself.

For full zip validation, use:
  python workflows/validate_package_zip.py <path-to-zip>
"""
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ─── Structural checks (safe to run alongside pytest) ─────────────────────────

def test_no_brace_expansion_directories():
    """Fix 1: No accidental brace-expansion directories."""
    brace_dirs = [
        d for d in ROOT.rglob("*")
        if d.is_dir() and ("{" in d.name or "}" in d.name or "," in d.name)
    ]
    assert not brace_dirs, (
        f"Brace-expansion directories found: {[str(d) for d in brace_dirs]}"
    )


def test_outputs_gitkeep_exists():
    """Fix 1: outputs/.gitkeep must exist."""
    assert (ROOT / "outputs" / ".gitkeep").exists(), "outputs/.gitkeep is missing"


def test_provider_registry_is_only_in_init():
    """Fix 2: get_composer_provider defined ONLY in providers/suno/__init__.py."""
    for fname in [
        "mock_suno.py", "manual_import.py", "local_unofficial_suno.py",
        "playwright_suno_web.py", "third_party_suno.py",
    ]:
        src = (ROOT / "providers" / "suno" / fname).read_text()
        assert "def get_composer_provider" not in src, (
            f"get_composer_provider must not be defined in {fname}"
        )
    init_src = (ROOT / "providers" / "suno" / "__init__.py").read_text()
    assert "def get_composer_provider" in init_src


def test_generate_album_imports_from_registry():
    """Fix 2: generate_album.py must import from providers.suno, not mock_suno."""
    src = (ROOT / "workflows" / "generate_album.py").read_text()
    assert "from providers.suno import get_composer_provider" in src


def test_exclude_styles_type_in_source():
    """Fix 3: models.py must declare exclude_styles as list[str]."""
    src = (ROOT / "app" / "models.py").read_text()
    assert "exclude_styles: list[str]" in src
    assert "exclude_styles: str =" not in src


def test_no_deprecated_utcnow_in_source():
    """
    Fix 2/9: No production source files may call datetime.utcnow().
    Test files and this file itself are excluded from the scan.

    We build the search token dynamically so this file does not contain
    the literal forbidden string.
    """
    # Build the forbidden pattern without embedding it as a string literal
    forbidden = ".".join(["datetime", "utcnow()"])

    violations = []
    for py_file in ROOT.rglob("*.py"):
        rel = str(py_file.relative_to(ROOT))
        # Skip test files, __pycache__, and this file
        if "__pycache__" in rel:
            continue
        if rel.startswith("tests/"):
            continue
        content = py_file.read_text(encoding="utf-8")
        for lineno, line in enumerate(content.split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if forbidden in stripped:
                violations.append(f"{rel}:{lineno}")

    assert not violations, (
        f"datetime.utcnow() found in source files "
        f"(use datetime.now(timezone.utc)): {violations}"
    )


def test_track_manifest_has_track_folder_path():
    """Fix 6: TrackManifest must have track_folder_path field."""
    src = (ROOT / "app" / "models.py").read_text()
    assert "track_folder_path" in src


def test_version_consistency():
    """Fix 4: All version strings must match."""
    pyproject = (ROOT / "pyproject.toml").read_text()
    config = (ROOT / "app" / "config.py").read_text()
    models = (ROOT / "app" / "models.py").read_text()

    from app.config import APP_VERSION as _V
    assert f'version = "{_V}"' in pyproject
    assert f'APP_VERSION = "{_V}"' in config
    assert f'app_version: str = "{_V}"' in models


def test_mock_provider_has_fast_mode():
    """Fix 3: MockSunoProvider must support fast_mode."""
    src = (ROOT / "providers" / "suno" / "mock_suno.py").read_text()
    assert "fast_mode" in src
    assert "_FAST_WAV_SECONDS" in src


def test_candidate_override_uses_track_folder_path():
    """Fix 6: Candidate override must not scan all song folders."""
    src = (ROOT / "app" / "tabs" / "tab1_song_generation.py").read_text()
    assert "track_folder_path" in src
    # Must NOT iterate over all folders
    assert "for folder in (songs_root" not in src
