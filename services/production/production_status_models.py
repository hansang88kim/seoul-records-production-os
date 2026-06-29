"""
services/production/production_status_models.py — QA status vocabulary (v0.8.4).

Shared status labels + helpers for the Production QA readiness dashboard.
Plain dicts are used as the data model (no Pydantic dependency required here).
"""
from __future__ import annotations


# Status labels for a single checklist item
STATUS_MISSING = "Missing"
STATUS_READY = "Ready"
STATUS_WARNING = "Warning"
STATUS_OPTIONAL = "Optional"
STATUS_COMPLETED = "Completed"
STATUS_NEEDS_REVIEW = "Needs Review"

# Which statuses count as "good" toward a readiness score
_GOOD = {STATUS_READY, STATUS_COMPLETED}
# Optional/Warning don't block but also don't fully count
_PARTIAL = {STATUS_OPTIONAL, STATUS_WARNING, STATUS_NEEDS_REVIEW}


def make_item(key: str, label: str, status: str, *,
              optional: bool = False, blocker: bool = False,
              path: str | None = None, detail: str = "") -> dict:
    """Build one checklist item."""
    return {
        "key": key,
        "label": label,
        "status": status,
        "optional": optional,
        "blocker": blocker,
        "path": path,
        "detail": detail,
    }


def group_score(items: list[dict]) -> int:
    """
    Compute a 0-100 readiness score for a group. Required items count fully;
    optional items count as half weight. Missing required → drags the score.
    """
    if not items:
        return 0
    total_weight = 0.0
    got = 0.0
    for it in items:
        weight = 0.5 if it.get("optional") else 1.0
        total_weight += weight
        if it["status"] in _GOOD:
            got += weight
        elif it["status"] in _PARTIAL:
            got += weight * 0.5
    if total_weight == 0:
        return 0
    return int(round(got / total_weight * 100))


def has_blocker(items: list[dict]) -> bool:
    """True if any required item is Missing (a blocker)."""
    return any(it.get("blocker") and it["status"] == STATUS_MISSING for it in items)
