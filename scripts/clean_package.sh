#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# Seoul Records Production OS — Clean Packaging Script (v0.1.3)
#
# Builds a zip, then validates it. Exits non-zero on any violation.
#
# Usage: bash scripts/clean_package.sh [version]
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

VERSION="${1:-0.1.3}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
ZIP_NAME="seoul-records-production-os-v${VERSION}.zip"
ZIP_PATH="$DIST/$ZIP_NAME"

echo "=== Seoul Records Production OS — Clean Package v${VERSION} ==="

# ── 1. Clean caches ──────────────────────────────────────────────
echo "Cleaning caches..."
find "$ROOT" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$ROOT" -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true
find "$ROOT" -name "*.pyc" -delete 2>/dev/null || true
find "$ROOT" -name ".DS_Store" -delete 2>/dev/null || true

# ── 2. Ensure outputs/.gitkeep ───────────────────────────────────
mkdir -p "$ROOT/outputs"
touch "$ROOT/outputs/.gitkeep"

# ── 3. Create zip ────────────────────────────────────────────────
mkdir -p "$DIST"
rm -f "$ZIP_PATH"
cd "$ROOT/.."

BASENAME="$(basename "$ROOT")"

# Build zip — exclude caches, outputs content, dist, .env, .git
zip -r "$ZIP_PATH" "$BASENAME/" \
  --exclude "*/__pycache__/*" \
  --exclude "*/.pytest_cache/*" \
  --exclude "*/.git/*" \
  --exclude "*/dist/*" \
  --exclude "*/.env" \
  --exclude "*/.DS_Store" \
  --exclude "*/*.pyc" \
  --exclude "*/frontend/node_modules/*" \
  --exclude "*/frontend/.next/*" \
  --exclude "*/frontend/out/*" \
  2>/dev/null

# Explicitly add outputs/.gitkeep (excluded by the outputs/* rule above if present)
cd "$ROOT/.."
zip "$ZIP_PATH" "$BASENAME/outputs/.gitkeep" 2>/dev/null || true

SIZE=$(du -sh "$ZIP_PATH" | cut -f1)
echo "Package created: $ZIP_PATH ($SIZE)"

# ── 4. Validate the zip ─────────────────────────────────────────
echo ""
echo "=== Validation ==="
python3 "$ROOT/workflows/validate_package_zip.py" "$ZIP_PATH"
RESULT=$?

if [ $RESULT -ne 0 ]; then
  echo ""
  echo "❌ Package validation FAILED. Fix issues and re-run."
  exit 1
fi

echo ""
echo "✅ Clean package ready: $ZIP_PATH ($SIZE)"
