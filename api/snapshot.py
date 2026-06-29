"""
api/snapshot.py — sanitized dashboard snapshot for the Next.js console (v1.0.0).

Builds the same JSON shape the frontend types expect (frontend/lib/types.ts) by
reusing the existing Python services (production_scanner / checklist,
supervisor, job stores). Everything here is READ-ONLY and SANITIZED — no token,
cookie, key, or client_secret is ever included. There is no business logic
duplicated; this is a thin sanitized adapter.

This module is intentionally framework-free (no FastAPI/Flask dependency). It
can be called directly or wrapped by any HTTP layer later; build_snapshot()
returns a plain dict that is JSON-serializable and secret-free.
"""
from __future__ import annotations

from datetime import datetime, timezone

from services.security.redaction import redact_dict


def _production_qa() -> dict:
    try:
        from services.production.production_checklist import build_checklist
        cl = build_checklist()
        # Convert checklist items to the frontend shape (no secrets present)
        groups = {
            group: [
                {"key": it["key"], "label": it["label"], "status": it["status"],
                 "optional": it["optional"], "blocker": it["blocker"],
                 "detail": it.get("detail", "")}
                for it in items
            ]
            for group, items in cl["groups"].items()
        }
        return {
            "overall_readiness": cl["overall_readiness"],
            "scores": cl["scores"],
            "next_action": cl["next_action"],
            "warnings": cl["warnings"],
            "groups": groups,
        }
    except Exception:
        return {"overall_readiness": 0, "scores": {}, "next_action": "",
                "warnings": [], "groups": {}}


def _remote_control() -> dict:
    try:
        from services.remote_control import security as SEC
        from services.remote_control import supervisor as SUP
        cfg = SEC.public_config_summary()  # booleans + count only (no secrets)
        st = SUP.load_status()
        return {
            "supervisor": {
                "status": st.get("status", "stopped"),
                "streamlit_running": st.get("streamlit_running", False),
                "streamlit_http_status": st.get("streamlit_http_status"),
                "last_health_check_at": st.get("last_health_check_at"),
                "restart_count_last_hour": st.get("restart_count_last_hour", 0),
            },
            "telegram_enabled": cfg["telegram_enabled"],
            "telegram_package_installed": cfg.get("telegram_package_installed", False),
            "allowed_chat_id_count": cfg["allowed_chat_id_count"],
            "tailscale_status": st.get("tailscale_status"),
        }
    except Exception:
        return {
            "supervisor": {"status": "stopped", "streamlit_running": False,
                           "streamlit_http_status": None,
                           "last_health_check_at": None,
                           "restart_count_last_hour": 0},
            "telegram_enabled": False, "telegram_package_installed": False,
            "allowed_chat_id_count": 0, "tailscale_status": None,
        }


def _active_jobs() -> list[dict]:
    jobs = []
    try:
        from services.remote_control.supervisor import active_jobs_summary
        summ = active_jobs_summary()
        # Map the supervisor summary into the frontend ActiveJob shape
        vr = summ.get("video_render", "idle")
        jobs.append({"id": "video_render", "kind": "video_render",
                     "status": "rendering" if "running" in str(vr) else "idle",
                     "progress_percent": _pct(vr), "label": "Video Render"})
        jobs.append({"id": "youtube_upload", "kind": "youtube_upload",
                     "status": summ.get("youtube_upload", "idle")
                     if summ.get("youtube_upload") in ("uploading", "queued") else "idle",
                     "progress_percent": 0, "label": "YouTube Upload"})
    except Exception:
        pass
    return jobs


def _pct(text) -> float:
    import re
    m = re.search(r"(\d+)", str(text))
    return float(m.group(1)) if m else 0.0


def build_snapshot() -> dict:
    """Return the full sanitized dashboard snapshot (JSON-serializable, no secrets)."""
    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "active_jobs": _active_jobs(),
        "latest_songs": [],   # populated by a song scanner in a later phase
        "latest_renders": [],
        "production_qa": _production_qa(),
        "remote_control": _remote_control(),
    }
    # Defense in depth: scrub the whole structure before returning.
    return redact_dict(snapshot)


def snapshot_json() -> str:
    import json
    return json.dumps(build_snapshot(), ensure_ascii=False)
