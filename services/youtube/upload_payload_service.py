"""
services/youtube/upload_payload_service.py — YouTube upload payload (v0.8.0).

Builds youtube_upload_payload.json in the shape the YouTube Data API v3
videos.insert expects (snippet + status). Default privacyStatus is 'private'.
No secrets are ever included in the payload.
"""
from __future__ import annotations

import json
from pathlib import Path


VALID_PRIVACY = ("private", "unlisted", "public")
DEFAULT_PRIVACY = "private"

# YouTube category 10 = Music
MUSIC_CATEGORY_ID = "10"


def build_upload_payload(
    title: str,
    description: str,
    tags: list[str],
    privacy_status: str = DEFAULT_PRIVACY,
    category_id: str = MUSIC_CATEGORY_ID,
    made_for_kids: bool = False,
) -> dict:
    """
    Build the videos.insert request body. privacyStatus defaults to 'private'.
    """
    if privacy_status not in VALID_PRIVACY:
        privacy_status = DEFAULT_PRIVACY

    return {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": made_for_kids,
            "embeddable": True,
        },
    }


def save_upload_payload(out_dir: str, payload: dict) -> str:
    """Write youtube_upload_payload.json."""
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "youtube_upload_payload.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
