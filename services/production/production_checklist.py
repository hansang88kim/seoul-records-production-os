"""
services/production/production_checklist.py — QA checklist + next action (v0.8.4).

Turns a production scan into grouped checklist items, warnings, readiness
scores, a single "next recommended action", and an exportable report. Secrets
are never read or written here.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from services.production import production_status_models as M
from services.production import production_scanner as scanner

# Pilot render sequence (status-aware guide)
PILOT_SEQUENCE = [
    ("30초 preview", "preview_30s.mp4", "Video Renderer"),
    ("3분 test render", "final_video.mp4 (3분)", "Video Renderer"),
    ("10분 test render", "final_video.mp4 (10분)", "Video Renderer"),
    ("60분 full render", "final_video.mp4", "Video Renderer"),
    ("YouTube package 생성", "manual_upload_package.zip", "YouTube Package"),
    ("수동/Private 업로드", "upload_result.json", "YouTube Package"),
]


def _st(present, *, optional=False, blocker=False, completed=False):
    if completed:
        return M.STATUS_COMPLETED
    if present:
        return M.STATUS_READY
    if optional:
        return M.STATUS_OPTIONAL
    if blocker:
        return M.STATUS_MISSING
    return M.STATUS_WARNING


def build_checklist(snapshot: dict | None = None) -> dict:
    """Build the full grouped checklist + scores + warnings + next action."""
    snap = snapshot or scanner.scan_all()
    songs = snap["songs"]
    thumbs = snap["thumbnails"]
    overlays = snap["overlays"]
    video = snap["video"]
    pkg = snap["youtube_package"]
    upload = snap["upload"]

    # ── Songs ────────────────────────────────────────────────────────────
    song_items = [
        M.make_item("mp3_found", f"MP3 파일 ({songs['mp3_count']}개)",
                    _st(songs["mp3_count"] > 0, blocker=True),
                    blocker=True, detail=f"{songs['mp3_count']}개 발견"),
        M.make_item("mp3_duration",
                    f"총 길이 {int(songs['total_duration_sec'])//60}분",
                    M.STATUS_READY if songs["total_duration_sec"] >= 180
                    else (M.STATUS_WARNING if songs["mp3_count"] else M.STATUS_MISSING),
                    detail=f"{songs['total_duration_sec']}초"),
    ]

    # ── Thumbnail assets ─────────────────────────────────────────────────
    thumb_items = [
        M.make_item("youtube_thumbnail", "YouTube Thumbnail 16:9",
                    _st(thumbs["youtube_thumbnail"], blocker=True),
                    blocker=True, path=thumbs["youtube_thumbnail"]),
        M.make_item("video_background", "Video Playback Background 16:9",
                    _st(thumbs["video_playback_background"]),
                    path=thumbs["video_playback_background"],
                    detail="없으면 썸네일이 배경으로 쓰여 제목이 겹칠 수 있음"),
        M.make_item("streaming_cover", "Streaming Cover 1:1",
                    _st(thumbs["streaming_cover"], optional=True),
                    optional=True, path=thumbs["streaming_cover"]),
        M.make_item("asset_manifest", "asset_manifest.json",
                    _st(thumbs["asset_manifest"], optional=True),
                    optional=True, path=thumbs["asset_manifest"]),
    ]

    # ── Canva overlays (all optional) ────────────────────────────────────
    overlay_items = [
        M.make_item("cta_sticker", "CTA 스티커 PNG",
                    _st(overlays["cta_sticker"], optional=True),
                    optional=True, path=overlays["cta_sticker"]),
        M.make_item("now_playing", f"Now Playing 카드 ({overlays['now_playing_count']}개)",
                    _st(overlays["now_playing_count"] > 0, optional=True),
                    optional=True),
        M.make_item("visualizer_frame", "비주얼라이저 프레임 PNG",
                    _st(overlays["visualizer_frame"], optional=True),
                    optional=True, path=overlays["visualizer_frame"]),
        M.make_item("center_title", "중앙 타이틀 PNG (선택)",
                    _st(overlays["center_title"], optional=True),
                    optional=True, path=overlays["center_title"]),
    ]

    # ── Video render ─────────────────────────────────────────────────────
    video_items = [
        M.make_item("preview_30s", "30초 preview",
                    _st(video["preview_30s"]), path=video["preview_30s"]),
        M.make_item("final_video", "final_video.mp4",
                    _st(video["final_video"], blocker=True,
                        completed=bool(video["final_video"]) and video["render_completed"]),
                    blocker=True, path=video["final_video"]),
        M.make_item("chapters", "chapters.txt",
                    _st(video["chapters"]), path=video["chapters"]),
        M.make_item("playlist_plan", "playlist_plan.json",
                    _st(video["playlist_plan"]), path=video["playlist_plan"]),
        M.make_item("render_plan", "render_plan.json",
                    _st(video["render_plan"]), path=video["render_plan"]),
        M.make_item("overlay_plan", "overlay_plan.json",
                    _st(video["overlay_plan"]), path=video["overlay_plan"]),
    ]

    # ── YouTube package ──────────────────────────────────────────────────
    pkg_items = [
        M.make_item("title", "title.txt", _st(pkg["title"]), path=pkg["title"]),
        M.make_item("description", "description.txt", _st(pkg["description"]), path=pkg["description"]),
        M.make_item("tags", "tags.txt", _st(pkg["tags"]), path=pkg["tags"]),
        M.make_item("hashtags", "hashtags.txt", _st(pkg["hashtags"]), path=pkg["hashtags"]),
        M.make_item("pinned_comment", "pinned_comment.txt", _st(pkg["pinned_comment"]), path=pkg["pinned_comment"]),
        M.make_item("thumbnail_upload_ready", "thumbnail_upload_ready",
                    _st(pkg["thumbnail_upload_ready"]), path=pkg["thumbnail_upload_ready"]),
        M.make_item("manual_zip", "manual_upload_package.zip",
                    _st(pkg["manual_upload_package_zip"], optional=True),
                    optional=True, path=pkg["manual_upload_package_zip"]),
        M.make_item("payload", "youtube_upload_payload.json",
                    _st(pkg["youtube_upload_payload"]), path=pkg["youtube_upload_payload"]),
    ]

    # ── Upload readiness ─────────────────────────────────────────────────
    upload_items = [
        M.make_item("manual_ready", "수동 패키지 준비",
                    _st(pkg["manual_upload_package_zip"] or pkg["package_manifest"], optional=True),
                    optional=True),
        M.make_item("api_deps", "API dependencies",
                    M.STATUS_READY if upload["api_dependencies_ready"] else M.STATUS_OPTIONAL,
                    optional=True,
                    detail=("설치됨" if upload["api_dependencies_ready"]
                            else "실제 업로드 시 필요: " + ", ".join(upload["api_dependencies_missing"]))),
        M.make_item("oauth", "OAuth 설정",
                    M.STATUS_READY if upload["oauth_configured"] else M.STATUS_OPTIONAL,
                    optional=True, detail=upload["oauth_status"]),
        M.make_item("upload_result", "upload_result.json (업로드됨)",
                    M.STATUS_COMPLETED if upload["upload_result"] else M.STATUS_OPTIONAL,
                    optional=True, path=upload["upload_result"]),
    ]

    # ── UnitedMasters distribution readiness ─────────────────────────────
    um = snap.get("unitedmasters", {})
    um_items = [
        M.make_item("um_package", "UnitedMasters 패키지",
                    _st(um.get("package_manifest"), optional=True),
                    optional=True, path=um.get("package_manifest")),
        M.make_item("um_cover", "Streaming Cover 1:1",
                    _st(thumbs["streaming_cover"], optional=True),
                    optional=True, path=thumbs["streaming_cover"]),
        M.make_item("um_master", "WAV/FLAC 배포 마스터",
                    M.STATUS_READY if um.get("has_wav_flac_master")
                    else M.STATUS_WARNING,
                    detail=("준비됨" if um.get("has_wav_flac_master")
                            else "MP3-only — 실제 배포에는 WAV/FLAC 마스터가 필요합니다")),
        M.make_item("um_checklist", "수동 업로드 체크리스트",
                    _st(um.get("manual_checklist"), optional=True),
                    optional=True, path=um.get("manual_checklist")),
        M.make_item("um_distribution_ready", "배포 준비 상태",
                    M.STATUS_COMPLETED if um.get("distribution_ready")
                    else (M.STATUS_WARNING if um.get("package_manifest") else M.STATUS_OPTIONAL),
                    optional=True,
                    detail=("Distribution Ready" if um.get("distribution_ready")
                            else "MP3-only는 배포 준비 상태가 아닙니다")),
    ]

    groups = {
        "Songs": song_items,
        "Thumbnail assets": thumb_items,
        "Canva overlays": overlay_items,
        "Video render": video_items,
        "YouTube package": pkg_items,
        "Upload readiness": upload_items,
        "UnitedMasters": um_items,
    }

    scores = {
        "song_readiness": M.group_score(song_items),
        "visual_readiness": M.group_score(thumb_items + overlay_items),
        "video_readiness": M.group_score(video_items),
        "youtube_package_readiness": M.group_score(pkg_items),
        "upload_readiness": M.group_score(upload_items),
        "unitedmasters_readiness": M.group_score(um_items),
    }
    overall = int(round(sum(scores.values()) / len(scores)))

    warnings = build_warnings(snap)
    next_action = recommend_next_action(snap)

    return {
        "groups": groups,
        "scores": scores,
        "overall_readiness": overall,
        "warnings": warnings,
        "next_action": next_action,
        "snapshot": snap,
    }


def build_warnings(snap: dict) -> list[dict]:
    """Asset warnings. Optional ones are level='optional'; blockers level='blocker'."""
    w = []
    thumbs = snap["thumbnails"]
    overlays = snap["overlays"]
    video = snap["video"]
    pkg = snap["youtube_package"]
    songs = snap["songs"]
    upload = snap["upload"]

    # Blockers
    if songs["mp3_count"] == 0:
        w.append({"level": "blocker", "message":
                  "MP3가 없습니다. Video Renderer를 쓰려면 먼저 Song Lab에서 곡을 생성하세요."})
    if not video["final_video"] and (pkg["title"] or pkg["package_manifest"]):
        w.append({"level": "blocker", "message":
                  "final_video.mp4가 없습니다. YouTube Package는 final_video가 있어야 합니다."})

    # Visual warnings
    if not thumbs["video_playback_background"] and thumbs["youtube_thumbnail"]:
        w.append({"level": "warning", "message":
                  "Video Playback Background가 없습니다. 썸네일을 배경으로 쓰면 중앙 타이틀이 겹칠 수 있습니다."})
    if not thumbs["video_playback_background"]:
        w.append({"level": "warning", "message": "video_playback_background_16x9가 없습니다."})
    if not thumbs["streaming_cover"]:
        w.append({"level": "optional", "message": "streaming_cover_1x1이 없습니다 (선택)."})
    if songs["mp3_count"] and songs["total_duration_sec"] < 180:
        w.append({"level": "warning", "message":
                  "MP3 총 길이가 짧습니다. 목표 길이까지 반복 재생 옵션을 고려하세요."})

    # Optional overlay warnings
    if not overlays["cta_sticker"]:
        w.append({"level": "optional", "message":
                  "CTA 스티커가 없습니다. 선택 사항이지만 브랜드 영상 품질 향상을 위해 권장됩니다."})
    if overlays["now_playing_count"] == 0:
        w.append({"level": "optional", "message": "Now Playing 카드가 없습니다 (선택)."})
    if not overlays["visualizer_frame"]:
        w.append({"level": "optional", "message": "비주얼라이저 프레임이 없습니다 (선택)."})

    # Render workflow
    if not video["preview_30s"] and not video["final_video"]:
        w.append({"level": "warning", "message":
                  "30초 preview가 없습니다. Full render 전에 preview를 먼저 생성하세요."})

    # Package / upload
    thumb_ready = pkg["thumbnail_upload_ready"]
    if not thumb_ready and thumbs["youtube_thumbnail"]:
        w.append({"level": "warning", "message":
                  "업로드용 썸네일(thumbnail_upload_ready)이 없습니다. 2MB 초과 시 압축본이 필요합니다."})
    if not upload["oauth_configured"]:
        w.append({"level": "optional", "message":
                  "OAuth 토큰이 없습니다. API 업로드를 하려면 인증이 필요합니다."})
    if not upload["api_dependencies_ready"]:
        w.append({"level": "optional", "message":
                  "API dependencies가 없습니다. 실제 업로드 시 pip install -r requirements.txt가 필요합니다."})

    # UnitedMasters distribution
    um = snap.get("unitedmasters", {})
    if um.get("package_manifest") and um.get("mp3_only") and not um.get("has_wav_flac_master"):
        w.append({"level": "warning", "message":
                  "UnitedMasters 패키지가 MP3-only입니다. 실제 배포에는 WAV/FLAC 마스터가 필요합니다."})

    return w


def recommend_next_action(snap: dict) -> str:
    """Return ONE short, practical next-step recommendation."""
    songs = snap["songs"]
    thumbs = snap["thumbnails"]
    video = snap["video"]
    pkg = snap["youtube_package"]
    upload = snap["upload"]

    if songs["mp3_count"] == 0:
        return "Song Lab에서 곡(MP3)을 먼저 생성하세요."
    if not thumbs["youtube_thumbnail"]:
        return "MP3는 준비되었지만 YouTube 썸네일이 없습니다. Thumbnail Studio에서 16:9 썸네일을 생성하세요."
    if not thumbs["video_playback_background"]:
        return "Video Playback Background가 없습니다. Thumbnail Studio에서 깨끗한 재생 배경을 내보내세요."
    if not video["preview_30s"] and not video["final_video"]:
        return "30초 preview가 없습니다. Full render 전에 Video Renderer에서 preview를 먼저 생성하세요."
    if not video["final_video"]:
        return "Preview를 확인했다면 Video Renderer에서 full render로 final_video.mp4를 생성하세요."
    if not pkg["package_manifest"] and not pkg["title"]:
        return "final_video.mp4는 준비됐지만 YouTube Package가 없습니다. YouTube Package 탭에서 패키지를 생성하세요."
    if pkg["package_manifest"] and not upload["upload_result"]:
        return "YouTube Package가 준비됐습니다. 수동 업로드 또는 Private Upload를 진행할 수 있습니다."
    return "모든 산출물이 준비되었습니다. YouTube Studio에서 최종 검토 후 공개하세요."


def pilot_sequence_status(snap: dict) -> list[dict]:
    """Status for each pilot step."""
    video = snap["video"]
    pkg = snap["youtube_package"]
    upload = snap["upload"]
    done = {
        "30초 preview": bool(video["preview_30s"]),
        "60분 full render": bool(video["final_video"]),
        "YouTube package 생성": bool(pkg["package_manifest"] or pkg["manual_upload_package_zip"]),
        "수동/Private 업로드": bool(upload["upload_result"]),
    }
    out = []
    for name, output, tab in PILOT_SEQUENCE:
        out.append({
            "step": name, "expected_output": output, "tab": tab,
            "status": M.STATUS_COMPLETED if done.get(name) else M.STATUS_NEEDS_REVIEW,
        })
    return out


# ─── Report export ───────────────────────────────────────────────────────────

def _reports_root() -> Path:
    d = Path(__file__).resolve().parent.parent.parent / "outputs" / "production_qa"
    d.mkdir(parents=True, exist_ok=True)
    return d


def export_report(checklist: dict | None = None) -> dict:
    """
    Write production_status.json / production_checklist.md / missing_assets.md /
    next_steps.md under outputs/production_qa/<report_id>/.
    Secrets are never read or included.
    """
    import uuid
    cl = checklist or build_checklist()
    report_id = (datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
                 + "_" + uuid.uuid4().hex[:6])
    d = _reports_root() / report_id
    d.mkdir(parents=True, exist_ok=True)

    # production_status.json (snapshot + scores + warnings; no secrets present)
    status = {
        "report_id": report_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "overall_readiness": cl["overall_readiness"],
        "scores": cl["scores"],
        "next_action": cl["next_action"],
        "warnings": cl["warnings"],
        "snapshot": cl["snapshot"],
    }
    (d / "production_status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    # production_checklist.md
    lines = [f"# Production QA Checklist", "",
             f"Overall readiness: **{cl['overall_readiness']}%**", "",
             f"Next action: {cl['next_action']}", ""]
    for group, items in cl["groups"].items():
        score = cl["scores"].get({
            "Songs": "song_readiness",
            "Thumbnail assets": "visual_readiness",
            "Video render": "video_readiness",
            "YouTube package": "youtube_package_readiness",
            "Upload readiness": "upload_readiness",
            "UnitedMasters": "unitedmasters_readiness",
        }.get(group, ""), "")
        lines.append(f"## {group}" + (f" ({score}%)" if score != "" else ""))
        for it in items:
            mark = {"Ready": "✅", "Completed": "✅", "Missing": "❌",
                    "Warning": "⚠️", "Optional": "▫️", "Needs Review": "🔎"}.get(it["status"], "•")
            lines.append(f"- {mark} {it['label']} — {it['status']}")
        lines.append("")
    (d / "production_checklist.md").write_text("\n".join(lines), encoding="utf-8")

    # missing_assets.md
    miss = ["# Missing / Warning Assets", ""]
    for w in cl["warnings"]:
        icon = {"blocker": "❌", "warning": "⚠️", "optional": "▫️"}.get(w["level"], "•")
        miss.append(f"- {icon} [{w['level']}] {w['message']}")
    (d / "missing_assets.md").write_text("\n".join(miss), encoding="utf-8")

    # next_steps.md
    steps = ["# Recommended Next Steps", "", f"➡️ {cl['next_action']}", "",
             "## Pilot render sequence", ""]
    for s in pilot_sequence_status(cl["snapshot"]):
        mark = "✅" if s["status"] == M.STATUS_COMPLETED else "🔎"
        steps.append(f"- {mark} {s['step']} → `{s['expected_output']}` ({s['tab']})")
    (d / "next_steps.md").write_text("\n".join(steps), encoding="utf-8")

    return {
        "report_id": report_id,
        "report_dir": str(d),
        "files": {
            "production_status": str(d / "production_status.json"),
            "production_checklist": str(d / "production_checklist.md"),
            "missing_assets": str(d / "missing_assets.md"),
            "next_steps": str(d / "next_steps.md"),
        },
    }
