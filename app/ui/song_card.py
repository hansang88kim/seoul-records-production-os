"""
app/ui/song_card.py — Compact Generated Song List (table-like rows).

One song = one row, ~40-52px tall.
Columns: status · title · duration · model · type · actions
"""
from __future__ import annotations
from pathlib import Path
import streamlit as st


_STATUS_ICONS = {
    "queued": "⏳", "generating": "🔄", "completed": "✅",
    "failed": "❌", "imported": "📥", "mp3_only_preview": "⚠️",
}


def _dur_str(duration) -> str:
    if not duration:
        return "—"
    d = float(duration)
    return f"{int(d//60)}:{int(d%60):02d}"


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


def render_song_list(songs: list[dict]):
    """Render the generated songs as a compact table."""
    if not songs:
        st.caption("아직 생성된 곡이 없습니다. 위에서 Generate를 눌러주세요.")
        return

    st.markdown(f"**🎵 생성된 곡 ({len(songs)}곡)**")

    # Table header
    cols = st.columns([0.4, 3, 0.8, 0.8, 0.6, 2.4])
    with cols[0]:
        st.caption("상태")
    with cols[1]:
        st.caption("제목")
    with cols[2]:
        st.caption("길이")
    with cols[3]:
        st.caption("모델")
    with cols[4]:
        st.caption("형식")
    with cols[5]:
        st.caption("액션")

    # Song rows
    for i, song in enumerate(songs):
        icon = _STATUS_ICONS.get(song.get("status", ""), "⚪")
        title = song.get("title", "제목 없음")
        duration = song.get("duration")
        model = song.get("model", "—")
        file_type = (song.get("file_type", "—") or "—").upper()
        file_path = song.get("file_path", "")
        has_file = file_path and Path(file_path).exists()

        cols = st.columns([0.4, 3, 0.8, 0.8, 0.6, 2.4])
        with cols[0]:
            st.write(icon)
        with cols[1]:
            st.write(f"**{title}**")
        with cols[2]:
            st.write(_dur_str(duration))
        with cols[3]:
            st.write(model)
        with cols[4]:
            st.write(file_type)
        with cols[5]:
            bc = st.columns(3)
            with bc[0]:
                if has_file and st.button("📂", key=f"o_{i}", help="폴더 열기"):
                    _open_folder(file_path)
            with bc[1]:
                if st.button("🔄", key=f"r_{i}", help="재생성"):
                    st.session_state["regenerate_song"] = song
            with bc[2]:
                if st.button("🗑", key=f"d_{i}", help="목록에서 제거"):
                    if has_file:
                        try:
                            Path(file_path).unlink()
                        except Exception:
                            pass
                    gen = st.session_state.get("generated_songs", [])
                    if i < len(gen):
                        gen.pop(i)
                    st.rerun()
