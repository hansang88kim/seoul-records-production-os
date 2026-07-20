"""
tests/test_youtube_mp3_chapters_v097.py — upload MP3s in YouTube Package Studio
→ auto-build the timestamp tracklist / chapters (v1.0.0-alpha.97).

The builder reuses build_playlist_plan + format_chapters_txt, then writes a
chapters file that parse_chapters_txt reads back for the package metadata.
"""
from __future__ import annotations

import app.tabs.youtube_package as yp
from services.video.playlist_builder import build_playlist_plan, format_chapters_txt
from services.youtube.metadata_generator import parse_chapters_txt


def test_scan_chapter_uploads_finds_audio_ignores_other(monkeypatch, tmp_path):
    d = tmp_path / "chap"
    d.mkdir()
    (d / "song_a.mp3").write_bytes(b"ID3____")
    (d / "song_b.wav").write_bytes(b"RIFF")
    (d / "notes.txt").write_text("nope")
    monkeypatch.setattr(yp, "_chap_upload_dir", lambda: d)
    got = {t["name"] for t in yp._scan_chapter_uploads()}
    assert got == {"song_a.mp3", "song_b.wav"}


def test_generated_tracklist_has_cumulative_timestamps(tmp_path):
    """v1.0.0-alpha.121: 각 곡 1회 — 반복 없이 누적 타임스탬프만."""
    tracks = [
        {"path": "a.mp3", "name": "track-A.mp3", "duration_sec": 178},   # 2:58
        {"path": "b.mp3", "name": "track-B.mp3", "duration_sec": 180},   # 3:00
    ]
    plan = build_playlist_plan(tracks)
    txt = "⏱ Tracklist\n" + format_chapters_txt(plan)
    path = tmp_path / "uploaded_chapters.txt"
    path.write_text(txt, encoding="utf-8")

    ents = parse_chapters_txt(str(path))
    # header line skipped; cumulative timestamps computed from durations
    assert ents[0] == {"timestamp": "00:00", "title": "track-A.mp3"}
    assert ents[1]["timestamp"] == "02:58"
    # 업로드한 2곡뿐 — 반복분이 붙지 않는다
    assert len(ents) == 2
    assert not any("(반복" in e["title"] for e in ents)
    assert plan["total_seconds"] == 358


def test_scan_chapter_uploads_empty_when_dir_absent(monkeypatch, tmp_path):
    # v1.0.0-alpha.99: the standalone timestamp-preview step was removed; the
    # builder now auto-feeds the tracklist into 메타데이터 생성. With no uploads
    # there are simply no tracks.
    monkeypatch.setattr(yp, "_chap_upload_dir", lambda: tmp_path / "nope")
    assert yp._scan_chapter_uploads() == []
