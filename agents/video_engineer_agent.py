"""
agents/video_engineer_agent.py
───────────────────────────────
VideoEngineerAgent — generates timestamps, YouTube chapters,
FFmpeg render commands, and (if FFmpeg is available) renders the final video.
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seconds_to_hhmmss(total_sec: float) -> str:
    total_sec = int(total_sec)
    h = total_sec // 3600
    m = (total_sec % 3600) // 60
    s = total_sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _wav_duration(path: Path) -> float:
    try:
        with wave.open(str(path), "r") as wf:
            return wf.getnframes() / float(wf.getframerate())
    except Exception:
        return 0.0


def _ffprobe_duration(path: Path) -> float | None:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", str(path),
            ],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(result.stdout)
        for stream in data.get("streams", []):
            if stream.get("duration"):
                return float(stream["duration"])
    except Exception:
        pass
    return None


class VideoEngineerAgent:

    def __init__(self, project_dir: Path, output_type: str = "1 Hour Playlist Mode") -> None:
        self.project_dir = project_dir
        self.output_type = output_type
        self.video_dir = project_dir / "03_longform_video"

    def _collect_selected_wavs(self) -> list[dict[str, Any]]:
        """Scan song_list.csv and collect approved WAV paths with durations."""
        csv_path = self.project_dir / "01_suno_song_generation" / "song_list.csv"
        if not csv_path.exists():
            return []

        tracks = []
        with csv_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                wav_path = Path(row.get("wav_path", ""))
                if wav_path.exists():
                    dur = _ffprobe_duration(wav_path) or _wav_duration(wav_path)
                    tracks.append({
                        "track_index": int(row.get("track_index", 0)),
                        "title": row.get("title", "Unknown"),
                        "wav_path": wav_path,
                        "duration_sec": dur,
                    })
        return sorted(tracks, key=lambda t: t["track_index"])

    def generate_timestamps(self) -> tuple[Path, Path]:
        """
        Generate timestamps.txt and youtube_chapters.txt.
        Returns (timestamps_path, chapters_path).
        """
        tracks = self._collect_selected_wavs()
        ts_dir = self.video_dir / "timestamps"
        ts_dir.mkdir(parents=True, exist_ok=True)

        if not tracks:
            # Write placeholder
            placeholder = (
                "00:00 — (No tracks found — run Song Generation first)\n"
            )
            ts_path = ts_dir / "timestamps.txt"
            ch_path = ts_dir / "youtube_chapters.txt"
            ts_path.write_text(placeholder, encoding="utf-8")
            ch_path.write_text(placeholder, encoding="utf-8")
            return ts_path, ch_path

        cursor = 0.0
        ts_lines = []
        chapter_lines = []

        for track in tracks:
            hhmmss = _seconds_to_hhmmss(cursor)
            ts_lines.append(f"{hhmmss} — {track['title']}")
            chapter_lines.append(f"{hhmmss} {track['title']}")
            cursor += track["duration_sec"]

        total_hhmmss = _seconds_to_hhmmss(cursor)

        ts_path = ts_dir / "timestamps.txt"
        ch_path = ts_dir / "youtube_chapters.txt"

        ts_path.write_text(
            "\n".join(ts_lines) + f"\n\nTotal: {total_hhmmss}\n",
            encoding="utf-8"
        )
        ch_path.write_text(
            "\n".join(chapter_lines) + "\n",
            encoding="utf-8"
        )
        return ts_path, ch_path

    def generate_ffmpeg_command(
        self, background_image: Path | None = None
    ) -> tuple[str, Path]:
        """
        Generate the FFmpeg render command for the longform video.
        Returns (command_string, command_file_path).
        """
        tracks = self._collect_selected_wavs()
        input_dir = self.video_dir / "input"
        scripts_dir = self.video_dir / "render_scripts"
        output_dir = self.video_dir / "output"
        input_dir.mkdir(parents=True, exist_ok=True)
        scripts_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Write audio list for FFmpeg concat
        audio_list_path = input_dir / "selected_audio_list.txt"
        with audio_list_path.open("w", encoding="utf-8") as f:
            for track in tracks:
                f.write(f"file '{track['wav_path']}'\n")

        # Resolve background image
        bg_path = background_image
        if bg_path is None:
            thumb = self.project_dir / "02_thumbnail_cover" / "final" / "youtube_thumbnail_16x9.jpg"
            if thumb.exists():
                bg_path = thumb
                # Copy to video input dir
                dest = input_dir / "background_image.jpg"
                shutil.copy2(thumb, dest)
                bg_path = dest
            else:
                bg_path = Path("background_image.jpg")  # placeholder path

        final_video = output_dir / "final_video.mp4"

        # Build command
        cmd_parts = [
            "ffmpeg -y",
            f"-loop 1 -i \"{bg_path}\"",
            f"-f concat -safe 0 -i \"{audio_list_path}\"",
            "-c:v libx264 -tune stillimage -preset slow -crf 18",
            "-c:a aac -b:a 320k -ar 44100",
            "-pix_fmt yuv420p",
            "-shortest",
            f"\"{final_video}\"",
        ]
        command = " \\\n  ".join(cmd_parts)

        cmd_path = scripts_dir / "ffmpeg_render_command.txt"
        cmd_path.write_text(command + "\n", encoding="utf-8")

        # Also write render config JSON
        render_config = {
            "output_type": self.output_type,
            "track_count": len(tracks),
            "tracks": [
                {
                    "track_index": t["track_index"],
                    "title": t["title"],
                    "duration_sec": t["duration_sec"],
                    "wav_path": str(t["wav_path"]),
                }
                for t in tracks
            ],
            "background_image": str(bg_path),
            "output_video": str(final_video),
            "audio_list": str(audio_list_path),
            "generated_at": _now_iso(),
        }
        (scripts_dir / "render_config.json").write_text(
            json.dumps(render_config, indent=2, ensure_ascii=False)
        )

        return command, cmd_path

    def render_video(self) -> dict[str, Any]:
        """
        Attempt to render final_video.mp4 using FFmpeg.
        If FFmpeg is not installed, marks manual_required.
        """
        ffmpeg_available = shutil.which("ffmpeg") is not None

        command, cmd_path = self.generate_ffmpeg_command()
        self.generate_timestamps()

        if not ffmpeg_available:
            result = {
                "status": "manual_required",
                "reason": "FFmpeg not found in PATH. Install FFmpeg and run the command in ffmpeg_render_command.txt.",
                "command_path": str(cmd_path),
                "ffmpeg_available": False,
            }
        else:
            try:
                # Execute render
                output_dir = self.video_dir / "output"
                final_video = output_dir / "final_video.mp4"
                proc = subprocess.run(
                    command, shell=True, capture_output=True, text=True, timeout=7200
                )
                if proc.returncode == 0:
                    result = {
                        "status": "completed",
                        "output_path": str(final_video),
                        "ffmpeg_available": True,
                    }
                else:
                    result = {
                        "status": "failed",
                        "error": proc.stderr[-2000:],
                        "ffmpeg_available": True,
                    }
            except subprocess.TimeoutExpired:
                result = {"status": "timeout", "ffmpeg_available": True}

        # Save video manifest
        video_manifest = {
            "output_type": self.output_type,
            "render_result": result,
            "command_path": str(cmd_path),
            "generated_at": _now_iso(),
        }
        manifest_path = self.video_dir / "output" / "video_manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(video_manifest, indent=2, ensure_ascii=False))

        return result
