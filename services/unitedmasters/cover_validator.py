"""Validate or prepare a separate UnitedMasters cover from approved artwork."""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageOps


RECOMMENDED_SIZE = 3000
MAX_COVER_SIZE = 6000
MAX_COVER_BYTES = 40_000_000
IMAGE_EXTS = (".png", ".jpg", ".jpeg")


def validate_cover(cover_path: str) -> dict:
    """
    Validate a streaming cover. Returns:
      {status, square, width, height, format, mode, warnings[], ok_for_distribution}
    """
    p = Path(cover_path) if cover_path else None
    if not p or not p.is_file():
        return {"status": "Cover Warning", "exists": False,
                "warnings": ["streaming_cover_1x1 파일이 없습니다"],
                "ok_for_distribution": False}

    ext = p.suffix.lower()
    if ext not in IMAGE_EXTS:
        return {"status": "Cover Warning", "exists": True, "format": ext,
                "warnings": ["JPG 또는 PNG만 지원됩니다"],
                "ok_for_distribution": False}

    try:
        with Image.open(p) as im:
            if im.format not in ("JPEG", "PNG"):
                raise ValueError("Expected JPEG or PNG")
            w, h = ImageOps.exif_transpose(im).size
            mode = im.mode
    except Exception:
        return {"status": "Cover Warning", "exists": True,
                "warnings": ["이미지를 열 수 없습니다"], "ok_for_distribution": False}

    warnings = []
    square = (w == h)
    if not square:
        warnings.append("1:1 정사각형이 아닙니다 (배포용 커버는 정사각형이어야 합니다)")
    if w < RECOMMENDED_SIZE or h < RECOMMENDED_SIZE:
        warnings.append(f"커버 해상도 {RECOMMENDED_SIZE}×{RECOMMENDED_SIZE} 미만입니다 (현재 {w}×{h})")
    if max(w, h) > MAX_COVER_SIZE:
        warnings.append(f"커버 해상도가 최대 {MAX_COVER_SIZE}×{MAX_COVER_SIZE}를 초과합니다.")
    if p.stat().st_size > MAX_COVER_BYTES:
        warnings.append("커버 파일은 웹 화면 기준 40 MB 이하여야 합니다.")
    if mode not in ("RGB", "RGBA"):
        warnings.append(f"RGB 모드를 권장합니다 (현재 {mode})")

    ready = (square and RECOMMENDED_SIZE <= w <= MAX_COVER_SIZE
             and p.stat().st_size <= MAX_COVER_BYTES)

    return {
        "status": "Cover Ready" if ready else "Cover Warning", "exists": True, "square": square,
        "width": w, "height": h, "format": ext, "mode": mode,
        "warnings": warnings,
        "ok_for_distribution": ready,
    }


def make_upload_ready_cover(cover_path: str, out_dir: str) -> str | None:
    """Fit a wide design inside a white 3000 px square, preserving every edge."""
    p = Path(cover_path)
    if not p.is_file() or p.suffix.lower() not in IMAGE_EXTS:
        return None
    try:
        with Image.open(p) as source:
            if source.format not in ("JPEG", "PNG"):
                return None
            source_format = source.format
            im = ImageOps.exif_transpose(source).convert("RGBA")
            w, h = im.size
            if w == h and w < RECOMMENDED_SIZE:
                return None
            side = w if w == h and w <= MAX_COVER_SIZE else RECOMMENDED_SIZE
            fitted = ImageOps.contain(im, (side, side), Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", (side, side), "white")
            x = (side - fitted.width) // 2
            y = (side - fitted.height) // 2
            canvas.paste(fitted, (x, y), fitted)
            out_dir = Path(out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            if w == h and source_format == "PNG":
                out_path = out_dir / "cover_upload_ready.png"
                canvas.save(out_path, dpi=(300, 300))
                if out_path.stat().st_size <= MAX_COVER_BYTES:
                    return str(out_path)
                out_path.unlink()
            out_path = out_dir / "cover_upload_ready.jpg"
            canvas.save(out_path, quality=95, dpi=(300, 300))
            if out_path.stat().st_size > MAX_COVER_BYTES:
                canvas.thumbnail((RECOMMENDED_SIZE, RECOMMENDED_SIZE), Image.Resampling.LANCZOS)
                canvas.save(out_path, quality=90, dpi=(300, 300))
        return str(out_path)
    except (OSError, ValueError, Image.DecompressionBombError):
        return None
