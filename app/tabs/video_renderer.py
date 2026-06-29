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
from services.video.overlay_assets import build_overlay_asset_library, build_overlay_asset_library_with_uploads
from services.video.visualizer import visualizer_config, VISUALIZER_STYLES
from services.video import render_plan as rp
from services.thumbnail import asset_types as AT
from services.thumbnail import session_store as ss
from services.thumbnail.video_renderer_rules import select_video_background


def render_video_renderer():
    """MP3-first Video Renderer entry point."""
    st.markdown("## 🎬 Video Renderer")
    st.caption("MP3-first 롱폼 뮤직비디오 · Canva 오버레이 · 오디오 반응형 비주얼라이저")

    # Live render progress (background full renders)
    _render_progress_panel()

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

    # Asset source: Canva uploads vs mock
    asset_mode = st.radio(
        "오버레이 자산 소스",
        ["Canva PNG 업로드", "Mock 자산 (테스트용 자동 생성)"],
        horizontal=True, key="vr_asset_mode",
        help="실제 사용 시 Canva에서 export한 PNG를 업로드하세요. Mock은 테스트 fallback입니다.",
    )
    uploaded_assets = {}
    if asset_mode.startswith("Canva"):
        with st.expander("📤 Canva PNG 업로드", expanded=True):
            up_cta = st.file_uploader("CTA 스티커 PNG", type=["png"], key="vr_up_cta")
            up_frame = st.file_uploader("비주얼라이저 프레임 PNG", type=["png"], key="vr_up_frame")
            up_now = st.file_uploader(
                "Now Playing 카드 PNG (트랙 순서대로 여러 개)", type=["png"],
                accept_multiple_files=True, key="vr_up_now",
            )
            if up_cta:
                uploaded_assets["cta"] = up_cta
            if up_frame:
                uploaded_assets["frame"] = up_frame
            if up_now:
                uploaded_assets["now_playing"] = up_now
            st.caption("업로드하지 않은 항목은 Mock으로 자동 대체됩니다.")

    st.session_state["vr_preview_cta"] = st.checkbox(
        "프리뷰에서 CTA 즉시 표시 (Preview CTA Now)", value=True, key="vr_prev_cta",
        help="프리뷰 짧은 클립 동안 CTA 스티커를 계속 보여줍니다.",
    )

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

        # Position / size controls
        st.markdown("**위치 / 크기 조정**")
        pcol1, pcol2, pcol3 = st.columns(3)
        with pcol1:
            viz_height = st.slider("높이 (px)", 60, 400, 160, key="vr_viz_h")
            viz_bottom = st.slider("하단 여백 (px)", 0, 400, 40, key="vr_viz_bm")
        with pcol2:
            viz_width = st.slider("너비 (%)", 10, 100, 100, key="vr_viz_w")
            viz_glow = st.slider("글로우 강도", 0.0, 10.0, 3.0, key="vr_viz_glow")
        with pcol3:
            use_custom_y = st.checkbox("Y 위치 직접 지정", value=False, key="vr_viz_use_y")
            viz_y = st.slider("Y 위치 (px)", 0, 1080, 880, key="vr_viz_y",
                              disabled=not use_custom_y)

        viz_cfg = visualizer_config(
            viz_style, viz_color, viz_height, viz_opacity, "bottom",
            y_position=(viz_y if use_custom_y else None),
            bottom_margin=viz_bottom, width_percent=viz_width,
            glow_strength=viz_glow,
        )

        # Visualizer frame controls (locked to visualizer by default)
        st.markdown("**Canva 프레임 정렬**")
        fcol1, fcol2 = st.columns(2)
        with fcol1:
            frame_lock = st.checkbox("프레임을 비주얼라이저 위치에 고정", value=True,
                                     key="vr_frame_lock",
                                     help="Canva 프레임과 동적 파형 위치를 자동 정렬합니다.")
        with fcol2:
            frame_opacity = st.slider("프레임 투명도", 0.0, 1.0, 1.0, key="vr_frame_op")
        st.session_state["vr_frame_cfg"] = {
            "lock_to_visualizer_position": frame_lock,
            "frame_opacity": frame_opacity,
        }
    else:
        viz_cfg = visualizer_config()
        st.session_state["vr_frame_cfg"] = {"lock_to_visualizer_position": True}

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
        # Build overlay PNGs — prefer uploaded Canva assets, fall back to mock
        uploaded_bytes = {}
        if uploaded_assets.get("cta"):
            uploaded_bytes["cta"] = uploaded_assets["cta"].getvalue()
        if uploaded_assets.get("frame"):
            uploaded_bytes["frame"] = uploaded_assets["frame"].getvalue()
        if uploaded_assets.get("now_playing"):
            uploaded_bytes["now_playing"] = [f.getvalue() for f in uploaded_assets["now_playing"]]
        lib = build_overlay_asset_library_with_uploads(
            session_path, plan, accent, uploaded=uploaded_bytes,
            make_center=en_center, center_title_text=selected_tracks[0]["name"],
        )
        plans = rp.build_render_plan(
            session_path, plan, bg_info, lib, viz_cfg,
            enable_now_playing=en_now, enable_cta=en_cta,
            enable_visualizer=en_viz, enable_center_title=en_center,
        )
        # Attach the visualizer frame config (lock/opacity) to the overlay plan
        plans["overlay_plan"]["visualizer_frame"] = st.session_state.get(
            "vr_frame_cfg", {"lock_to_visualizer_position": True})
        paths = rp.save_plans(out_dir, plans, plan)
        concat = rp.build_mp3_concat_list(out_dir, plan)

        if prev15 or prev30:
            seconds = 15 if prev15 else 30
            cmd = rp.build_preview_command(
                concat, bg_info.get("path") or "", out_dir, seconds,
                render_plan=plans["render_plan"], overlay_plan=plans["overlay_plan"],
                preview_cta_now=st.session_state.get("vr_preview_cta", True),
            )
            _run_or_show(cmd, f"{seconds}초 프리뷰")
        else:
            # Full render runs in a BACKGROUND WORKER (UI never blocks)
            cmd = rp.build_full_render_command(
                concat, bg_info.get("path") or "", out_dir, plan["total_seconds"],
                render_plan=plans["render_plan"], overlay_plan=plans["overlay_plan"],
            )
            from workflows.render_video import _ffmpeg_available
            if not _ffmpeg_available():
                st.warning("FFmpeg가 설치되어 있지 않습니다. 전체 렌더 명령:")
                st.code(" ".join(cmd["command"]))
            else:
                from services.video.render_job_store import launch_render_job
                job = launch_render_job(out_dir, cmd["command"],
                                        plan["total_seconds"], cmd["output"])
                st.session_state["active_render_job"] = job["render_job_id"]
                st.success(f"🎬 백그라운드 렌더 시작! (Job: {job['render_job_id']})")
                st.info("UI는 멈추지 않습니다. 아래 '렌더 진행 상황'에서 확인하세요.")
                st.rerun()

        # Show generated plans
        st.divider()
        st.markdown("**생성된 플랜 파일:**")
        for key, p in paths.items():
            st.caption(f"✅ {key}: {Path(p).name}")

        # Show layer order
        st.markdown("**오버레이 레이어 순서 (아래→위):**")
        st.code(" → ".join(plans["overlay_plan"]["layer_order"]))


def _render_progress_panel():
    """Show live progress + cancel for the active background render job, and
    recover it from disk after a Streamlit rerun / tab switch / refresh."""
    from services.video.render_job_store import (
        load_render_state, list_render_jobs, request_cancel,
    )
    # Recovery: prefer the session's active job; else the most recent ACTIVE one
    job_id = st.session_state.get("active_render_job")
    state = load_render_state(job_id) if job_id else None
    if not state:
        active = [j for j in list_render_jobs(20)
                  if j.get("status") in ("running", "cancelling", "queued")]
        if active:
            state = active[0]
            st.session_state["active_render_job"] = state["render_job_id"]

    if state:
        with st.container():
            st.markdown("#### 🎬 렌더 진행 상황")
            status = state.get("status", "")
            pct = state.get("progress_percent", 0) or 0
            jid = state["render_job_id"]

            if status in ("running", "cancelling"):
                st.progress(pct / 100)
                cur = int(state.get("current_time_sec", 0) or 0)
                total = int(state.get("total_seconds", 0) or 0)
                elapsed = int(state.get("elapsed_sec", 0) or 0)
                eta = state.get("eta_sec")
                speed = state.get("speed", "")
                cols = st.columns(4)
                cols[0].metric("진행률", f"{pct:.0f}%")
                cols[1].metric("렌더 위치", f"{cur//60}:{cur%60:02d} / {total//60}:{total%60:02d}")
                cols[2].metric("속도", speed or "—")
                cols[3].metric("남은 시간", f"{int(eta)//60}:{int(eta)%60:02d}" if eta else "계산 중")
                st.caption(f"경과: {elapsed//60}:{elapsed%60:02d} · "
                           f"worker_pid={state.get('worker_pid')} · ffmpeg_pid={state.get('ffmpeg_pid')}")

                bcol1, bcol2 = st.columns(2)
                with bcol1:
                    if st.button("🔄 새로고침", key="vr_refresh_progress", use_container_width=True):
                        st.rerun()
                with bcol2:
                    if status == "running":
                        if st.button("⏹️ 렌더 취소", key="vr_cancel_render", use_container_width=True):
                            request_cancel(jid)
                            st.warning("취소 요청됨 — FFmpeg를 종료하는 중입니다.")
                            st.rerun()
                    else:
                        st.button("⏳ 취소 중...", key="vr_cancelling", disabled=True,
                                  use_container_width=True)
            elif status == "completed":
                st.success(f"✅ 렌더 완료! → {Path(state.get('output_path','')).name}")
                out = state.get("output_path", "")
                if out and Path(out).exists():
                    st.video(out)
            elif status == "cancelled":
                st.info(f"⏹️ 렌더 취소됨 (파일은 보존됨): {Path(state.get('output_path','')).name}")
            elif status == "failed":
                st.error(f"❌ 렌더 실패: {state.get('last_message','')}")

            st.divider()

    # Render Job History
    _render_job_history()


def _render_job_history():
    """List recent render jobs (running/completed/failed/cancelled) with actions."""
    from services.video.render_job_store import list_render_jobs, get_render_log, _jobs_dir
    jobs = list_render_jobs(20)
    if not jobs:
        return

    with st.expander(f"📋 렌더 작업 내역 ({len(jobs)}개)", expanded=False):
        status_icon = {"running": "🟢", "cancelling": "🟡", "completed": "✅",
                       "failed": "❌", "cancelled": "⏹️", "queued": "⏳"}
        for j in jobs:
            jid = j["render_job_id"]
            icon = status_icon.get(j.get("status", ""), "•")
            cols = st.columns([3, 1, 1])
            with cols[0]:
                pct = j.get("progress_percent", 0) or 0
                st.write(f"{icon} `{jid}` · {j.get('status','')} · {pct:.0f}%")
            with cols[1]:
                if st.button("📂 폴더", key=f"vr_open_{jid}", use_container_width=True):
                    import subprocess, platform
                    folder = str(_jobs_dir() / jid)
                    try:
                        if platform.system() == "Windows":
                            subprocess.Popen(["explorer", folder])
                        elif platform.system() == "Darwin":
                            subprocess.Popen(["open", folder])
                        else:
                            subprocess.Popen(["xdg-open", folder])
                    except Exception:
                        st.caption(folder)
            with cols[2]:
                if st.button("📄 로그", key=f"vr_log_{jid}", use_container_width=True):
                    st.session_state["vr_view_log"] = jid
                    st.rerun()

            # Show log if selected
            if st.session_state.get("vr_view_log") == jid:
                log = get_render_log(jid, last_n=30)
                if log:
                    st.code("\n".join(f"[{l.get('level','info')}] {l.get('message','')}"
                                       for l in log))
                else:
                    st.caption("로그가 없습니다.")


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
