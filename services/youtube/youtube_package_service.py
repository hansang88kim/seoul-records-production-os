"""
services/youtube/youtube_package_service.py — Package orchestration (v0.8.0).

Creates outputs/youtube_package/<package_id>/ and writes all metadata files,
the upload checklist, the upload payload, the manifest, validates the
thumbnail, and optionally builds manual_upload_package.zip.

Does NOT call the real YouTube API. Upload (mock by default) is a separate,
explicit step.
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from services.youtube import metadata_generator as MG
from services.youtube import thumbnail_validator as TV
from services.youtube import upload_payload_service as UP


UPLOAD_MODE_MANUAL = "manual_package_only"
UPLOAD_MODE_API_PRIVATE = "api_private"
UPLOAD_MODE_API_UNLISTED = "api_unlisted"
UPLOAD_MODE_PUBLIC = "public"

DEFAULT_UPLOAD_MODE = UPLOAD_MODE_MANUAL


def _packages_root() -> Path:
    d = Path(__file__).resolve().parent.parent.parent / "outputs" / "youtube_package"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _new_package_id() -> str:
    return (datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            + "_" + uuid.uuid4().hex[:6])


def create_package(
    video_path: str,
    thumbnail_path: str,
    chapters_path: str,
    playlist_title: str = "",
    country: str = "",
    volume: int = 1,
    mood: str = "",
    duration_min: int = 60,
    upload_mode: str = DEFAULT_UPLOAD_MODE,
    metadata_override: dict | None = None,
) -> dict:
    """
    Build a full YouTube upload package on disk.

    Returns the package_manifest dict (also saved as package_manifest.json).
    """
    package_id = _new_package_id()
    pkg_dir = _packages_root() / package_id
    pkg_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []

    # ── Metadata ─────────────────────────────────────────────────────
    if metadata_override:
        meta = metadata_override
    else:
        meta = MG.generate_all_metadata(
            playlist_title, country, volume, mood, chapters_path, duration_min)

    title = meta["title"]
    description = meta["description"]
    tags = meta["tags"]
    hashtags = meta["hashtags"]
    pinned = meta["pinned_comment"]
    chapters = meta.get("chapters", [])
    chapters_section = meta.get("chapters_section", "")

    # Write metadata text files
    (pkg_dir / "title.txt").write_text(title, encoding="utf-8")
    (pkg_dir / "description.txt").write_text(description, encoding="utf-8")
    (pkg_dir / "tags.txt").write_text("\n".join(tags), encoding="utf-8")
    (pkg_dir / "hashtags.txt").write_text(" ".join(hashtags), encoding="utf-8")
    (pkg_dir / "pinned_comment.txt").write_text(pinned, encoding="utf-8")

    # Chapters (preserve exact timestamps/order; copy-ready)
    chapters_youtube = chapters_section or _chapters_passthrough(chapters_path)
    (pkg_dir / "chapters_youtube.txt").write_text(chapters_youtube, encoding="utf-8")

    # ── Video reference ──────────────────────────────────────────────
    video_exists = bool(video_path and Path(video_path).exists())
    if not video_exists:
        warnings.append("final_video.mp4를 찾을 수 없습니다.")
    video_ref = {
        "video_path": video_path,
        "exists": video_exists,
        "size_mb": round(Path(video_path).stat().st_size / (1024 * 1024), 2)
        if video_exists else 0.0,
    }
    (pkg_dir / "selected_video_reference.json").write_text(
        json.dumps(video_ref, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── Thumbnail validation + upload-ready ──────────────────────────
    thumb_result = TV.validate_thumbnail(thumbnail_path, str(pkg_dir))
    thumbnail_original_path = None
    thumbnail_upload_ready_path = thumb_result.get("upload_ready_path")

    # Keep an explicit copy of the original (do not overwrite source)
    if thumbnail_path and Path(thumbnail_path).exists():
        ext = Path(thumbnail_path).suffix.lower()
        orig_copy = pkg_dir / f"thumbnail_original{ext}"
        try:
            shutil.copy2(thumbnail_path, orig_copy)
            thumbnail_original_path = str(orig_copy)
        except Exception:
            thumbnail_original_path = thumbnail_path
    if thumb_result.get("warnings"):
        warnings.extend(thumb_result["warnings"])

    # ── Upload payload (privacy default private) ─────────────────────
    payload = UP.build_upload_payload(title, description, tags,
                                      privacy_status=UP.DEFAULT_PRIVACY)
    UP.save_upload_payload(str(pkg_dir), payload)

    # ── Upload checklist ─────────────────────────────────────────────
    checklist_md = _build_checklist(
        video_exists, video_ref, thumb_result, title, description,
        bool(chapters), bool(tags), bool(pinned), upload_mode)
    (pkg_dir / "upload_checklist.md").write_text(checklist_md, encoding="utf-8")

    # ── Manifest ─────────────────────────────────────────────────────
    manifest = {
        "package_id": package_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "video_path": video_path,
        "thumbnail_original_path": thumbnail_original_path,
        "thumbnail_upload_ready_path": thumbnail_upload_ready_path,
        "chapters_path": chapters_path,
        "title": title,
        "description_path": str(pkg_dir / "description.txt"),
        "tags": tags,
        "hashtags": hashtags,
        "privacy_status_default": UP.DEFAULT_PRIVACY,
        "upload_mode": upload_mode,
        "status": "ready" if video_exists else "incomplete",
        "thumbnail_status": thumb_result.get("status"),
        "warnings": warnings,
        "package_dir": str(pkg_dir),
    }
    (pkg_dir / "package_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return manifest


def _chapters_passthrough(chapters_path: str) -> str:
    """Return chapters.txt content verbatim (preserve timestamps/order)."""
    p = Path(chapters_path) if chapters_path else None
    if p and p.exists():
        return p.read_text(encoding="utf-8")
    return ""


def _build_checklist(video_exists, video_ref, thumb_result, title, description,
                     has_chapters, has_tags, has_pinned, upload_mode) -> str:
    """Build upload_checklist.md with status badges."""
    def badge(ok):
        return "✅" if ok else "⬜"

    thumb_ready = thumb_result.get("status") in (TV.STATUS_READY, TV.STATUS_COMPRESSED)
    thumb_size_ok = (thumb_result.get("upload_ready_size_mb") or 99) <= 2.0
    thumb_aspect = thumb_result.get("aspect_ok", False)

    lines = [
        "# YouTube 업로드 체크리스트",
        "",
        f"{badge(video_exists)} final_video.mp4 존재",
        f"{badge(video_ref.get('exists') and video_ref.get('size_mb', 0) > 0)} 영상 파일 확인 ({video_ref.get('size_mb', 0)}MB)",
        f"{badge(thumb_aspect)} 썸네일 16:9",
        f"{badge(thumb_size_ok)} 썸네일 업로드본 ≤ 2MB",
        f"{badge(bool(title))} 제목 생성됨",
        f"{badge(bool(description))} 설명 생성됨",
        f"{badge(has_chapters)} 챕터 포함",
        f"{badge(has_tags)} 태그 생성됨",
        f"{badge(has_pinned)} 고정 댓글 생성됨",
        "⬜ 영상 수동 검토 (사용자 확인 필요)",
        "⬜ 오디오/영상 싱크 확인 (사용자 확인 필요)",
        "⬜ 저작권/권리 검토 (사용자 확인 필요)",
        f"{badge(bool(upload_mode))} 업로드 모드 선택됨: {upload_mode}",
        "✅ 기본 공개 범위: private (안전)",
        "",
        "> 업로드 전 반드시 영상을 직접 검토하고 저작권을 확인하세요.",
    ]
    return "\n".join(lines)


def build_manual_package_zip(package_dir: str) -> str | None:
    """
    Zip the package folder into manual_upload_package.zip (inside the same
    folder). Never deletes anything. Returns the zip path.
    """
    pkg = Path(package_dir)
    if not pkg.exists():
        return None
    zip_base = pkg / "manual_upload_package"
    # Zip everything except an existing zip of the same name
    tmp_dir = pkg.parent / f"_tmp_{pkg.name}"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    shutil.copytree(pkg, tmp_dir, ignore=shutil.ignore_patterns(
        "manual_upload_package.zip"))
    try:
        shutil.make_archive(str(zip_base), "zip", tmp_dir)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    zip_path = str(zip_base) + ".zip"
    return zip_path if Path(zip_path).exists() else None


def list_packages(limit: int = 20) -> list[dict]:
    """List recent packages (most recent first)."""
    root = _packages_root()
    if not root.exists():
        return []
    pkgs = []
    for d in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if d.is_dir():
            mf = d / "package_manifest.json"
            if mf.exists():
                try:
                    pkgs.append(json.loads(mf.read_text(encoding="utf-8")))
                except Exception:
                    pass
            if len(pkgs) >= limit:
                break
    return pkgs
