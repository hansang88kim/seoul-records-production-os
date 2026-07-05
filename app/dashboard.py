"""
Seoul Records Production OS — Dashboard / Router (v1.0.0-alpha.31)

Sidebar navigation model: app/main.py owns a vertical nav in the sidebar and
stores the current page in st.session_state["nav_page"]. render_dashboard()
routes to the matching page. The old horizontal st.tabs()-based navigation
(render_home_tabs / render_production_tabs) is replaced by this router; every
individual page's render_* function is unchanged.
"""
import streamlit as st
from pathlib import Path
from app.tabs.project_screen import render_project_screen
from app.tabs.song_lab import render_song_lab


def render_dashboard(page: str = "dashboard"):
    if "current_project" not in st.session_state:
        st.session_state.current_project = None
        st.session_state.current_output_folder = None

    if page == "song_lab":
        # Song Lab
        render_song_lab()
    elif page == "thumbnail":
        # Thumbnail Studio
        from app.tabs.thumbnail_studio import render_thumbnail_studio
        render_thumbnail_studio()
    elif page == "video":
        # Video Renderer
        from app.tabs.video_renderer import render_video_renderer
        render_video_renderer()
    elif page == "youtube":
        # YouTube Package
        from app.tabs.youtube_package import render_youtube_package
        render_youtube_package()
    elif page == "qa":
        # Production QA
        from app.tabs.production_qa_tab import render_production_qa
        render_production_qa()
    elif page == "um":
        # UnitedMasters
        from app.tabs.unitedmasters_tab import render_unitedmasters
        render_unitedmasters()
    elif page == "history":
        # History
        render_history()
    elif page == "library":
        # Library
        render_library()
    elif page == "project":
        # 프로젝트 관리
        render_project_screen()
    else:
        render_home()


def _card_metric(col, label: str, value, color: str):
    with col:
        with st.container(border=True):
            st.markdown(
                f"<div style='color:#6b6c78;font-size:0.72rem;text-transform:uppercase;"
                f"letter-spacing:0.5px'>{label}</div>"
                f"<div style='font-size:1.6rem;font-weight:700;color:{color};margin-top:2px'>{value}</div>",
                unsafe_allow_html=True,
            )


def render_home():
    """
    Real-data dashboard landing page. Every number here is read straight from
    job_store / project_manager — no mock/placeholder data (unlike the
    frontend/ Next.js console's mock-first snapshot).
    """
    st.markdown("# 🏠 Dashboard")
    st.caption("전체 제작 파이프라인 상태와 다음 작업을 한눈에 확인합니다.")

    # ── Current project banner (if one is open) ─────────────────────────
    manifest = st.session_state.get("current_project")
    if manifest:
        with st.container(border=True):
            col_a, col_b = st.columns([4, 1])
            with col_a:
                st.markdown(f"##### 📁 현재 프로젝트: {manifest.project_name}")
                completed = sum(1 for t in manifest.tracks if t.status in ("saved", "approved"))
                total = manifest.track_count
                if total > 0:
                    st.progress(completed / total)
                    st.caption(f"트랙 진행: {completed}/{total} · {manifest.language_pack} · {manifest.production_mode}")
            with col_b:
                st.write("")
                if st.button("프로젝트 닫기", use_container_width=True, key="dash_close_project"):
                    st.session_state.current_project = None
                    st.session_state.current_output_folder = None
                    st.rerun()
        st.write("")

    # ── Real counts ───────────────────────────────────────────────────────
    try:
        from app.project_manager import list_song_projects
        song_projects = list_song_projects()
    except Exception:
        song_projects = []
    total_songs = sum(p.get("song_count", 0) for p in song_projects)

    try:
        from services.job_store import get_active_jobs, list_jobs
        from services.generation_job_manager import get_queued_jobs
        active_jobs = [j for j in get_active_jobs() if j.get("status") == "running"]
        queued_jobs = get_queued_jobs()
        recent_jobs = list_jobs(limit=5)
    except Exception:
        active_jobs, queued_jobs, recent_jobs = [], [], []

    col1, col2, col3, col4 = st.columns(4)
    _card_metric(col1, "프로젝트", len(song_projects), "#7fd4e8")
    _card_metric(col2, "생성된 곡", total_songs, "#e8c37c")
    _card_metric(col3, "진행 중 작업", len(active_jobs), "#e8639f")
    _card_metric(col4, "대기열", len(queued_jobs), "#74d9a0")

    st.write("")

    # ── Quick actions ────────────────────────────────────────────────────
    st.markdown("##### 바로가기")

    def _goto(key):
        st.session_state.nav_page = key
        st.rerun()

    qa1, qa2, qa3, qa4, qa5 = st.columns(5)
    with qa1:
        if st.button("🎵 곡 생성", use_container_width=True, key="dash_go_song"):
            _goto("song_lab")
    with qa2:
        if st.button("🖼️ 썸네일 제작", use_container_width=True, key="dash_go_thumb"):
            _goto("thumbnail")
    with qa3:
        if st.button("🎬 영상 렌더링", use_container_width=True, key="dash_go_video"):
            _goto("video")
    with qa4:
        if st.button("▶️ YouTube 패키지", use_container_width=True, key="dash_go_yt"):
            _goto("youtube")
    with qa5:
        if st.button("✅ QA 확인", use_container_width=True, key="dash_go_qa"):
            _goto("qa")

    st.write("")
    col_left, col_right = st.columns([3, 2])

    # ── Recent songs ─────────────────────────────────────────────────────
    with col_left:
        st.markdown("##### 최근 생성 곡")
        recent_songs = []
        try:
            from app.project_manager import get_song_project_songs
            for p in song_projects[:5]:
                recent_songs.extend(get_song_project_songs(p["name"])[:3])
        except Exception:
            pass

        with st.container(border=True):
            if recent_songs:
                for s in recent_songs[:8]:
                    dur = s.get("duration")
                    dur_str = f"{int(dur // 60)}:{int(dur % 60):02d}" if dur else "—"
                    st.markdown(
                        "<div style='display:flex;justify-content:space-between;padding:0.35rem 0;"
                        "border-bottom:1px solid #34353f55'>"
                        f"<span style='color:#f4f4f6;font-size:0.85rem'>{s.get('title', '제목 없음')}</span>"
                        f"<span style='color:#6b6c78;font-size:0.78rem'>{dur_str}</span></div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("아직 생성된 곡이 없습니다. Song Lab에서 시작하세요.")

    # ── Active / queued / recently-completed jobs ───────────────────────
    with col_right:
        st.markdown("##### 활성 작업")
        with st.container(border=True):
            if active_jobs:
                for j in active_jobs:
                    pct = j.get("progress_percent", 0) or 0
                    title = j.get("current_track_title", "")
                    st.progress(pct / 100)
                    st.caption(f"🎵 {title} · {j.get('completed_tracks', 0)}/{j.get('total_tracks', 0)}곡 · {j.get('project', '?')}")
            elif queued_jobs:
                for qi, j in enumerate(queued_jobs):
                    st.caption(f"⏳ 대기 {qi + 1}. {j.get('project', '?')} · {j.get('total_tracks', 0)}곡")
            else:
                st.caption("진행 중인 작업이 없습니다.")

            completed = [j for j in recent_jobs if j.get("status") in ("completed", "partially_failed")]
            if completed:
                st.markdown(
                    "<div style='margin-top:0.6rem;color:#6b6c78;font-size:0.7rem;"
                    "text-transform:uppercase;letter-spacing:1px'>최근 완료</div>",
                    unsafe_allow_html=True,
                )
                for j in completed[:3]:
                    icon = "✅" if j["status"] == "completed" else "⚠️"
                    st.caption(f"{icon} {j.get('project', '?')} · {j.get('completed_tracks', 0)}/{j.get('total_tracks', 0)}곡")


_MODE_LABELS = {
    "auto_batch": "🎵 곡 생성",
    "thumbnail_batch": "🖼️ 썸네일 생성",
}
_STATUS_LABELS = {
    "running": "🔵 진행 중",
    "queued": "⏳ 대기 중",
    "completed": "✅ 완료",
    "partially_failed": "⚠️ 일부 실패",
    "failed": "🔴 실패",
}


def render_history():
    """
    All job history (song generation + thumbnail generation) in one place —
    job_store is generic across modes, so this just lists everything with a
    status/mode filter. v1.0.0-alpha.38.
    """
    st.markdown("# 📜 History")
    st.caption("곡 생성과 썸네일 생성 작업 이력을 한 곳에서 확인합니다.")

    try:
        from services.job_store import list_jobs
        all_jobs = list_jobs(limit=100)
    except Exception:
        all_jobs = []

    if not all_jobs:
        st.info("아직 작업 이력이 없습니다.")
        return

    col1, col2 = st.columns(2)
    with col1:
        status_opt = st.selectbox(
            "상태", ["전체"] + list(_STATUS_LABELS.values()), key="hist_status_filter",
        )
    with col2:
        mode_opt = st.selectbox(
            "종류", ["전체"] + list(_MODE_LABELS.values()), key="hist_mode_filter",
        )

    def _match(j):
        if status_opt != "전체" and _STATUS_LABELS.get(j.get("status"), j.get("status")) != status_opt:
            return False
        if mode_opt != "전체" and _MODE_LABELS.get(j.get("mode"), j.get("mode")) != mode_opt:
            return False
        return True

    filtered = [j for j in all_jobs if _match(j)]
    st.caption(f"{len(filtered)}개 작업 표시 중 (전체 {len(all_jobs)}개)")

    for j in filtered:
        mode_label = _MODE_LABELS.get(j.get("mode"), j.get("mode", "?"))
        status_label = _STATUS_LABELS.get(j.get("status"), j.get("status", "?"))
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 2])
            with c1:
                st.markdown(f"**{j.get('project', '?')}**")
                st.caption(f"{mode_label} · job_id: {j.get('job_id', '')}")
            with c2:
                st.caption(status_label)
                total = j.get("total_tracks", 0) or 0
                if total:
                    st.progress(min(1.0, (j.get("completed_tracks", 0) or 0) / total))
                    st.caption(f"{j.get('completed_tracks', 0)}/{total} 완료 · "
                              f"실패 {j.get('failed_tracks', 0)}")
            with c3:
                st.caption(f"생성: {(j.get('created_at') or '')[:19].replace('T', ' ')}")
                if j.get("completed_at"):
                    st.caption(f"완료: {j['completed_at'][:19].replace('T', ' ')}")
            if j.get("last_message"):
                st.caption(f"💬 {j['last_message']}")


def render_library():
    """
    Browse all saved generation results — songs (project_manager) and
    thumbnail images (thumbnail session_store) — in one place.
    v1.0.0-alpha.38.
    """
    st.markdown("# 📚 Library")
    st.caption("지금까지 생성한 곡과 이미지를 한 곳에서 확인합니다.")

    lib_tab_songs, lib_tab_images = st.tabs(["🎵 곡 라이브러리", "🖼️ 이미지 라이브러리"])

    with lib_tab_songs:
        try:
            from app.project_manager import list_song_projects, get_song_project_songs
            song_projects = list_song_projects()
        except Exception:
            song_projects = []

        if not song_projects:
            st.info("아직 생성된 곡이 없습니다. Song Lab에서 시작하세요.")
        else:
            for p in song_projects:
                with st.expander(f"📁 {p['name']} ({p.get('song_count', 0)}곡)"):
                    try:
                        songs = get_song_project_songs(p["name"])
                    except Exception:
                        songs = []
                    if not songs:
                        st.caption("이 프로젝트에는 아직 곡이 없습니다.")
                    for s in songs:
                        dur = s.get("duration")
                        dur_str = f"{int(dur // 60)}:{int(dur % 60):02d}" if dur else "—"
                        st.markdown(
                            "<div style='display:flex;justify-content:space-between;padding:0.3rem 0;"
                            "border-bottom:1px solid #34353f55'>"
                            f"<span style='color:#f4f4f6;font-size:0.85rem'>{s.get('title', '제목 없음')}</span>"
                            f"<span style='color:#6b6c78;font-size:0.78rem'>{dur_str}</span></div>",
                            unsafe_allow_html=True,
                        )

    with lib_tab_images:
        try:
            from services.thumbnail.session_store import list_sessions, load_candidates
            sessions = list_sessions(limit=30)
        except Exception:
            sessions = []

        if not sessions:
            st.info("아직 생성된 이미지가 없습니다. Thumbnail Studio에서 시작하세요.")
        else:
            for sess in sessions:
                sid = sess.get("session_id", "")
                title = sess.get("title") or sess.get("theme") or sid
                try:
                    cands = load_candidates(sid)
                except Exception:
                    cands = []
                generated = [c for c in cands if c.get("uploaded_image_path")]
                with st.expander(f"🖼️ {title} ({len(generated)}/{len(cands)}장 생성됨) · {sid}"):
                    if not generated:
                        st.caption("생성된 이미지가 없습니다.")
                        continue
                    ncol = min(4, len(generated))
                    cols = st.columns(ncol)
                    for idx, c in enumerate(generated):
                        fp = c.get("uploaded_image_path")
                        with cols[idx % ncol]:
                            if fp and Path(fp).exists():
                                st.image(fp, use_container_width=True,
                                        caption=c.get("candidate_id", ""))
