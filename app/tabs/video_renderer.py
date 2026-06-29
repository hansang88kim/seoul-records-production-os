"""
app/tabs/video_renderer.py — MP3-first Video Renderer (v0.7.1).

Replaces the old WAV/static-image flow. Scans MP3s, builds a target-duration
playlist, picks the clean playback background, generates Canva overlay PNGs,
and renders preview/full MP4 with audio-reactive visualizer.

Does NOT touch music generation or Thumbnail Studio export logic.
"""
from __future__ import annotations

from pathlib import Path
import streamlit as st

from services.video.playlist_builder import (
    scan_mp3_files, build_playlist_plan, format_chapters_txt,
)
from services.video.overlay_assets import build_overlay_asset_library
from services.video.visualizer import visualizer_config, VISUALIZER_STYLES
from services.video import render_plan as rp
from services.thumbnail import asset_types as AT
from services.thumbnail import session_store as ss
from services.thumbnail.video_renderer_rules import select_video_background


def render_video_renderer():
    """MP3-first Video Renderer entry point."""
    st.markdown("## 🎬 Video Renderer")
    st.caption("MP3-first 롱폼 뮤직비디오 · Canva 오버레이 · 오디오 반응형 비주얼라이저")

    # ── 1. MP3 playlist ──────────────────────────────────────────────
    st.markdown("#### 1️⃣ MP3 플레이리스트")
    tracks = scan_mp3_files()
    if not tracks:
        st.warning("⚠️ outputs/ 에서 MP3를 찾을 수 없습니다. 먼저 Song Lab에서 곡을 생성하세요.")
        st.caption("WAV는 필요하지 않습니다 — MP3만 있으면 됩니다.")
        return

    st.caption(f"발견된 MP3: {len(tracks)}개 (WAV 불필요)")
    labels = [f"{t['name']} ({int(t['duration_sec'])//60}:{int(t['duration_sec'])%60:02d}) · {t['source']}"
              for t in tracks]
    chosen_idx = st.multiselect(
        "플레이리스트에 포함할 MP3 선택 (순서대로)",
        range(len(tracks)), format_func=lambda i: labels[i],
        default=list(range(min(len(tracks), 10))),
    )
    selected_tracks = [tracks[i] for i in chosen_idx]

    if not selected_tracks:
        st.info("MP3를 하나 이상 선택하세요.")
        return

    col1, col2 = st.columns(2)
    with col1:
        target = st.radio("목표 길이", [60, 65, 70], horizontal=True,
                          format_func=lambda m: f"{m}분", key="vr_target")
    with col2:
        repeat = st.checkbox("목표 길이까지 반복 재생", value=True, key="vr_repeat",
                            help="선택한 곡들을 목표 시간에 도달할 때까지 반복합니다.")

    plan = build_playlist_plan(selected_tracks, target, repeat)
    total_min = int(plan["total_seconds"]) // 60
    total_sec = int(plan["total_seconds"]) % 60
    st.success(f"📋 플레이리스트: {len(plan['entries'])}개 트랙 · 총 {total_min}:{total_sec:02d} "
               f"({len(plan['chapters'])}개 챕터)")

    # ── 2. Background ────────────────────────────────────────────────
    st.markdown("#### 2️⃣ 재생 배경")
    thumb_sessions = ss.list_sessions(limit=20)
    if not thumb_sessions:
        st.warning("⚠️ Thumbnail Studio에서 video_playback_background를 먼저 내보내세요.")
        st.caption("배경 없이도 플레이리스트 플랜은 저장할 수 있습니다.")
        bg_info = {"asset_type": None, "path": None, "is_clean_playback": False,
                   "warning": "배경 없음"}
    else:
        sess_labels = {f"{s['session_id']} ({s['country']})": s["session_id"]
                       for s in thumb_sessions}
        sel_sess = st.selectbox("Thumbnail 세션 선택", list(sess_labels.keys()))
        sess_id = sess_labels[sel_sess]
        bg_info = select_video_background(sess_id)

        if bg_info["asset_type"] == AT.VIDEO_PLAYBACK_BACKGROUND_16X9:
            st.success(f"✅ 깨끗한 재생 배경 사용: video_playback_background_16x9")
            if bg_info["path"] and Path(bg_info["path"]).exists():
                st.image(bg_info["path"], width=320)
        elif bg_info["asset_type"] == AT.YOUTUBE_THUMBNAIL_16X9:
            st.warning(f"⚠️ {bg_info['warning']}")
            if bg_info["path"] and Path(bg_info["path"]).exists():
                st.image(bg_info["path"], width=320)
        else:
            st.error("사용 가능한 배경이 없습니다.")

    # ── 3. Overlay assets ────────────────────────────────────────────
    st.markdown("#### 3️⃣ Canva 오버레이 자산")
    st.caption("모든 텍스트/스티커는 Canva PNG 오버레이입니다 (FFmpeg drawtext 미사용).")
    ocol1, ocol2, ocol3, ocol4 = st.columns(4)
    with ocol1:
        en_now = st.checkbox("Now Playing", value=True, key="vr_now")
    with ocol2:
        en_cta = st.checkbox("CTA 스티커", value=True, key="vr_cta")
    with ocol3:
        en_viz = st.checkbox("비주얼라이저", value=True, key="vr_viz")
    with ocol4:
        en_center = st.checkbox("중앙 타이틀", value=False, key="vr_center",
                               help="기본 OFF — 재생 영상에는 보통 사용하지 않습니다.")

    # ── 4. Visualizer ────────────────────────────────────────────────
    if en_viz:
        st.markdown("#### 4️⃣ 비주얼라이저 (오디오 반응형)")
        vcol1, vcol2, vcol3 = st.columns(3)
        with vcol1:
            viz_style = st.selectbox("스타일", VISUALIZER_STYLES,
                                     format_func=lambda s: {
                                         "minimal_wave": "Minimal Wave Line",
                                         "soft_eq_bars": "Soft Equalizer Bars",
                                         "citypop_glow": "CityPop Glow Wave",
                                     }.get(s, s), key="vr_viz_style")
        with vcol2:
            viz_color = st.color_picker("색상", "#ff4d6d", key="vr_viz_color")
        with vcol3:
            viz_opacity = st.slider("투명도", 0.0, 1.0, 0.85, key="vr_viz_op")
        viz_cfg = visualizer_config(viz_style, viz_color, 160, viz_opacity, "bottom")
    else:
        viz_cfg = visualizer_config()

    # ── 5. Render ────────────────────────────────────────────────────
    st.markdown("#### 5️⃣ 렌더링")
    st.caption("Full 렌더 전에 짧은 프리뷰로 시각 효과를 확인하세요.")

    from app.config import APP_VERSION
    out_dir = str(Path("outputs") / "video_renders" / f"render_{plan['target_seconds']}s")

    # Build overlay library + plans (in-memory; assets generated on demand)
    session_path = str(Path("outputs") / "video_renders" / "session")

    rcol1, rcol2, rcol3 = st.columns(3)
    with rcol1:
        prev15 = st.button("▶️ 15초 프리뷰", use_container_width=True)
    with rcol2:
        prev30 = st.button("▶️ 30초 프리뷰", use_container_width=True)
    with rcol3:
        full = st.button("🎬 전체 렌더링", type="primary", use_container_width=True)

    if prev15 or prev30 or full:
        accent = viz_cfg.get("color", "#ff4d6d")
        # Generate Canva overlay PNGs
        lib = build_overlay_asset_library(session_path, plan, accent,
                                          make_center=en_center,
                                          center_title_text=selected_tracks[0]["name"])
        plans = rp.build_render_plan(
            session_path, plan, bg_info, lib, viz_cfg,
            enable_now_playing=en_now, enable_cta=en_cta,
            enable_visualizer=en_viz, enable_center_title=en_center,
        )
        paths = rp.save_plans(out_dir, plans, plan)
        concat = rp.build_mp3_concat_list(out_dir, plan)

        if prev15 or prev30:
            seconds = 15 if prev15 else 30
            cmd = rp.build_preview_command(concat, bg_info.get("path") or "", out_dir, seconds)
            _run_or_show(cmd, f"{seconds}초 프리뷰")
        else:
            cmd = rp.build_full_render_command(concat, bg_info.get("path") or "", out_dir,
                                               plan["total_seconds"])
            _run_or_show(cmd, "전체 영상")

        # Show generated plans
        st.divider()
        st.markdown("**생성된 플랜 파일:**")
        for key, p in paths.items():
            st.caption(f"✅ {key}: {Path(p).name}")

        # Show layer order
        st.markdown("**오버레이 레이어 순서 (아래→위):**")
        st.code(" → ".join(plans["overlay_plan"]["layer_order"]))


def _run_or_show(cmd: dict, label: str):
    """Run FFmpeg if available, else show the command."""
    from workflows.render_video import _ffmpeg_available
    import subprocess

    if not _ffmpeg_available():
        st.warning(f"FFmpeg가 설치되어 있지 않습니다. {label} 렌더 명령:")
        st.code(" ".join(cmd["command"]))
        return

    bg = cmd["command"]
    # Check background exists
    try:
        with st.spinner(f"{label} 렌더링 중..."):
            result = subprocess.run(cmd["command"], capture_output=True, text=True, timeout=600)
        if result.returncode == 0 and Path(cmd["output"]).exists():
            st.success(f"✅ {label} 완료!")
            st.video(cmd["output"])
        else:
            st.error(f"렌더 실패. 명령을 확인하세요:")
            st.code(" ".join(cmd["command"]))
            if result.stderr:
                st.caption(result.stderr[-500:])
    except Exception as e:
        st.error(f"렌더 오류: {e}")
        st.code(" ".join(cmd["command"]))
