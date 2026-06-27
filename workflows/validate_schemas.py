"""
validate_schemas.py — validates project manifests and preset JSON files against schemas.

Used in CI and as a project health check.
Implements its own minimal JSON Schema validator to avoid external dependencies.
"""

from __future__ import annotations
import json
import os
import sys
from typing import Any


# ---------------------------------------------------------------------------
# Minimal JSON Schema validator (subset: required, type, properties)
# ---------------------------------------------------------------------------

def _validate(instance: Any, schema: dict, path: str = "#") -> list[str]:
    """Recursively validate `instance` against `schema`. Returns list of errors."""
    errors: list[str] = []
    schema_type = schema.get("type")

    if schema_type:
        type_map = {
            "object": dict,
            "array": list,
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "null": type(None),
        }
        expected = type_map.get(schema_type)
        if expected and not isinstance(instance, expected):
            errors.append(f"{path}: expected type {schema_type}, got {type(instance).__name__}")
            return errors

    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                errors.append(f"{path}: missing required property '{req}'")
        props = schema.get("properties", {})
        for key, sub_schema in props.items():
            if key in instance:
                errors.extend(_validate(instance[key], sub_schema, path=f"{path}/{key}"))

    elif isinstance(instance, list):
        items_schema = schema.get("items")
        if items_schema:
            for i, item in enumerate(instance):
                errors.extend(_validate(item, items_schema, path=f"{path}[{i}]"))

    return errors


def validate_json_file(json_path: str, schema_path: str) -> tuple[bool, list[str]]:
    """
    Validate a JSON file against a schema file.

    Returns (ok, errors).
    """
    if not os.path.exists(json_path):
        return False, [f"File not found: {json_path}"]
    if not os.path.exists(schema_path):
        return False, [f"Schema not found: {schema_path}"]

    try:
        with open(json_path, encoding="utf-8") as f:
            instance = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON in {json_path}: {e}"]

    try:
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON schema in {schema_path}: {e}"]

    errors = _validate(instance, schema)
    return (len(errors) == 0), errors


def validate_project(project_dir: str, schemas_dir: str) -> dict:
    """
    Validate all manifest files in a project directory.

    Returns dict with overall ok status and per-file results.
    """
    manifest_path = os.path.join(project_dir, "project_manifest.json")
    schema_path = os.path.join(schemas_dir, "project_manifest.schema.json")

    ok, errors = validate_json_file(manifest_path, schema_path)
    return {
        "ok": ok,
        "manifest": {
            "path": manifest_path,
            "ok": ok,
            "errors": errors,
        },
    }


def validate_all_presets(presets_dir: str) -> dict:
    """Validate that all JSON files in the presets directory are valid JSON."""
    results = {}
    for root, _, files in os.walk(presets_dir):
        for file in files:
            if not file.endswith(".json"):
                continue
            path = os.path.join(root, file)
            try:
                with open(path, encoding="utf-8") as f:
                    json.load(f)
                results[path] = {"ok": True}
            except json.JSONDecodeError as e:
                results[path] = {"ok": False, "error": str(e)}
    return results


def run(project_root: str) -> dict:
    """
    Run all schema validations for a project root.

    Returns overall result dict.
    """
    schemas_dir = os.path.join(project_root, "templates")
    presets_dir = os.path.join(project_root, "presets")
    outputs_dir = os.path.join(project_root, "outputs")

    results: dict = {"schemas_dir": schemas_dir, "projects": {}, "presets": {}}

    # Validate all project output manifests
    if os.path.isdir(outputs_dir):
        for entry in os.listdir(outputs_dir):
            proj_dir = os.path.join(outputs_dir, entry)
            manifest = os.path.join(proj_dir, "project_manifest.json")
            if os.path.isfile(manifest):
                results["projects"][entry] = validate_project(proj_dir, schemas_dir)

    # Validate presets
    if os.path.isdir(presets_dir):
        results["presets"] = validate_all_presets(presets_dir)

    all_ok = all(v.get("ok", True) for v in results["presets"].values())
    all_ok = all_ok and all(
        v.get("ok", True) for v in results["projects"].values()
    )
    results["all_ok"] = all_ok
    return results


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    result = run(root)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("all_ok", True) else 1)
