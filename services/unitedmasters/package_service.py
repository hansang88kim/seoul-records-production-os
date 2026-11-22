"""
services/unitedmasters/package_service.py — UnitedMasters package builder (v0.9.0).

Builds a manual-upload distribution package from the Video Renderer playlist
order + streaming cover. MP3 goes in audio_mp3_reference (source/YouTube audio).
WAV/FLAC masters are copied into audio_distribution_master ONLY when actually
provided. NO fake WAV. Source MP3s and Video Renderer files are never modified
or deleted.
"""
from __future__ import annotations

import csv
import json
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from services.unitedmasters import track_builder as TB
from services.unitedmasters import cover_validator as CV


UPLOAD_GUIDE = Path(__file__).resolve().parents[2] / "docs" / "unitedmasters_distribution_package.md"


def _packages_root() -> Path:
    d = Path(__file__).resolve().parent.parent.parent / "outputs" / "unitedmasters_package"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _new_package_id() -> str:
    return (datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            + "_" + uuid.uuid4().hex[:6])


def default_release_metadata(release_title: str = "", artist: str = "Seoul Records") -> dict:
    """Sensible defaults for the release metadata form."""
    return {
        "artist_name": artist,
        "release_title": release_title or "Korea CityPop Playlist Vol.1",
        "release_version": "",
        "primary_genre": "City Pop",
        "secondary_genre": "",
        "language": "Korean",
        "label_name": "Seoul Records",
        "copyright_year": datetime.now(timezone.utc).year,
        "copyright_owner": "Seoul Records",
        "publishing_owner": "Seoul Records",
        "release_date_desired": "",
        "explicit_content": False,
        "previously_released": False,
        "upc": "",
        "credits": {"songwriter": "", "composer": "", "producer": ""},
    }


def create_package(playlist_plan: dict,
                   cover_path: str,
                   release_metadata: dict | None = None,
                   master_overrides: dict | None = None,
                   allow_mp3_only_draft: bool = True,
                   *,
                   title_overrides: dict | None = None) -> dict:
    """
    Build the UnitedMasters package on disk. Returns the package_manifest dict.

    - MP3 copied to audio_mp3_reference/NN_title.mp3 (source audio).
    - WAV/FLAC copied to audio_distribution_master/NN_title.ext ONLY if provided.
    - cover copied into cover/ (+ cover_upload_ready).
    - distribution_ready means every track has a verified master and the cover is prepared.
    """
    package_id = _new_package_id()
    pkg = _packages_root() / package_id
    (pkg / "cover").mkdir(parents=True, exist_ok=True)
    (pkg / "audio_mp3_reference").mkdir(parents=True, exist_ok=True)
    (pkg / "audio_distribution_master").mkdir(parents=True, exist_ok=True)
    (pkg / "metadata").mkdir(parents=True, exist_ok=True)

    meta = release_metadata or default_release_metadata()
    tracks = TB.build_tracklist(playlist_plan, master_overrides, title_overrides)

    # ── Copy MP3 references + any provided masters ───────────────────────
    for t in tracks:
        safe_title = "".join(ch for ch in t["title"] if ch not in '\\/:*?"<>|').strip()
        mp3_src = Path(t["mp3_path"]) if t.get("mp3_path") else None
        if mp3_src and mp3_src.exists():
            dest = pkg / "audio_mp3_reference" / f"{t['track_no']}_{safe_title}.mp3"
            shutil.copy2(mp3_src, dest)
            t["packaged_mp3"] = str(dest)
        # Distribution master ONLY if a real WAV/FLAC exists (never fabricated)
        if t.get("master_path") and Path(t["master_path"]).exists():
            ext = Path(t["master_path"]).suffix.lower()
            dest = pkg / "audio_distribution_master" / f"{t['track_no']}_{safe_title}{ext}"
            shutil.copy2(t["master_path"], dest)
            t["packaged_master"] = str(dest)

    # ── Cover ────────────────────────────────────────────────────────────
    packaged_cover = None
    upload_ready_cover = None
    if cover_path and Path(cover_path).is_file() and Path(cover_path).suffix.lower() in CV.IMAGE_EXTS:
        ext = Path(cover_path).suffix.lower()
        packaged_cover = pkg / "cover" / f"streaming_cover_1x1{ext}"
        shutil.copy2(cover_path, packaged_cover)
        upload_ready_cover = CV.make_upload_ready_cover(cover_path, str(pkg / "cover"))
    cover_result = CV.validate_cover(upload_ready_cover or cover_path)

    # ── Distribution readiness ───────────────────────────────────────────
    masters_ready = TB.tracklist_distribution_ready(tracks)
    distribution_ready = masters_ready and bool(upload_ready_cover and cover_result["ok_for_distribution"])
    mp3_only = bool(tracks) and all(t["source_audio_mp3"] and not t["master_path"] for t in tracks)

    warnings = []
    if mp3_only:
        warnings.append("MP3-only 패키지입니다 — 실제 배포에는 WAV/FLAC 마스터가 필요합니다.")
    warnings.extend(f"{t['track_no']}. {t['title']} · {warning}"
                    for t in tracks for warning in t["warnings"])
    if cover_result.get("warnings"):
        warnings.extend(cover_result["warnings"])

    status = ("Distribution Ready" if distribution_ready
              else ("MP3-only Warning" if mp3_only else "Draft Package"))

    # ── Tracklist CSV / JSON ─────────────────────────────────────────────
    _write_tracklist_csv(pkg / "tracklist.csv", tracks)
    (pkg / "tracklist.json").write_text(
        json.dumps(tracks, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── release_metadata.json ────────────────────────────────────────────
    release_meta_full = dict(meta)
    release_meta_full["release_type"] = "Re-Release" if meta.get("previously_released") else "New Release"
    release_meta_full["track_count"] = len(tracks)
    release_meta_full["tracks"] = [
        {"order": t["order"], "track_no": t["track_no"], "title": t["title"],
         "duration_sec": t["duration_sec"], "distribution_ready": t["distribution_ready"],
         "source_file": Path(t["packaged_master"]).name if t.get("packaged_master") else "",
         "audio_format": t["master_audio"]}
        for t in tracks
    ]
    (pkg / "release_metadata.json").write_text(
        json.dumps(release_meta_full, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── metadata/ docs ───────────────────────────────────────────────────
    _write_metadata_docs(pkg / "metadata", meta, tracks, status, masters_ready,
                         cover_result["ok_for_distribution"] and bool(upload_ready_cover))

    # ── package_manifest.json ────────────────────────────────────────────
    manifest = {
        "package_id": package_id,
        "package_dir": str(pkg),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "release_title": meta.get("release_title", ""),
        "artist_name": meta.get("artist_name", ""),
        "track_count": len(tracks),
        "status": status,
        "distribution_ready": distribution_ready,
        "audio_masters_ready": masters_ready,
        "mp3_only": mp3_only,
        "cover_path": str(packaged_cover) if packaged_cover else None,
        "cover_upload_ready": upload_ready_cover,
        "cover_status": cover_result.get("status"),
        "tracklist_csv": str(pkg / "tracklist.csv"),
        "tracklist_json": str(pkg / "tracklist.json"),
        "release_metadata_json": str(pkg / "release_metadata.json"),
        "warnings": warnings,
    }
    (pkg / "package_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _write_tracklist_csv(path: Path, tracks: list[dict]):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["order", "track_no", "title", "duration_sec",
                    "mp3_path", "master_path", "distribution_ready", "source_file"])
        for t in tracks:
            w.writerow([t["order"], t["track_no"], t["title"], t["duration_sec"],
                        t.get("mp3_path", ""), t.get("master_path") or "",
                        t["distribution_ready"],
                        Path(t["packaged_master"]).name if t.get("packaged_master") else ""])


def _write_metadata_docs(mdir: Path, meta: dict, tracks: list[dict],
                         status: str, masters_ready: bool, cover_ready: bool):
    # release_notes.txt
    (mdir / "release_notes.txt").write_text(
        f"{meta.get('release_title','')}\n{meta.get('artist_name','')} · "
        f"{meta.get('label_name','')}\n장르: {meta.get('primary_genre','')}\n"
        f"트랙 수: {len(tracks)}\n상태: {status}\n", encoding="utf-8")

    # credits.csv
    with (mdir / "credits.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["track_no", "title", "songwriter", "composer", "producer"])
        cr = meta.get("credits", {})
        for t in tracks:
            w.writerow([t["track_no"], t["title"], cr.get("songwriter", ""),
                        cr.get("composer", ""), cr.get("producer", "")])

    # rights_checklist.md
    (mdir / "rights_checklist.md").write_text(
        "# Rights / Copyright Checklist\n\n"
        "- [ ] 모든 트랙과 커버의 사용 권리 및 필요한 증빙을 확인했습니다.\n"
        "- [ ] 각 곡의 제3자 샘플·비트·녹음과 커버의 제3자 소재를 사실대로 표시했습니다.\n"
        "- [ ] 커버와 음원의 AI 사용을 확인하고 해당 항목에 표시했습니다.\n"
        f"- [ ] Copyright: {meta.get('copyright_year','')} {meta.get('copyright_owner','')}\n"
        f"- [ ] Publishing: {meta.get('publishing_owner','')}\n"
        "- [ ] Explicit 여부 확인\n", encoding="utf-8")

    # upload_instructions.md
    shutil.copyfile(UPLOAD_GUIDE, mdir / "upload_instructions.md")

    # unitedmasters_manual_upload_checklist.md
    master_line = f"- [{'x' if masters_ready else ' '}] 곡별 원본 WAV/FLAC {len(tracks)}개 검증"
    cover_line = f"- [{'x' if cover_ready else ' '}] 1:1 업로드용 커버 생성"
    (mdir / "unitedmasters_manual_upload_checklist.md").write_text(
        "# UnitedMasters 업로드 체크리스트\n\n"
        f"{master_line}\n{cover_line}\n"
        "- [ ] Music에서 Seoul Records 아티스트와 기존 초안을 확인했습니다.\n"
        "- [ ] Release Details, 커버 미리보기, Draft Auto-Saved를 확인했습니다.\n"
        "- [ ] 직접 제작한 커버는 No – I own the artwork를 선택했습니다. "
        "제3자 소재가 있으면 Yes – I’ll upload a license와 실제 증빙을 사용했습니다.\n"
        "- [ ] AI used in cover art를 제작 사실에 맞게 표시했습니다.\n"
        f"- [ ] Source File {len(tracks)}개의 순서·파일명·길이를 tracklist.csv와 대조했습니다.\n"
        "- [ ] 곡별 정확한 제목, 작사·작곡자와 추가 크레딧, Explicit, Radio Edit, 가사, "
        "제3자 음원 및 재발매의 기존 ISRC를 확인했습니다.\n"
        "- [ ] 합의된 Split Pay와 발매일을 확인했습니다.\n"
        "- [ ] 권리·증빙·최종 확인 항목을 검토하고 승인 후 웹에서 Submit했습니다.\n"
        "- [ ] Music에서 심사 상태와 링크를 기록했습니다. Live 상태는 공개 시 확인합니다.\n",
        encoding="utf-8")


def build_manual_upload_zip(package_dir: str) -> str | None:
    """Zip the package folder into manual_upload_package.zip (no deletion)."""
    pkg = Path(package_dir)
    if not pkg.is_dir():
        return None
    zip_path = pkg / "manual_upload_package.zip"
    with NamedTemporaryFile(dir=pkg.parent, suffix=".zip", delete=False) as temp:
        temp_path = Path(temp.name)
    try:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(pkg.rglob("*")):
                if file.is_file() and file != zip_path:
                    archive.write(file, file.relative_to(pkg))
        temp_path.replace(zip_path)
    finally:
        temp_path.unlink(missing_ok=True)
    return str(zip_path)


def list_packages(limit: int = 20) -> list[dict]:
    root = _packages_root()
    out = []
    if not root.exists():
        return []
    for d in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        mf = d / "package_manifest.json"
        if mf.exists():
            try:
                out.append(json.loads(mf.read_text(encoding="utf-8")))
            except Exception:
                pass
        if len(out) >= limit:
            break
    return out


UNITEDMASTERS_URL = "https://unitedmasters.com/"
