"""
app/ui/song_card.py — Generated Song Card Component
"""
from __future__ import annotations
from pathlib import Path
import streamlit as st


_STATUS_ICONS = {
    "queued": "⏳",
    "generating": "🔄",
    "completed": "✅",
    "failed": "❌",
    "imported": "📥",
    "mp3_only_preview": "⚠️",
}


def render_song_card(song: dict, index: int):
    """
    Render a single song result card.
    song dict keys: title, status, provider, model, duration, file_type,
                    file_path, distribution_eligible, created_at, clip_id
    """
    icon = _STATUS_ICONS.get(song.get("status", ""), "⚪")
    title = song.get("title", "Untitled")
    status = song.get("status", "unknown")
    duration = song.get("duration")
    model = song.get("model", "—")
    file_type = song.get("file_type", "—").upper()
    eligible = song.get("distribution_eligible", False)

    dur_str = f"{int(duration//60)}:{int(duration%60):02d}" if duration else "—"
    elig_badge = "🟢 배포 가능" if eligible else "🟡 미리듣기만"

    with st.container():
        col_info, col_meta, col_actions = st.columns([4, 3, 3])

        with col_info:
            st.markdown(f"**{icon} {title}**")
            st.caption(f"{status} · {song.get('provider', '—')}")

        with col_meta:
            st.caption(f"🤖 {model} · ⏱️ {dur_str} · 📄 {file_type}")
            st.caption(elig_badge)

        with col_actions:
            file_path = song.get("file_path", "")
            col_a, col_b = st.columns(2)
            with col_a:
                if file_path and Path(file_path).exists():
                    if st.button("📂 열기", key=f"open_{index}", use_container_width=True):
                        import subprocess, platform
                        folder = str(Path(file_path).parent)
                        if platform.system() == "Windows":
                            subprocess.Popen(["explorer", folder])
                        elif platform.system() == "Darwin":
                            subprocess.Popen(["open", folder])
                        else:
                            subprocess.Popen(["xdg-open", folder])
            with col_b:
                if st.button("🔄 재생성", key=f"regen_{index}", use_container_width=True):
                    st.session_state["regenerate_song"] = song

        st.divider()


def render_song_list(songs: list[dict]):
    """Render the generated songs list."""
    if not songs:
        st.caption("아직 생성된 곡이 없습니다. 위에서 Generate를 눌러주세요.")
        return

    st.markdown(f"##### 🎵 생성된 곡 ({len(songs)}곡)")
    for i, song in enumerate(songs):
        render_song_card(song, i)
