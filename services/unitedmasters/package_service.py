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
from datetime import datetime, timezone
from pathlib import Path

from services.unitedmasters import track_builder as TB
from services.unitedmasters import cover_validator as CV


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
                   allow_mp3_only_draft: bool = True) -> dict:
    """
    Build the UnitedMasters package on disk. Returns the package_manifest dict.

    - MP3 copied to audio_mp3_reference/NN_title.mp3 (source audio).
    - WAV/FLAC copied to audio_distribution_master/NN_title.ext ONLY if provided.
    - cover copied into cover/ (+ cover_upload_ready).
    - distribution_ready is True only if EVERY track has a valid master.
    """
    package_id = _new_package_id()
    pkg = _packages_root() / package_id
    (pkg / "cover").mkdir(parents=True, exist_ok=True)
    (pkg / "audio_mp3_reference").mkdir(parents=True, exist_ok=True)
    (pkg / "audio_distribution_master").mkdir(parents=True, exist_ok=True)
    (pkg / "metadata").mkdir(parents=True, exist_ok=True)

    meta = release_metadata or default_release_metadata()
    tracks = TB.build_tracklist(playlist_plan, master_overrides)

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
    cover_result = CV.validate_cover(cover_path)
    packaged_cover = None
    upload_ready_cover = None
    if cover_path and Path(cover_path).exists():
        ext = Path(cover_path).suffix.lower()
        packaged_cover = pkg / "cover" / f"streaming_cover_1x1{ext}"
        shutil.copy2(cover_path, packaged_cover)
        upload_ready_cover = CV.make_upload_ready_cover(cover_path, str(pkg / "cover"))

    # ── Distribution readiness ───────────────────────────────────────────
    distribution_ready = TB.tracklist_distribution_ready(tracks)
    mp3_only = (not distribution_ready) and all(t["source_audio_mp3"] for t in tracks)

    warnings = []
    if mp3_only:
        warnings.append("MP3-only 패키지입니다 — 실제 배포에는 WAV/FLAC 마스터가 필요합니다.")
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
    release_meta_full["track_count"] = len(tracks)
    release_meta_full["tracks"] = [
        {"order": t["order"], "track_no": t["track_no"], "title": t["title"],
         "duration_sec": t["duration_sec"], "distribution_ready": t["distribution_ready"]}
        for t in tracks
    ]
    (pkg / "release_metadata.json").write_text(
        json.dumps(release_meta_full, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── metadata/ docs ───────────────────────────────────────────────────
    _write_metadata_docs(pkg / "metadata", meta, tracks, status, distribution_ready)

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
                    "mp3_path", "master_path", "distribution_ready"])
        for t in tracks:
            w.writerow([t["order"], t["track_no"], t["title"], t["duration_sec"],
                        t.get("mp3_path", ""), t.get("master_path") or "",
                        t["distribution_ready"]])


def _write_metadata_docs(mdir: Path, meta: dict, tracks: list[dict],
                         status: str, distribution_ready: bool):
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
        "- [ ] 모든 트랙의 저작권 보유 확인\n"
        "- [ ] 샘플/서드파티 소스 없음 확인\n"
        f"- [ ] Copyright: {meta.get('copyright_year','')} {meta.get('copyright_owner','')}\n"
        f"- [ ] Publishing: {meta.get('publishing_owner','')}\n"
        "- [ ] Explicit 여부 확인\n", encoding="utf-8")

    # upload_instructions.md
    (mdir / "upload_instructions.md").write_text(
        "# UnitedMasters 업로드 안내\n\n"
        "1. UnitedMasters에 로그인\n2. 새 릴리스 생성\n"
        "3. release_metadata.json 값으로 메타데이터 입력\n"
        "4. cover/ 의 커버 업로드\n"
        "5. audio_distribution_master/ 의 WAV/FLAC를 01, 02 순서로 업로드\n"
        "   (WAV/FLAC가 없으면 먼저 마스터를 준비하세요 — MP3는 배포 마스터가 아닙니다)\n"
        "6. 트랙 제목/순서 확인\n7. 크레딧 입력\n8. 릴리스 날짜 선택\n"
        "9. 권리/저작권 검토\n10. 검토 제출\n", encoding="utf-8")

    # unitedmasters_manual_upload_checklist.md
    master_line = ("- [x] WAV/FLAC 마스터 준비됨" if distribution_ready
                   else "- [ ] WAV/FLAC 마스터 준비 필요 (현재 MP3만 있음)")
    (mdir / "unitedmasters_manual_upload_checklist.md").write_text(
        "# UnitedMasters Manual Upload Checklist\n\n"
        "- [ ] UnitedMasters 로그인\n- [ ] 새 릴리스 생성\n"
        "- [ ] 릴리스 메타데이터 입력\n- [ ] 커버 아트 업로드\n"
        f"{master_line}\n- [ ] 트랙을 01, 02, 03 순서로 업로드\n"
        "- [ ] 트랙 제목/순서 확인\n- [ ] 크레딧 추가\n"
        "- [ ] 릴리스 날짜 선택\n- [ ] 권리/저작권 검토\n- [ ] 검토 제출\n",
        encoding="utf-8")


def build_manual_upload_zip(package_dir: str) -> str | None:
    """Zip the package folder into manual_upload_package.zip (no deletion)."""
    pkg = Path(package_dir)
    if not pkg.exists():
        return None
    zip_base = pkg / "manual_upload_package"
    tmp_dir = pkg.parent / f"_tmp_um_{pkg.name}"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    shutil.copytree(pkg, tmp_dir, ignore=shutil.ignore_patterns("manual_upload_package.zip"))
    try:
        shutil.make_archive(str(zip_base), "zip", tmp_dir)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    zip_path = str(zip_base) + ".zip"
    return zip_path if Path(zip_path).exists() else None


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
