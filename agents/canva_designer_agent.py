"""
CanvaDesignerAgent — applies text overlays and exports final assets via Canva.

v0.1: Stub. Saves placeholder Canva URL files and logs intent.
v0.4+: Will integrate with Canva MCP (template-based, not freeform design).

POLICY:
- Always work via templates. Never do freeform design.
- Text is added by Canva template filling, not by prompt.
- Final exports: youtube_thumbnail_16x9.jpg/.png + dsp_cover_3000x3000.jpg/.png
"""

from __future__ import annotations
import os


# Placeholder Canva template IDs — replace with real IDs in v0.4
_TEMPLATE_IDS = {
    "youtube_thumbnail": "CANVA_TEMPLATE_YOUTUBE_16x9_TODO",
    "dsp_cover": "CANVA_TEMPLATE_DSP_COVER_1x1_TODO",
}


class CanvaDesignerAgent:
    """Orchestrates Canva template filling for visual assets."""

    def __init__(self, canva_mcp_token: str = ""):
        self.token = canva_mcp_token
        self._available = bool(canva_mcp_token)

    def is_available(self) -> bool:
        return self._available

    def create_youtube_thumbnail(
        self,
        source_image_path: str,
        title: str,
        output_dir: str,
    ) -> dict:
        """
        Fill Canva thumbnail template with title text and source image.

        v0.1: Writes placeholder URL file.
        """
        url_file = os.path.join(output_dir, "canva", "youtube_thumbnail_canva_url.txt")
        os.makedirs(os.path.dirname(url_file), exist_ok=True)
        with open(url_file, "w", encoding="utf-8") as f:
            f.write(
                f"# Canva thumbnail URL — fill manually in v0.1\n"
                f"# Template: {_TEMPLATE_IDS['youtube_thumbnail']}\n"
                f"# Title: {title}\n"
                f"# Source image: {source_image_path}\n"
                f"# TODO: implement Canva MCP in v0.4\n"
            )
        return {"status": "placeholder", "url_file": url_file}

    def create_dsp_cover(
        self,
        source_image_path: str,
        title: str,
        artist: str,
        output_dir: str,
    ) -> dict:
        """
        Fill Canva DSP cover template.

        v0.1: Writes placeholder URL file.
        """
        url_file = os.path.join(output_dir, "canva", "dsp_cover_canva_url.txt")
        os.makedirs(os.path.dirname(url_file), exist_ok=True)
        with open(url_file, "w", encoding="utf-8") as f:
            f.write(
                f"# Canva DSP cover URL — fill manually in v0.1\n"
                f"# Template: {_TEMPLATE_IDS['dsp_cover']}\n"
                f"# Title: {title}\n"
                f"# Artist: {artist}\n"
                f"# Source image: {source_image_path}\n"
                f"# TODO: implement Canva MCP in v0.4\n"
            )
        return {"status": "placeholder", "url_file": url_file}

    def export_final_assets(self, canva_design_id: str, output_dir: str) -> dict:
        """
        Export finalized design as PNG and JPG.

        v0.1: Not implemented. Returns stub result.
        """
        # TODO v0.4: call Canva MCP export endpoint
        return {
            "status": "not_implemented",
            "message": "Canva export requires v0.4 MCP integration.",
        }
