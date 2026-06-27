#!/usr/bin/env python3
"""CI helper: validate all JSON files under presets/."""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
failed = False
for f in sorted(root.glob("presets/**/*.json")):
    try:
        json.loads(f.read_text(encoding="utf-8"))
        print(f"OK: {f.relative_to(root)}")
    except Exception as e:
        print(f"FAIL: {f.relative_to(root)}: {e}")
        failed = True

if failed:
    sys.exit(1)
print("All preset JSON files valid.")
