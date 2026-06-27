"""
tests/test_version.py
──────────────────────
Version consistency test — all version strings must match APP_VERSION.
Never hardcodes the version number; always imports APP_VERSION to compare.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# ─── Source of truth ─────────────────────────────────────────────────────────
from app.config import APP_VERSION


BASE_DIR = Path(__file__).resolve().parent.parent


def test_app_version_is_semver():
    """APP_VERSION must be a valid semver string (MAJOR.MINOR.PATCH)."""
    assert re.match(r"^\d+\.\d+\.\d+$", APP_VERSION), (
        f"APP_VERSION '{APP_VERSION}' is not valid semver"
    )


def test_pyproject_toml_version_matches():
    """pyproject.toml version must match APP_VERSION."""
    pyproject = (BASE_DIR / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{APP_VERSION}"' in pyproject, (
        f"pyproject.toml must contain version = \"{APP_VERSION}\"\n"
        f"APP_VERSION={APP_VERSION}"
    )


def test_project_manifest_default_version_matches():
    """ProjectManifest.app_version default must match APP_VERSION."""
    from app.models import ProjectManifest
    import uuid
    # Instantiate with minimal required fields to check default
    m = ProjectManifest(project_id=str(uuid.uuid4()), project_name="version-test")
    assert m.app_version == APP_VERSION, (
        f"ProjectManifest.app_version default is '{m.app_version}', "
        f"expected '{APP_VERSION}'"
    )


def test_readme_mentions_version():
    """README.md must mention the current version."""
    readme = (BASE_DIR / "README.md").read_text(encoding="utf-8")
    assert APP_VERSION in readme, (
        f"README.md must contain '{APP_VERSION}'"
    )


def test_app_version_not_empty():
    """APP_VERSION must be a non-empty string."""
    assert isinstance(APP_VERSION, str)
    assert len(APP_VERSION) > 0
