"""
services/youtube/thumbnail_validator.py — Thumbnail validation + compression (v0.8.0).

YouTube custom thumbnail constraints:
  - aspect ratio 16:9
  - recommended 1280x720 or 1920x1080
  - file size <= 2MB
  - PNG / JPEG accepted

If a thumbnail is over 2MB, an upload-ready compressed copy is created WITHOUT
overwriting the original (kept separately as thumbnail_upload_ready.jpg/png).
"""
from __future__ import annotations

from pathlib import Path


MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2MB
ACCEPTED_EXT = {".png", ".jpg", ".jpeg"}

# Status codes
STATUS_READY = "ready"
STATUS_COMPRESSED = "too_large_compressed"
STATUS_WRONG_ASPECT = "wrong_aspect_ratio"
STATUS_MISSING = "missing"
STATUS_BAD_FORMAT = "bad_format"


def _aspect_ok(w: int, h: int, tol: float = 0.02) -> bool:
    """Check 16:9 within tolerance."""
    if h == 0:
        return False
    return abs((w / h) - (16 / 9)) <= tol


def validate_thumbnail(thumbnail_path: str, out_dir: str) -> dict:
    """
    Validate a thumbnail and, if needed, create an upload-ready compressed copy.

    Returns:
      {
        "status": one of the STATUS_* codes,
        "original_path": str,
        "upload_ready_path": str | None,
        "width": int, "height": int,
        "original_size_mb": float,
        "upload_ready_size_mb": float | None,
        "aspect_ok": bool,
        "warnings": [str],
        "message": str,
      }
    """
    result = {
        "status": STATUS_MISSING,
        "original_path": thumbnail_path,
        "upload_ready_path": None,
        "width": 0, "height": 0,
        "original_size_mb": 0.0,
        "upload_ready_size_mb": None,
        "aspect_ok": False,
        "warnings": [],
        "message": "",
    }

    p = Path(thumbnail_path)
    if not thumbnail_path or not p.exists():
        result["message"] = "썸네일이 없습니다. Thumbnail Studio에서 먼저 내보내세요."
        return result

    if p.suffix.lower() not in ACCEPTED_EXT:
        result["status"] = STATUS_BAD_FORMAT
        result["message"] = f"지원하지 않는 형식: {p.suffix} (png/jpg/jpeg만 가능)"
        result["warnings"].append("형식 오류")
        return result

    size = p.stat().st_size
    result["original_size_mb"] = round(size / (1024 * 1024), 2)

    # Inspect dimensions
    try:
        from PIL import Image
        with Image.open(p) as im:
            w, h = im.size
            result["width"], result["height"] = w, h
    except Exception as e:
        result["status"] = STATUS_BAD_FORMAT
        result["message"] = f"이미지를 열 수 없습니다: {e}"
        return result

    result["aspect_ok"] = _aspect_ok(w, h)
    if not result["aspect_ok"]:
        result["warnings"].append(
            f"16:9가 아닙니다 ({w}x{h}). YouTube 권장: 1280x720 또는 1920x1080")

    # Size check + compression
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if size <= MAX_UPLOAD_BYTES:
        # Already upload-ready — copy to a clearly-named upload file (keep original)
        ext = p.suffix.lower()
        ready = out / f"thumbnail_upload_ready{ext}"
        try:
            import shutil
            shutil.copy2(p, ready)
            result["upload_ready_path"] = str(ready)
            result["upload_ready_size_mb"] = round(ready.stat().st_size / (1024 * 1024), 2)
        except Exception:
            result["upload_ready_path"] = str(p)
            result["upload_ready_size_mb"] = result["original_size_mb"]
        result["status"] = STATUS_WRONG_ASPECT if not result["aspect_ok"] else STATUS_READY
        result["message"] = ("업로드 준비 완료 (≤2MB)" if result["aspect_ok"]
                             else "업로드 가능하나 16:9 경고 있음")
    else:
        # Compress to JPEG under 2MB (do NOT overwrite the original)
        ready = out / "thumbnail_upload_ready.jpg"
        compressed = _compress_to_under_2mb(p, ready)
        if compressed:
            result["upload_ready_path"] = str(ready)
            result["upload_ready_size_mb"] = round(ready.stat().st_size / (1024 * 1024), 2)
            result["status"] = STATUS_COMPRESSED
            result["message"] = (f"원본 {result['original_size_mb']}MB > 2MB — "
                                 f"압축본 생성 ({result['upload_ready_size_mb']}MB)")
            result["warnings"].append("원본이 2MB를 초과하여 압축본을 생성했습니다 (원본 보존).")
        else:
            result["status"] = STATUS_BAD_FORMAT
            result["message"] = "압축에 실패했습니다."

    return result


def _compress_to_under_2mb(src: Path, dest: Path) -> bool:
    """Compress an image to JPEG under 2MB by lowering quality, then scaling."""
    try:
        from PIL import Image
        with Image.open(src) as im:
            im = im.convert("RGB")
            # Try decreasing quality first
            for q in (90, 85, 80, 70, 60, 50, 40):
                im.save(dest, "JPEG", quality=q, optimize=True)
                if dest.stat().st_size <= MAX_UPLOAD_BYTES:
                    return True
            # Still too big — scale down progressively
            w, h = im.size
            for scale in (0.85, 0.7, 0.6, 0.5):
                nw, nh = int(w * scale), int(h * scale)
                resized = im.resize((nw, nh), Image.LANCZOS)
                resized.save(dest, "JPEG", quality=80, optimize=True)
                if dest.stat().st_size <= MAX_UPLOAD_BYTES:
                    return True
            # Last resort: keep the smallest attempt
            return dest.exists()
    except Exception:
        return False
