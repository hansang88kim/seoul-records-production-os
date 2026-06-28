"""
Seoul Records Production OS — Dashboard / Router
"""
import streamlit as st
from app.config import APP_NAME, APP_VERSION
from app.tabs.project_screen import render_project_screen
from app.tabs.song_lab import render_song_lab
from app.tabs.tab1_song_generation import render_tab_song_generation
from app.tabs.tab2_thumbnail import render_tab_thumbnail
from app.tabs.tab3_video import render_tab_video
from app.tabs.tab4_youtube import render_tab_youtube
from app.tabs.tab5_distribution import render_tab_distribution


def render_dashboard():
    # ── Sidebar: Project Info ────────────────────────────────────────────────
    with st.sidebar:
        if "current_project" in st.session_state and st.session_state.current_project:
            manifest = st.session_state.current_project

            st.markdown(f"##### 📁 {manifest.project_name}")

            # Status
            _icons = {
                "project_created": "🟡", "song_generation_ready": "🟡",
                "song_generation_in_progress": "🔵", "song_generation_completed": "🟢",
                "thumbnail_completed": "🟢", "video_rendered": "🟢",
                "completed": "✅", "failed": "🔴", "paused": "⏸",
            }
            icon = _icons.get(manifest.status, "⚪")
            status_label = manifest.status.replace("_", " ").title()
            st.caption(f"{icon} {status_label}")

            # Progress
            completed = sum(1 for t in manifest.tracks if t.status in ("saved", "approved"))
            total = manifest.track_count
            if total > 0:
                st.progress(completed / total)
                st.caption(f"트랙 진행: {completed}/{total}")

            # Info
            col1, col2 = st.columns(2)
            with col1:
                st.caption(f"🌏 {manifest.language_pack}")
            with col2:
                st.caption(f"🎚 {manifest.production_mode}")

            st.divider()

            if st.button("📂 프로젝트 닫기", use_container_width=True):
                st.session_state.current_project = None
                st.session_state.current_output_folder = None
                st.rerun()
        else:
            st.caption("프로젝트를 선택하세요")

        st.divider()
        st.caption("© Seoul Records")

    # ── Main Content ─────────────────────────────────────────────────────────
    if "current_project" not in st.session_state:
        st.session_state.current_project = None
        st.session_state.current_output_folder = None

    if st.session_state.current_project is None:
        # No project open — show Song Lab with project creation integrated
        render_home_tabs()
    else:
        render_production_tabs()


def render_production_tabs():
    manifest = st.session_state.current_project

    # Header
    st.markdown(f"# 🎵 {manifest.project_name}")
    col1, col2, col3 = st.columns(3)
    with col1:
        completed = sum(1 for t in manifest.tracks if t.status in ("saved", "approved"))
        st.metric("완료 트랙", f"{completed}/{manifest.track_count}")
    with col2:
        st.metric("모드", manifest.production_mode)
    with col3:
        st.metric("출력", manifest.output_type or "—")

    st.divider()

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🎵 Song Lab",
        "🖼️ 썸네일",
        "🎬 영상 제작",
        "▶️ YouTube",
        "📦 배포",
    ])

    with tab1:
        render_song_lab()
    with tab2:
        render_tab_thumbnail()
    with tab3:
        render_tab_video()
    with tab4:
        render_tab_youtube()
    with tab5:
        render_tab_distribution()


def render_home_tabs():
    """Home screen: Song Lab + Project management in tabs."""
    tab_lab, tab_project = st.tabs(["🎵 Song Lab", "📁 프로젝트 관리"])

    with tab_lab:
        render_song_lab()

    with tab_project:
        render_project_screen()
