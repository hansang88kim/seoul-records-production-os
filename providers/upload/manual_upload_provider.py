"""
ManualUploadProvider — generates upload packages and checklists for manual browser upload.

Used for both YouTube and UnitedMasters in v0.1.
"""

from __future__ import annotations
import os
import json
import shutil
import zipfile
from datetime import datetime, timezone


class ManualUploadProvider:
    """Creates structured upload packages for manual browser upload."""

    def create_youtube_package(
        self,
        video_path: str,
        thumbnail_path: str,
        metadata: dict,
        output_dir: str,
    ) -> dict:
        """
        Assemble a YouTube upload package.

        Returns path to the zip file and a checklist.
        """
        assets_dir = os.path.join(output_dir, "assets")
        metadata_dir = os.path.join(output_dir, "metadata")
        os.makedirs(assets_dir, exist_ok=True)
        os.makedirs(metadata_dir, exist_ok=True)

        # Copy assets
        for src, name in [
            (video_path, "final_video.mp4"),
            (thumbnail_path, "youtube_thumbnail_16x9.jpg"),
        ]:
            if src and os.path.exists(src):
                shutil.copy2(src, os.path.join(assets_dir, name))

        # Write metadata files
        self._write_text(metadata.get("title", ""), metadata_dir, "youtube_title.txt")
        self._write_text(metadata.get("description", ""), metadata_dir, "youtube_description.txt")
        self._write_text("\n".join(metadata.get("tags", [])), metadata_dir, "youtube_tags.txt")
        self._write_text(
            " ".join(f"#{t}" for t in metadata.get("hashtags", [])),
            metadata_dir,
            "youtube_hashtags.txt",
        )
        with open(os.path.join(metadata_dir, "upload_config.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "visibility": "private",
                    "category": "Music",
                    "language": metadata.get("language", "ko"),
                    **metadata,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        # Zip the package
        zip_path = os.path.join(output_dir, "youtube_upload_package.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for root, _, files in os.walk(output_dir):
                for file in files:
                    if file.endswith(".zip"):
                        continue
                    fpath = os.path.join(root, file)
                    zf.write(fpath, os.path.relpath(fpath, output_dir))

        return {"status": "ready", "zip": zip_path, "metadata_dir": metadata_dir}

    def create_distribution_package(
        self,
        tracks: list[dict],
        cover_path: str,
        release_metadata: dict,
        output_dir: str,
    ) -> dict:
        """
        Assemble a UnitedMasters distribution package.

        Blocks MP3-only tracks.
        Returns status and zip path.
        """
        audio_dir = os.path.join(output_dir, "unitedmasters", "audio")
        os.makedirs(audio_dir, exist_ok=True)

        blocked = []
        for i, track in enumerate(tracks, 1):
            wav = track.get("wav_path") or track.get("master_wav_path")
            if not wav or not os.path.exists(wav):
                mp3 = track.get("mp3_path") or track.get("preview_mp3_path")
                reason = (
                    "BLOCKED: Only MP3 exists — MP3-to-WAV conversion not allowed."
                    if (mp3 and os.path.exists(mp3))
                    else "BLOCKED: WAV master missing."
                )
                blocked.append({"track": track.get("title", f"track_{i}"), "reason": reason})
                continue
            safe = track.get("title", f"track_{i:02d}").replace(" ", "_")
            shutil.copy2(wav, os.path.join(audio_dir, f"{i:02d}_{safe}.wav"))

        zip_path = os.path.join(output_dir, "unitedmasters_package.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for root, _, files in os.walk(output_dir):
                for file in files:
                    if file.endswith(".zip"):
                        continue
                    fpath = os.path.join(root, file)
                    zf.write(fpath, os.path.relpath(fpath, output_dir))

        return {
            "status": "blocked" if blocked else "ready",
            "blocked": blocked,
            "zip": zip_path,
        }

    @staticmethod
    def _write_text(content: str, directory: str, filename: str) -> None:
        with open(os.path.join(directory, filename), "w", encoding="utf-8") as f:
            f.write(content)
