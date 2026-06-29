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
        "🖼️ Thumbnail Studio",
        "🎬 영상 제작",
        "▶️ YouTube",
        "📦 배포",
    ])

    with tab1:
        render_song_lab()
    with tab2:
        # v0.6.0: new Thumbnail Studio (Flow prompts + candidate gallery + Canva branding)
        from app.tabs.thumbnail_studio import render_thumbnail_studio
        render_thumbnail_studio()
    with tab3:
        # v0.7.1: MP3-first Video Renderer (Canva overlays + audio-reactive visualizer)
        from app.tabs.video_renderer import render_video_renderer
        render_video_renderer()
    with tab4:
        # v0.8.0: YouTube Package Studio (manual package + optional private API upload)
        from app.tabs.youtube_package import render_youtube_package
        render_youtube_package()
    with tab5:
        render_tab_distribution()


def render_home_tabs():
    """
    Home screen tabs. v0.8.1: Video Renderer and YouTube Package are now
    available here too — they scan the global outputs/ folder and do not need
    an open project. Song Lab / Thumbnail Studio / Project management keep
    their existing behavior; only tab exposure changed (no logic changes).
    """
    tab_lab, tab_thumb, tab_video, tab_youtube, tab_project = st.tabs(
        ["🎵 Song Lab", "🖼️ Thumbnail Studio", "🎬 Video Renderer",
         "▶️ YouTube Package", "📁 프로젝트 관리"]
    )

    with tab_lab:
        render_song_lab()

    with tab_thumb:
        from app.tabs.thumbnail_studio import render_thumbnail_studio
        render_thumbnail_studio()

    with tab_video:
        # v0.8.1: usable without an open project (scans outputs/ globally)
        st.info("프로젝트를 열지 않아도 기존 outputs 폴더의 MP3와 썸네일을 "
                "선택해 영상을 만들 수 있습니다.")
        from app.tabs.video_renderer import render_video_renderer
        render_video_renderer()

    with tab_youtube:
        # v0.8.1: usable without an open project (scans outputs/ globally)
        st.info("생성된 final_video.mp4와 YouTube 썸네일을 선택해 "
                "업로드 패키지를 만들 수 있습니다.")
        from app.tabs.youtube_package import render_youtube_package
        render_youtube_package()

    with tab_project:
        render_project_screen()
