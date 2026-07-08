"""
app/ui/song_card.py — Compact Generated Song List (table-like rows).

One song = one row. Columns: status · title · duration · model · type · actions.
v1.0.0-alpha.48:
  * ▶️ inline playback — click to open an audio player row under the song
    (one at a time); resolves the file even when the manifest has no
    file_path (Suno submitted → manually downloaded into songs/).
  * Project-aware delete — when project_name is given, 🗑 removes the song
    from the PROJECT MANIFEST (+ audio file), not just the session list.
  * key_ns — unique widget keys per list, so multiple project expanders can
    render song lists on the same page without key collisions.
  * 길이 자동 계산 — missing durations are read from the audio file.
"""
from __future__ import annotations
from pathlib import Path
import streamlit as st


_STATUS_ICONS = {
    "queued": "⏳", "generating": "🔄", "completed": "✅",
    "failed": "❌", "imported": "📥", "mp3_only_preview": "⚠️",
    "submitted": "✅", "saved": "✅", "approved": "✅",
}


def _dur_str(duration) -> str:
    if not duration:
        return "—"
    d = float(duration)
    return f"{int(d//60)}:{int(d%60):02d}"


def _file_duration(path: str) -> float | None:
    """Read the audio duration from disk (cached per path)."""
    cache = st.session_state.setdefault("_song_dur_cache", {})
    if path in cache:
        return cache[path]
    dur = None
    try:
        import mutagen
        m = mutagen.File(path)
        if m is not None and m.info is not None:
            dur = float(m.info.length or 0) or None
    except Exception:
        dur = None
    cache[path] = dur
    return dur


def _resolve_file(song: dict, project_name: str | None) -> str:
    """Playable file for a song — manifest file_path or project songs/ scan."""
    fp = song.get("file_path", "") or ""
    if fp and Path(fp).exists():
        return fp
    if project_name:
        try:
            from app.project_manager import find_song_file
            return find_song_file(project_name, song)
        except Exception:
            return ""
    return ""


def _open_folder(file_path: str):
    """Open the folder containing the file."""
    import subprocess, platform
    folder = str(Path(file_path).parent)
    if platform.system() == "Windows":
        subprocess.Popen(["explorer", folder])
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", folder])
    else:
        subprocess.Popen(["xdg-open", folder])


def render_song_list(songs: list[dict], project_name: str | None = None,
                     key_ns: str = ""):
    """
    Render the generated songs as a compact table.

    project_name — when given, playback resolves files from that project's
    songs/ folder and 🗑 removes the song from the project manifest.
    key_ns — widget-key namespace; REQUIRED to be unique when several lists
    render on one page (e.g. 프로젝트 관리's per-project expanders).
    """
    if not songs:
        st.caption("아직 생성된 곡이 없습니다. 위에서 Generate를 눌러주세요.")
        return

    ns = key_ns or (project_name or "default")
    play_key = "song_playing"

    st.markdown(f"**🎵 생성된 곡 ({len(songs)}곡)**")

    # v1.0.0-alpha.83: compact card-per-song layout (was a 6-column table that
    # stacked into ~10 lines/song on mobile → huge vertical scroll). Each song
    # is now one info line + a horizontal action bar (kept horizontal on mobile
    # via the st.container(key="srx-actrow…") CSS opt-out in app/main.py).
    import html as _html

    for i, song in enumerate(songs):
        icon = _STATUS_ICONS.get(song.get("status", ""), "⚪")
        title = song.get("title", "제목 없음")
        model = song.get("model", "—")
        file_path = _resolve_file(song, project_name)
        has_file = bool(file_path)
        file_type = (song.get("file_type") or
                     (Path(file_path).suffix.lstrip(".") if has_file else "—") or "—").upper()
        duration = song.get("duration") or (_file_duration(file_path) if has_file else None)

        row_id = f"{ns}_{i}"
        is_playing = st.session_state.get(play_key) == row_id

        meta = f"{_dur_str(duration)} · {model} · {file_type}"
        st.markdown(
            f"<div style='display:flex;align-items:baseline;gap:0.5rem;flex-wrap:wrap;"
            f"margin:0.15rem 0 0.1rem'>"
            f"<span>{icon}</span>"
            f"<span style='font-weight:650;color:var(--ink)'>{_html.escape(title)}</span>"
            f"<span style='color:var(--muted-2);font-size:0.82rem'>· {_html.escape(meta)}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        with st.container(key=f"srx-actrow-{ns}-{i}"):
            bc = st.columns([1, 1, 1, 1, 6])
            with bc[0]:
                if has_file:
                    if st.button("⏸" if is_playing else "▶️", key=f"p_{row_id}",
                                 help="정지" if is_playing else "재생"):
                        st.session_state[play_key] = None if is_playing else row_id
                        st.rerun()
            with bc[1]:
                if has_file and st.button("📂", key=f"o_{row_id}", help="폴더 열기"):
                    _open_folder(file_path)
            with bc[2]:
                if st.button("🔄", key=f"r_{row_id}", help="재생성"):
                    st.session_state["regenerate_song"] = song
            with bc[3]:
                if st.button("🗑", key=f"d_{row_id}", help="곡 삭제 (파일 + 목록)"):
                    if project_name:
                        from app.project_manager import remove_song_from_project
                        remove_song_from_project(project_name, song, delete_file=True)
                    else:
                        if has_file:
                            try:
                                Path(file_path).unlink()
                            except Exception:
                                pass
                        gen = st.session_state.get("generated_songs", [])
                        if i < len(gen):
                            gen.pop(i)
                    if st.session_state.get(play_key) == row_id:
                        st.session_state[play_key] = None
                    st.rerun()

        # Inline player row (full width, under the song being played)
        if is_playing and has_file:
            st.audio(file_path)
