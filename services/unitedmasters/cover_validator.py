"""
services/unitedmasters/cover_validator.py — streaming cover 1:1 validation (v0.9.0).

Validates the streaming_cover_1x1 image for distribution: square aspect,
3000x3000 recommended, JPG/PNG, reasonable size. Never modifies the original;
if a resize is needed AND the source is large enough, writes a separate
cover_upload_ready file (no upscaling, no distortion).
"""
from __future__ import annotations

from pathlib import Path


RECOMMENDED_SIZE = 3000


def validate_cover(cover_path: str) -> dict:
    """
    Validate a streaming cover. Returns:
      {status, square, width, height, format, mode, warnings[], ok_for_distribution}
    """
    p = Path(cover_path) if cover_path else None
    if not p or not p.exists():
        return {"status": "Cover Warning", "exists": False,
                "warnings": ["streaming_cover_1x1 파일이 없습니다"],
                "ok_for_distribution": False}

    ext = p.suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg"):
        return {"status": "Cover Warning", "exists": True, "format": ext,
                "warnings": ["JPG 또는 PNG만 지원됩니다"],
                "ok_for_distribution": False}

    try:
        from PIL import Image
        with Image.open(p) as im:
            w, h = im.size
            mode = im.mode
    except Exception:
        return {"status": "Cover Warning", "exists": True,
                "warnings": ["이미지를 열 수 없습니다"], "ok_for_distribution": False}

    warnings = []
    square = (w == h)
    if not square:
        warnings.append("1:1 정사각형이 아닙니다 (배포용 커버는 정사각형이어야 합니다)")
    if w < RECOMMENDED_SIZE or h < RECOMMENDED_SIZE:
        warnings.append(f"권장 해상도 {RECOMMENDED_SIZE}x{RECOMMENDED_SIZE} 미만입니다 (현재 {w}x{h})")
    if mode not in ("RGB", "RGBA"):
        warnings.append(f"RGB 모드를 권장합니다 (현재 {mode})")

    ok = square and not warnings or (square and all("권장" in x or "RGB" in x for x in warnings))
    status = "Cover Ready" if (square and w >= RECOMMENDED_SIZE and h >= RECOMMENDED_SIZE) \
        else "Cover Warning"

    return {
        "status": status, "exists": True, "square": square,
        "width": w, "height": h, "format": ext, "mode": mode,
        "warnings": warnings,
        "ok_for_distribution": square,  # square is the hard requirement
    }


def make_upload_ready_cover(cover_path: str, out_dir: str) -> str | None:
    """
    Create cover_upload_ready.(png|jpg) WITHOUT modifying the original.
    - If already square AND >= 3000: copy as upload-ready.
    - If square but smaller: copy as-is (NO upscaling / NO distortion).
    - If non-square: do a CENTER CROP to square (no stretching) at the largest
      square that fits, then (only) downscale to 3000 if larger.
    Returns the path, or None on failure.
    """
    p = Path(cover_path)
    if not p.exists():
        return None
    try:
        from PIL import Image
    except ImportError:
        return None

    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    out_ext = ".png" if p.suffix.lower() == ".png" else ".jpg"
    out_path = d / f"cover_upload_ready{out_ext}"

    try:
        with Image.open(p) as im:
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGB")
            w, h = im.size
            if w != h:
                # center crop to the largest square (no distortion)
                side = min(w, h)
                left = (w - side) // 2
                top = (h - side) // 2
                im = im.crop((left, top, left + side, top + side))
                w = h = side
            # only DOWNSCALE if larger than recommended (never upscale)
            if w > RECOMMENDED_SIZE:
                im = im.resize((RECOMMENDED_SIZE, RECOMMENDED_SIZE), Image.LANCZOS)
            if out_ext == ".jpg" and im.mode == "RGBA":
                im = im.convert("RGB")
            im.save(out_path)
        return str(out_path)
    except Exception:
        return None
