"""
LocalUploadProvider — accepts manually uploaded image files.

v0.1: Validates and copies user-supplied images to the correct project folders.
"""

from __future__ import annotations
import os
import shutil
from .base import ImageProvider

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


class LocalUploadProvider(ImageProvider):
    """Accepts user-uploaded images and validates their dimensions."""

    def generate_youtube_thumbnail(
        self,
        prompt: str,
        output_path: str,
        width: int = 1280,
        height: int = 720,
    ) -> str:
        raise NotImplementedError(
            "LocalUploadProvider does not generate images. "
            "Use import_thumbnail() to import a user-supplied file."
        )

    def generate_dsp_cover(
        self,
        prompt: str,
        output_path: str,
        size: int = 3000,
    ) -> str:
        raise NotImplementedError(
            "LocalUploadProvider does not generate images. "
            "Use import_cover() to import a user-supplied file."
        )

    def import_thumbnail(self, source_path: str, dest_path: str) -> dict:
        """
        Validate and import a user-supplied thumbnail.

        Args:
            source_path: Path to user's image file.
            dest_path: Destination path inside the project folder.

        Returns:
            dict with status, width, height, path.
        """
        if not os.path.exists(source_path):
            return {"status": "error", "reason": f"File not found: {source_path}"}

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy2(source_path, dest_path)

        result = {"status": "ok", "path": dest_path}
        if _PIL_AVAILABLE:
            with Image.open(dest_path) as img:
                w, h = img.size
                result["width"] = w
                result["height"] = h
                if w < 1280 or h < 720:
                    result["status"] = "warning"
                    result["reason"] = f"Image is smaller than recommended 1280×720 ({w}×{h})"
        return result

    def import_cover(self, source_path: str, dest_path: str) -> dict:
        """
        Validate and import a user-supplied DSP cover.

        Args:
            source_path: Path to user's image file.
            dest_path: Destination path inside the project folder.

        Returns:
            dict with status, width, height, path.
        """
        if not os.path.exists(source_path):
            return {"status": "error", "reason": f"File not found: {source_path}"}

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy2(source_path, dest_path)

        result = {"status": "ok", "path": dest_path}
        if _PIL_AVAILABLE:
            with Image.open(dest_path) as img:
                w, h = img.size
                result["width"] = w
                result["height"] = h
                if w != h:
                    result["status"] = "error"
                    result["reason"] = f"Cover must be square. Got {w}×{h}."
                elif w < 3000:
                    result["status"] = "warning"
                    result["reason"] = f"Cover is smaller than required 3000×3000 ({w}×{h})"
        return result

    def get_capabilities(self) -> dict:
        return {
            "provider": "local_upload",
            "available": True,
            "generates_images": False,
            "accepts_uploads": True,
            "validates_dimensions": _PIL_AVAILABLE,
        }
