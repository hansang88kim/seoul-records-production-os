"""Base interface for image generation providers."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional


class ImageProvider(ABC):
    """Abstract base for all image generation providers."""

    @abstractmethod
    def generate_youtube_thumbnail(
        self,
        prompt: str,
        output_path: str,
        width: int = 1280,
        height: int = 720,
    ) -> str:
        """Generate a YouTube thumbnail (16:9). Returns saved file path."""

    @abstractmethod
    def generate_dsp_cover(
        self,
        prompt: str,
        output_path: str,
        size: int = 3000,
    ) -> str:
        """Generate a DSP cover image (1:1). Returns saved file path."""

    @abstractmethod
    def get_capabilities(self) -> dict:
        """Return provider capabilities dict."""
