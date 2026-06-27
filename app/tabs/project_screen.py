"""
Seoul Records Production OS — Project Creation & Resume Screen
"""
import json
from pathlib import Path
from datetime import datetime

import streamlit as st
from app.config import (
    APP_NAME, TRACK_COUNT_OPTIONS, OUTPUT_TYPES, PRODUCTION_MODES, OUTPUTS_DIR
)
from app.project_manager import create_project, list_projects, resume_project


def render_project_screen():
    st.title(f"🎵 {APP_NAME}")
    st.markdown("### Seoul Records City Pop Production OS")
    st.caption("Create a new project or resume an existing one.")
    st.divider()

    col_new, col_resume = st.columns([1, 1], gap="large")

    # ── NEW PROJECT ───────────────────────────────────────────────────────────
    with col_new:
        st.markdown("#### ✨ New Project")

        project_name = st.text_input(
            "Project Name",
            placeholder="e.g. Seoul Night Vol. 1",
            help="This will become your output folder name.",
        )

        st.text_input(
            "Core Style",
            value="Seoul Records City Pop",
            disabled=True,
            help="Core style is fixed. Creative direction is set by the preset system.",
        )

        language_pack = st.selectbox(
            "Language / Market Pack",
            ["ko_kr_seoul"],
            help="Future packs: Tokyo, Saigon, Bangkok, Taipei, Hong Kong…",
        )

        theme = st.text_input(
            "Theme",
            placeholder="e.g. Late Night Drive, Rainy City, Summer Farewell",
        )

        track_count = st.selectbox(
            "Track Count",
            TRACK_COUNT_OPTIONS,
            index=1,
        )

        production_mode = st.radio(
            "Production Mode",
            PRODUCTION_MODES,
            horizontal=True,
        )

        output_type = st.selectbox(
            "Output Type",
            OUTPUT_TYPES,
            index=2,
        )

        # Preview output folder
        if project_name:
            from app.project_manager import build_output_folder_name
            folder = build_output_folder_name(project_name, language_pack)
            st.caption(f"📁 Output folder: `outputs/{folder}/`")

        st.divider()

        if st.button("🚀 Create Project", type="primary", use_container_width=True):
            if not project_name.strip():
                st.error("Project name is required.")
            else:
                with st.spinner("Creating project…"):
                    manifest, output_folder = create_project(
                        project_name=project_name.strip(),
                        theme=theme.strip(),
                        track_count=track_count,
                        production_mode=production_mode,
                        output_type=output_type,
                        language_pack=language_pack,
                    )
                    st.session_state.current_project = manifest
                    st.session_state.current_output_folder = str(output_folder)
                st.success(f"Project '{project_name}' created!")
                st.rerun()

    # ── PROJECT LIBRARY ───────────────────────────────────────────────────────
    with col_resume:
        from app.tabs.project_library import render_project_library_panel
        render_project_library_panel()
