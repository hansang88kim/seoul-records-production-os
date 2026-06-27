"""
NanoBananaProvider — image generation via Nano Banana / Flow API.

v0.1: Stub. Not implemented.
v0.4+: Will call Nano Banana or Flow image generation API.

TODO v0.4:
- Obtain API endpoint from Nano Banana / Flow documentation.
- Implement create_image(prompt, aspect_ratio, output_path).
- Handle rate limits and async polling.
- Store image_generation_log.jsonl in project folder.
"""

from __future__ import annotations
from .base import ImageProvider


class NanoBananaProvider(ImageProvider):
    """Nano Banana / Flow image generation provider. Not yet implemented."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    def generate_youtube_thumbnail(
        self,
        prompt: str,
        output_path: str,
        width: int = 1280,
        height: int = 720,
    ) -> str:
        # TODO v0.4: implement
        raise NotImplementedError(
            "NanoBananaProvider is not implemented in v0.1. "
            "Use MockImageProvider or set COMPOSER_PROVIDER=mock."
        )

    def generate_dsp_cover(
        self,
        prompt: str,
        output_path: str,
        size: int = 3000,
    ) -> str:
        # TODO v0.4: implement
        raise NotImplementedError(
            "NanoBananaProvider is not implemented in v0.1. "
            "Use MockImageProvider or set COMPOSER_PROVIDER=mock."
        )

    def get_capabilities(self) -> dict:
        return {
            "provider": "nano_banana",
            "available": False,
            "version": "stub_v0.1",
            "notes": "Implement in v0.4",
        }
