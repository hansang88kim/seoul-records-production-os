#!/usr/bin/env python3
"""CI helper: package cleanliness checks."""
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent

# No brace-expansion dirs
bad = [str(d) for d in root.rglob("*")
       if d.is_dir() and ("{" in d.name or "}" in d.name or "," in d.name)]
assert not bad, f"Brace-expansion dirs found: {bad}"
print("✅ No brace-expansion directories")

# outputs/.gitkeep
assert (root / "outputs" / ".gitkeep").exists(), "outputs/.gitkeep missing"
print("✅ outputs/.gitkeep present")

# Provider registry single source
assert "def get_composer_provider" not in (root / "providers/suno/mock_suno.py").read_text(encoding="utf-8")
assert "def get_composer_provider" in (root / "providers/suno/__init__.py").read_text(encoding="utf-8")
print("✅ Provider registry is single source")

# exclude_styles is list[str]
assert "exclude_styles: list[str]" in (root / "app/models.py").read_text(encoding="utf-8")
print("✅ exclude_styles type is list[str]")

# Version consistency: config.py → pyproject.toml and models.py
config_text = (root / "app/config.py").read_text(encoding="utf-8")
match = re.search(r'APP_VERSION = "([^"]+)"', config_text)
assert match, "APP_VERSION not found in app/config.py"
ver = match.group(1)

pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
assert f'version = "{ver}"' in pyproject, f"pyproject.toml version mismatch: expected {ver}"

models = (root / "app/models.py").read_text(encoding="utf-8")
assert f'app_version: str = "{ver}"' in models, f"models.py app_version mismatch: expected {ver}"

print(f"✅ Version consistency: {ver}")
print("Package cleanliness checks passed.")
