"""
Seoul Records Production OS — Dashboard / Router
"""
import streamlit as st
from app.config import APP_NAME, APP_VERSION
from app.tabs.project_screen import render_project_screen
from app.tabs.tab1_song_generation import render_tab_song_generation
from app.tabs.tab2_thumbnail import render_tab_thumbnail
from app.tabs.tab3_video import render_tab_video
from app.tabs.tab4_youtube import render_tab_youtube
from app.tabs.tab5_distribution import render_tab_distribution


def render_dashboard():
    # Sidebar
    with st.sidebar:
        st.markdown(f"## 🎵 {APP_NAME}")
        st.caption(f"v{APP_VERSION} · Seoul Records")
        st.divider()

        if "current_project" in st.session_state and st.session_state.current_project:
            manifest = st.session_state.current_project
            st.markdown(f"**{manifest.project_name}**")
            st.caption(f"📁 {manifest.language_pack}")
            st.caption(f"🎚 {manifest.production_mode} Mode")
            st.caption(f"🎵 {manifest.track_count} tracks")
            st.divider()
            _status_color = {
                "project_created": "🟡",
                "song_generation_ready": "🟡",
                "song_generation_in_progress": "🔵",
                "song_generation_completed": "🟢",
                "thumbnail_completed": "🟢",
                "video_rendered": "🟢",
                "completed": "✅",
                "failed": "🔴",
                "paused": "⏸",
            }
            icon = _status_color.get(manifest.status, "⚪")
            st.caption(f"Status: {icon} {manifest.status}")
            st.divider()

            completed = sum(1 for t in manifest.tracks if t.status in ("saved", "approved"))
            total = manifest.track_count
            if total > 0:
                st.progress(completed / total, text=f"Tracks: {completed}/{total}")
            st.divider()

            if st.button("🔄 Close Project", use_container_width=True):
                st.session_state.current_project = None
                st.session_state.current_output_folder = None
                st.rerun()
        else:
            st.caption("No project open")

        st.divider()
        st.caption("Seoul Records City Pop Core")
        st.caption("© Seoul Records")

    # Main content
    if "current_project" not in st.session_state:
        st.session_state.current_project = None
        st.session_state.current_output_folder = None

    if st.session_state.current_project is None:
        render_project_screen()
    else:
        render_production_tabs()


def render_production_tabs():
    manifest = st.session_state.current_project
    st.title(f"🎵 {manifest.project_name}")
    st.caption(f"Seoul Records City Pop · {manifest.language_pack} · {manifest.production_mode} Mode")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🎵 Song Generation",
        "🖼 Thumbnail & Cover",
        "🎬 Longform Video",
        "▶️ YouTube Upload",
        "📦 Distribution",
    ])

    with tab1:
        render_tab_song_generation()

    with tab2:
        render_tab_thumbnail()

    with tab3:
        render_tab_video()

    with tab4:
        render_tab_youtube()

    with tab5:
        render_tab_distribution()
