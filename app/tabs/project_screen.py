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
    st.markdown("# 🎵 Seoul Records Production OS")
    st.caption("AI 시티팝 음악 레이블 프로덕션 하네스")
    st.divider()

    col_new, col_sep, col_resume = st.columns([5, 1, 5])

    # ── 새 프로젝트 ──────────────────────────────────────────────────────────
    with col_new:
        st.markdown("### ✨ 새 프로젝트")

        project_name = st.text_input(
            "프로젝트 이름",
            placeholder="예: Seoul Night Vol. 1",
        )

        theme = st.text_input(
            "테마",
            placeholder="예: 늦은 밤 드라이브, 비 오는 도시, 여름 이별",
        )

        col_tracks, col_mode = st.columns(2)
        with col_tracks:
            track_count = st.selectbox("트랙 수", TRACK_COUNT_OPTIONS, index=1)
        with col_mode:
            production_mode = st.selectbox("모드", PRODUCTION_MODES)

        language_pack = st.selectbox(
            "언어팩",
            ["ko_kr_seoul"],
            help="향후: Tokyo, Saigon, Bangkok, Taipei, Hong Kong 등",
        )

        output_type = st.selectbox("출력 형식", OUTPUT_TYPES, index=2)

        if project_name:
            from app.project_manager import build_output_folder_name
            folder = build_output_folder_name(project_name, language_pack)
            st.caption(f"📁 `outputs/{folder}/`")

        st.markdown("")
        if st.button("🚀 프로젝트 생성", type="primary", use_container_width=True):
            if not project_name.strip():
                st.error("프로젝트 이름을 입력하세요")
            else:
                with st.spinner("생성 중..."):
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
                st.success(f"'{project_name}' 생성 완료!")
                st.rerun()

    # ── 구분선 ───────────────────────────────────────────────────────────────
    with col_sep:
        st.markdown("")

    # ── 기존 프로젝트 ─────────────────────────────────────────────────────────
    with col_resume:
        from app.tabs.project_library import render_project_library_panel
        render_project_library_panel()
