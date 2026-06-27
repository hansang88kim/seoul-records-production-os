#!/usr/bin/env python3
"""
workflows/validate_package_zip.py
─────────────────────────────────
Validates a Seoul Records Production OS zip package for cleanliness.

Usage:
  python workflows/validate_package_zip.py dist/seoul-records-production-os-v0.1.2.zip

Checks:
  - No __pycache__ directories
  - No .pytest_cache directories
  - No brace-expansion directories
  - outputs/.gitkeep exists
  - No generated media assets (WAV, MP3, MP4, PNG, JPG in outputs/)
  - No .env file
  - No *.pyc files

Exits 0 on success, 1 on failure.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path


def validate_zip(zip_path: str) -> list[str]:
    """Return a list of violation messages. Empty = clean."""
    violations: list[str] = []

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()

    # Check for __pycache__
    pycache = [n for n in names if "__pycache__" in n]
    if pycache:
        violations.append(f"__pycache__ found ({len(pycache)} entries): {pycache[:3]}")

    # Check for .pytest_cache
    pytest_cache = [n for n in names if ".pytest_cache" in n]
    if pytest_cache:
        violations.append(f".pytest_cache found ({len(pytest_cache)} entries)")

    # Check for *.pyc
    pyc = [n for n in names if n.endswith(".pyc")]
    if pyc:
        violations.append(f"*.pyc files found ({len(pyc)} entries): {pyc[:3]}")

    # Check for brace-expansion dirs
    brace = [n for n in names if "{" in n or "}" in n]
    if brace:
        violations.append(f"Brace-expansion entries found: {brace[:3]}")

    # Check outputs/.gitkeep exists
    gitkeep_candidates = [n for n in names if n.endswith("outputs/.gitkeep")]
    if not gitkeep_candidates:
        violations.append("outputs/.gitkeep not found in zip")

    # Check for generated media in outputs/
    media_in_outputs = [
        n for n in names
        if "/outputs/" in n
        and not n.endswith(".gitkeep")
        and any(n.lower().endswith(ext) for ext in
                [".wav", ".mp3", ".mp4", ".mov", ".png", ".jpg", ".jpeg", ".zip"])
    ]
    if media_in_outputs:
        violations.append(
            f"Generated media in outputs/ ({len(media_in_outputs)}): {media_in_outputs[:3]}"
        )

    # Check no .env
    env_files = [n for n in names if n.endswith("/.env") or n.endswith("/.env.local")]
    if env_files:
        violations.append(f".env files found: {env_files}")

    return violations


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <path-to-zip>")
        sys.exit(2)

    zip_path = sys.argv[1]
    if not Path(zip_path).exists():
        print(f"ERROR: File not found: {zip_path}")
        sys.exit(2)

    print(f"Validating: {zip_path}")
    violations = validate_zip(zip_path)

    with zipfile.ZipFile(zip_path) as zf:
        total = len(zf.namelist())

    if violations:
        print(f"\n❌ FAILED — {len(violations)} violation(s) in {total} files:\n")
        for v in violations:
            print(f"  • {v}")
        sys.exit(1)
    else:
        print(f"\n✅ PASSED — {total} files, no violations")
        sys.exit(0)


if __name__ == "__main__":
    main()
