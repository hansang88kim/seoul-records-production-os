"""
Seoul Records Production OS — Main Streamlit App
Entry point: streamlit run app/main.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os as _os
import subprocess as _sp
import streamlit as st
from app.config import APP_NAME, APP_VERSION
from app.dashboard import render_dashboard

st.set_page_config(
    page_title=f"{APP_NAME} v{APP_VERSION}",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Global CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Noto+Sans+KR:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
    /* ── Base ──────────────────────────────────────────────────────────── */
    .stApp {
        background:
            radial-gradient(ellipse 80% 50% at 50% -20%, rgba(200, 185, 122, 0.06), transparent),
            radial-gradient(ellipse 60% 50% at 100% 100%, rgba(80, 110, 180, 0.05), transparent),
            #070b16;
        font-family: 'Inter', 'Noto Sans KR', -apple-system, sans-serif;
    }
    .block-container {
        padding: 4rem 2rem 4rem;
        max-width: 1280px;
    }

    /* ── Typography ───────────────────────────────────────────────────── */
    h1 {
        color: #e8dcc0;
        font-weight: 700;
        font-size: 1.6rem;
        letter-spacing: -0.5px;
        margin-bottom: 0.25rem;
    }
    h2 {
        color: #d4c48a;
        font-weight: 600;
        font-size: 1.25rem;
        letter-spacing: -0.3px;
    }
    h3 {
        color: #c0b070;
        font-weight: 600;
        font-size: 1.05rem;
    }
    h4 {
        color: #d4c48a;
        font-weight: 600;
        font-size: 1rem;
        letter-spacing: -0.2px;
        margin: 0.5rem 0;
    }
    h5 {
        color: #9a8d6a;
        font-weight: 500;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 0.5rem;
    }
    p, span, label, .stMarkdown {
        color: #b0bcd0;
        font-size: 0.88rem;
        line-height: 1.5;
    }
    .stCaption, small {
        color: #5a6a84 !important;
        font-size: 0.78rem;
    }

    /* ── Tabs ─────────────────────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: #0c1224;
        border-radius: 10px;
        padding: 3px;
        border: 1px solid #151f38;
    }
    .stTabs [data-baseweb="tab"] {
        color: #4a5a78;
        font-size: 0.82rem;
        font-weight: 500;
        padding: 0.5rem 1.2rem;
        border-radius: 8px;
        border: none;
    }
    .stTabs [aria-selected="true"] {
        color: #e8dcc0;
        background: rgba(200, 185, 122, 0.12);
        border: 1px solid rgba(200, 185, 122, 0.2);
    }

    /* ── Sidebar ──────────────────────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: #0a1020;
        border-right: 1px solid #131c32;
    }
    [data-testid="stSidebar"] h2 {
        font-size: 1.1rem;
        color: #e8dcc0;
    }
    [data-testid="stSidebar"] h5 {
        font-size: 0.72rem;
        color: #6a7a94;
    }

    /* ── Inputs ────────────────────────────────────────────────────────── */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div {
        background: #0e1628;
        border: 1px solid #1a2540;
        border-radius: 8px;
        color: #c8d0e0;
        font-size: 0.85rem;
        font-family: 'Inter', 'Noto Sans KR', sans-serif;
    }
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #c8b97a;
        box-shadow: 0 0 0 1px rgba(200, 185, 122, 0.3);
    }
    .stTextInput > label,
    .stTextArea > label,
    .stSelectbox > label {
        color: #8090a8;
        font-size: 0.8rem;
        font-weight: 500;
    }

    /* ── Buttons ───────────────────────────────────────────────────────── */
    .stButton > button {
        font-family: 'Inter', 'Noto Sans KR', sans-serif;
        font-size: 0.82rem;
        font-weight: 500;
        border-radius: 8px;
        padding: 0.45rem 1rem;
        transition: all 0.15s ease;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #c8b97a 0%, #9a8650 100%);
        color: #080d1a;
        font-weight: 600;
        border: none;
        box-shadow: 0 2px 8px rgba(200, 185, 122, 0.2);
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #ddd0a0 0%, #b8a060 100%);
        box-shadow: 0 4px 16px rgba(200, 185, 122, 0.3);
        transform: translateY(-1px);
    }
    .stButton > button[kind="secondary"] {
        background: #111b30;
        color: #8a98b4;
        border: 1px solid #1e2e4a;
    }
    .stButton > button[kind="secondary"]:hover {
        background: #162040;
        color: #b0bcd0;
        border-color: #2a3e60;
    }

    /* ── Expander ──────────────────────────────────────────────────────── */
    [data-testid="stExpander"] {
        background: #0c1224;
        border: 1px solid #151f38;
        border-radius: 10px;
    }
    [data-testid="stExpander"] summary {
        color: #8a98b4;
        font-size: 0.85rem;
    }

    /* ── Metrics ───────────────────────────────────────────────────────── */
    [data-testid="stMetricValue"] {
        color: #e8dcc0;
        font-size: 1.3rem;
        font-weight: 600;
    }
    [data-testid="stMetricLabel"] {
        color: #5a6a84;
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* ── Slider ────────────────────────────────────────────────────────── */
    .stSlider > div > div > div > div {
        background: #c8b97a;
    }
    .stSlider label {
        color: #8090a8;
        font-size: 0.8rem;
    }

    /* ── Radio ─────────────────────────────────────────────────────────── */
    .stRadio > label {
        color: #8090a8;
        font-size: 0.82rem;
    }
    .stRadio > div {
        gap: 0.3rem;
    }

    /* ── Progress ──────────────────────────────────────────────────────── */
    .stProgress > div > div {
        background: linear-gradient(90deg, #c8b97a, #a89050);
        border-radius: 4px;
    }

    /* ── Divider ───────────────────────────────────────────────────────── */
    hr {
        border-color: #131c32 !important;
        margin: 0.75rem 0;
    }

    /* ── Alert boxes ──────────────────────────────────────────────────── */
    .stAlert {
        border-radius: 8px;
        font-size: 0.83rem;
    }

    /* ── File uploader ────────────────────────────────────────────────── */
    [data-testid="stFileUploader"] {
        border: 1px dashed #1e2e4a;
        border-radius: 10px;
        padding: 1rem;
    }

    /* ── Button text no-wrap ───────────────────────────────────────────── */
    .stButton > button {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* ── Checkbox inline ──────────────────────────────────────────────── */
    .stCheckbox label {
        color: #6a7a94;
        font-size: 0.78rem;
    }

    /* ── Selectbox ─────────────────────────────────────────────────────── */
    .stSelectbox label {
        font-size: 0.78rem;
        color: #6a7a94;
    }

    /* ── Scrollbar ─────────────────────────────────────────────────────── */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #080d1a; }
    ::-webkit-scrollbar-thumb { background: #1e2e4a; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #2a3e60; }
</style>
""", unsafe_allow_html=True)

# ─── Credential helper ───────────────────────────────────────────────────────
def _credential_field(label, env_var, placeholder, verify_fn=None, persist_env=False):
    """
    Render a credential field that retains its value across reruns.
    Shows status + edit button. Only re-prompts when 편집 is clicked.
    """
    state_key = f"_editing_{env_var}"
    current = _os.getenv(env_var, "")

    is_editing = st.session_state.get(state_key, not bool(current))

    if current and not is_editing:
        # Connected — show status + edit button
        col_status, col_edit = st.columns([3, 1])
        with col_status:
            st.markdown(f"<div style='color:#5ec27a;font-size:0.78rem;padding-top:6px'>🟢 {label} 연결됨</div>", unsafe_allow_html=True)
        with col_edit:
            if st.button("편집", key=f"edit_{env_var}", use_container_width=True):
                st.session_state[state_key] = True
                st.rerun()
        return

    # Editing mode — show input + connect button
    st.markdown(f"<div style='color:#c08070;font-size:0.78rem'>🔴 {label}</div>", unsafe_allow_html=True)
    new_val = st.text_input(
        label, type="password", placeholder=placeholder,
        key=f"input_{env_var}", label_visibility="collapsed",
    )
    col_connect, col_cancel = st.columns([2, 1]) if current else st.columns([1, 0.001])
    with col_connect:
        if st.button(f"🔗 연결", key=f"connect_{env_var}", use_container_width=True):
            if new_val.strip():
                _os.environ[env_var] = new_val.strip()
                if persist_env:
                    _persist_env(env_var, new_val.strip())
                ok, msg = (True, "연결됨") if not verify_fn else verify_fn(new_val.strip())
                if ok:
                    st.session_state[state_key] = False
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
            else:
                st.warning("값을 입력하세요")
    if current:
        with col_cancel:
            if st.button("취소", key=f"cancel_{env_var}", use_container_width=True):
                st.session_state[state_key] = False
                st.rerun()


def _persist_env(key, value):
    """Write key=value to .env (update or append)."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
        updated = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                updated = True
                break
        if not updated:
            lines.append(f"{key}={value}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        env_path.write_text(f"{key}={value}\n", encoding="utf-8")


def _verify_suno(cookie):
    try:
        from providers.suno.suno_cli_provider import SunoCliProvider
        ready = SunoCliProvider().verify_ready()
        return ready["ok"], ready["message"]
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        # Surface the actual error location and message
        return False, f"{type(e).__name__}: {e} (위치: {tb.strip().splitlines()[-2].strip() if len(tb.splitlines()) > 1 else '?'})"


def _verify_openai(key):
    try:
        import requests
        r = requests.get("https://api.openai.com/v1/models",
                         headers={"Authorization": f"Bearer {key}"}, timeout=10)
        if r.status_code == 200:
            return True, "ChatGPT 인증 성공"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, f"{type(e).__name__}"


def _verify_gemini(key):
    try:
        from providers.ai.base import GeminiProvider
        models = GeminiProvider.list_models(key)
        if models:
            flash = [m for m in models if "flash" in m and "lite" not in m]
            preferred = flash[0] if flash else models[0]
            # Store full list for debug display
            st.session_state["_gemini_models"] = models
            return True, f"[v2] 연결됨 → 사용 모델: {preferred} (총 {len(models)}개 가능)"
        import requests
        r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}", timeout=12)
        if r.status_code == 200:
            return True, "[v2] 인증됐으나 generateContent 지원 모델 없음"
        if r.status_code == 400:
            return False, "키 형식 오류"
        if r.status_code == 403:
            return False, "키 비활성화/권한 없음 — Google AI Studio 확인"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center;padding:0.5rem 0 0.2rem">
        <div style="font-size:1.3rem;font-weight:700;color:#e8dcc0;letter-spacing:-0.5px">🎵 Seoul Records</div>
        <div style="font-size:0.65rem;color:#4a5a78;letter-spacing:2px;text-transform:uppercase;margin-top:2px">Production OS v{APP_VERSION}</div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    st.markdown("<div style='color:#6a7a94;font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;margin:0.3rem 0'>🔑 Suno</div>", unsafe_allow_html=True)
    _credential_field("Suno 쿠키", "SUNO_COOKIE", "suno.com 쿠키", verify_fn=_verify_suno, persist_env=True)

    st.markdown("<div style='color:#6a7a94;font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;margin:0.8rem 0 0.3rem'>🤖 AI Composer</div>", unsafe_allow_html=True)
    _credential_field("ChatGPT", "OPENAI_API_KEY", "sk-...", verify_fn=_verify_openai, persist_env=True)
    st.markdown("")
    _credential_field("Gemini", "GOOGLE_GEMINI_API_KEY", "AI...", verify_fn=_verify_gemini, persist_env=True)

    st.markdown("<div style='color:#6a7a94;font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;margin:0.8rem 0 0.3rem'>🎨 Image Gen</div>", unsafe_allow_html=True)
    _credential_field("Midjourney (Apiframe)", "APIFRAME_API_KEY", "Apiframe API 키",
                      persist_env=True)

    st.divider()

    # ── Job Status Panel ─────────────────────────────────────────────
    # Recover interrupted jobs on each render (detects dead workers)
    try:
        from services.generation_job_manager import mark_interrupted_jobs, start_next_queued_job
        mark_interrupted_jobs()
        # Safety net: if nothing is running but jobs are queued, start the next
        # (covers the case where a worker died before chaining the queue)
        start_next_queued_job()
    except Exception:
        pass

    try:
        from services.job_store import get_active_jobs, list_jobs
        active = get_active_jobs()
        recent = list_jobs(limit=5)

        if active:
            st.markdown("<div style='color:#6a7a94;font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;margin:0.3rem 0'>🔄 진행 중</div>", unsafe_allow_html=True)
            for j in active:
                if j.get("status") != "running":
                    continue
                pct = j.get("progress_percent", 0) or 0
                title = j.get("current_track_title", "")
                st.progress(pct / 100)
                st.caption(f"🎵 {title} · {j.get('completed_tracks',0)}/{j.get('total_tracks',0)}곡")

        # Queued jobs
        from services.generation_job_manager import get_queued_jobs
        queued = get_queued_jobs()
        if queued:
            st.markdown("<div style='color:#6a7a94;font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;margin:0.3rem 0'>📋 대기열</div>", unsafe_allow_html=True)
            for qi, j in enumerate(queued):
                st.caption(f"⏳ {qi+1}. {j.get('project','?')} · {j.get('total_tracks',0)}곡 대기 중")

        completed = [j for j in recent if j.get("status") in ("completed", "partially_failed")]
        if completed:
            st.markdown("<div style='color:#6a7a94;font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;margin:0.3rem 0'>📋 최근 작업</div>", unsafe_allow_html=True)
            for j in completed[:3]:
                status_icon = "✅" if j["status"] == "completed" else "⚠️"
                st.caption(f"{status_icon} {j.get('project','?')} · {j.get('completed_tracks',0)}/{j.get('total_tracks',0)}곡")
    except Exception:
        pass  # job store not available yet

render_dashboard()
