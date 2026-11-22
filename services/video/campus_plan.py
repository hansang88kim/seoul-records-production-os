"""Playlist, chapter and caption timing for the Seoul Records campus preset."""
from __future__ import annotations

import json
from math import isfinite
from pathlib import Path

from services.youtube.metadata_generator import _clean_track_title

PRESET_PATH = Path(__file__).resolve().parents[2] / "presets" / "video" / "seoul_records_campus_v1.json"


def load_campus_preset() -> dict:
    return json.loads(PRESET_PATH.read_text(encoding="utf-8"))


def build_campus_playlist(tracks: list[dict], preset: dict) -> dict:
    """Align starts to video frames and place silence between, not over, songs."""
    fps = preset["video"]["fps"]
    gap_frames = round(fps * preset["transition"]["silence_ms"] / 1000)
    cursor = round(fps * preset["video"]["lead_in_seconds"])
    entries, chapters = [], []
    for track in tracks:
        duration = float(track.get("duration_sec") or 0)
        if not track.get("path") or not isfinite(duration) or duration <= 0:
            raise ValueError(f"음원 길이를 확인할 수 없습니다. {track.get('name', '')}")
        frames = max(1, round(duration * fps))
        name = track["name"]
        title = track.get("title") or _clean_track_title(name)
        entry = {
            "path": str(Path(track["path"]).resolve()), "name": name, "title": title,
            "duration_sec": duration, "start_frame": cursor, "end_frame": cursor + frames,
            "start_sec": cursor / fps, "end_sec": (cursor + frames) / fps,
        }
        chapters.append({"title": title, "start_sec": entry["start_sec"] if entries else 0,
                         "end_sec": entry["end_sec"]})
        entries.append(entry)
        cursor += frames + gap_frames
    if not entries:
        raise ValueError("음원을 한 곡 이상 선택하세요.")
    return {"entries": entries, "chapters": chapters, "fps": fps,
            "total_frames": entries[-1]["end_frame"], "total_seconds": entries[-1]["end_sec"]}


def render_window(plan: dict, preset: dict, mode: str) -> tuple[int, int]:
    """Return the half-open frame interval for a preview, transition or full render."""
    total = plan["total_frames"]
    fps = plan["fps"]
    if mode == "full":
        return 0, total
    if mode == "preview":
        return 0, min(total, preset["video"]["preview_seconds"] * fps)
    if mode == "transition" and len(plan["entries"]) > 1:
        start = plan["entries"][1]["start_frame"]
        return max(0, start - 5 * fps), min(total, start + 5 * fps)
    raise ValueError("곡 전환 미리보기에는 두 곡 이상이 필요합니다.")


def _time(seconds: float, duration: float) -> float:
    time = float(seconds)
    if not isfinite(time) or not 0 <= time <= duration:
        raise ValueError("타이밍은 곡 길이 이내의 초 단위 값이어야 합니다.")
    return time


def read_captions(data: bytes, plan: dict) -> dict:
    """Read verified, original-track-relative syllable and instrumental timings."""
    try:
        records = json.loads(data.decode("utf-8-sig"))["tracks"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("가사 타이밍 JSON에는 tracks 배열이 필요합니다.") from exc
    if not isinstance(records, list):
        raise ValueError("가사 타이밍 JSON에는 tracks 배열이 필요합니다.")

    captions = {}
    for record in records:
        number = "?"
        try:
            number = record["track_no"]
            if type(number) is not int or not 1 <= number <= len(plan["entries"]) or str(number) in captions:
                raise ValueError("선택 목록 내의 중복 없는 곡 번호를 입력하세요.")
            duration = plan["entries"][number - 1]["duration_sec"]
            lyrics, instrumental = [], []
            for line in record.get("lyrics", []):
                syllables = [
                    {"start_sec": _time(s["start_sec"], duration), "text": s["text"]}
                    for s in line["syllables"]
                ]
                times = [s["start_sec"] for s in syllables]
                end = _time(line["end_sec"], duration)
                if (not times or times != sorted(times) or times[-1] >= end
                        or any(not isinstance(s["text"], str) or not s["text"] for s in syllables)):
                    raise ValueError("가사 음절과 끝 시간을 재생 순서대로 입력하세요.")
                if lyrics and times[0] < lyrics[-1]["end_sec"]:
                    raise ValueError("가사 줄의 실제 발성 시간이 겹칩니다.")
                lyrics.append({"end_sec": end, "syllables": syllables})
            for interval in record.get("instrumental", []):
                start = _time(interval["start_sec"], duration)
                end = _time(interval["end_sec"], duration)
                if end <= start or (instrumental and start < instrumental[-1]["end_sec"]):
                    raise ValueError("연주 구간의 시작·끝을 겹치지 않게 입력하세요.")
                for line in lyrics:
                    if start < line["end_sec"] and line["syllables"][0]["start_sec"] < end:
                        raise ValueError("연주 구간과 실제 가사 발성이 겹칩니다.")
                instrumental.append({"start_sec": start, "end_sec": end})
            captions[str(number)] = {"lyrics": lyrics, "instrumental": instrumental}
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"가사 타이밍 {number}번 트랙. {exc}") from exc
    return captions
