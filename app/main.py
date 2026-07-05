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
# Palette mirrors frontend/styles/globals.css (Studio Console design tokens):
# near-black slate background, soft cyan primary, magenta + amber accents.
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Noto+Sans+KR:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
    :root {
        --bg:        #16171d;
        --card:      #1e1f27;
        --card-2:    #22232c;
        --border:    #34353f99;
        --fg:        #f4f4f6;
        --muted:     #9a9ba6;
        --muted-2:   #6b6c78;
        --cyan:      #7fd4e8;
        --cyan-dim:  rgba(127, 212, 232, 0.14);
        --magenta:   #e8639f;
        --magenta-dim: rgba(232, 99, 159, 0.14);
        --amber:     #e8c37c;
        --amber-dim: rgba(232, 195, 124, 0.14);
        --success:   #74d9a0;
        --danger:    #e06a52;
    }

    /* -- Base -- */
    .stApp { background: var(--bg); font-family: 'Inter', 'Noto Sans KR', -apple-system, sans-serif; }
    .block-container { padding: 3rem 2rem 4rem; max-width: 1320px; }

    /* -- Typography -- */
    h1 { color: var(--fg); font-weight: 700; font-size: 1.7rem; letter-spacing: -0.5px; margin-bottom: 0.25rem; }
    h2 { color: var(--fg); font-weight: 600; font-size: 1.2rem; letter-spacing: -0.3px; }
    h3 { color: var(--fg); font-weight: 600; font-size: 1.02rem; }
    h4 { color: var(--fg); font-weight: 600; font-size: 0.95rem; letter-spacing: -0.2px; margin: 0.5rem 0; }
    h5 { color: var(--muted); font-weight: 600; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 0.5rem; }
    p, span, label, .stMarkdown { color: var(--muted); font-size: 0.88rem; line-height: 1.55; }
    .stCaption, small { color: var(--muted-2) !important; font-size: 0.78rem; }

    /* -- Cards (bordered containers used as dashboard/metric panels) -- */
    div[data-testid="column"] > div[data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 14px;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {
        border-radius: 14px;
    }

    /* -- Tabs (still used inside individual pages) -- */
    .stTabs [data-baseweb="tab-list"] { gap: 0; background: var(--card-2); border-radius: 10px; padding: 3px; border: 1px solid var(--border); }
    .stTabs [data-baseweb="tab"] { color: var(--muted-2); font-size: 0.82rem; font-weight: 500; padding: 0.5rem 1.2rem; border-radius: 8px; border: none; }
    .stTabs [aria-selected="true"] { color: var(--fg); background: var(--cyan-dim); border: 1px solid rgba(127, 212, 232, 0.25); }

    /* -- Sidebar -- */
    [data-testid="stSidebar"] { background: #1a1b21; border-right: 1px solid var(--border); }
    [data-testid="stSidebar"] h2 { font-size: 1.1rem; color: var(--fg); }
    [data-testid="stSidebar"] h5 { font-size: 0.72rem; color: var(--muted); }
    [data-testid="stSidebar"] .stButton > button { text-align: left; justify-content: flex-start; width: 100%; }
    [data-testid="stSidebar"] .stButton > button[kind="secondary"] { background: transparent; color: var(--muted); border: 1px solid transparent; font-weight: 500; }
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover { background: var(--card-2); color: var(--fg); border-color: var(--border); }
    [data-testid="stSidebar"] .stButton > button[kind="primary"] { background: var(--cyan-dim); color: var(--cyan); border: 1px solid rgba(127, 212, 232, 0.3); font-weight: 600; box-shadow: none; }
    [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover { background: var(--cyan-dim); transform: none; box-shadow: none; }

    /* -- Inputs -- */
    .stTextInput > div > div > input, .stTextArea > div > div > textarea, .stSelectbox > div > div {
        background: var(--card-2); border: 1px solid var(--border); border-radius: 8px; color: var(--fg);
        font-size: 0.85rem; font-family: 'Inter', 'Noto Sans KR', sans-serif;
    }
    .stTextInput > div > div > input:focus, .stTextArea > div > div > textarea:focus {
        border-color: var(--cyan); box-shadow: 0 0 0 1px rgba(127, 212, 232, 0.35);
    }
    .stTextInput > label, .stTextArea > label, .stSelectbox > label { color: var(--muted); font-size: 0.8rem; font-weight: 500; }

    /* -- Buttons (main content area) -- */
    .stButton > button {
        font-family: 'Inter', 'Noto Sans KR', sans-serif; font-size: 0.82rem; font-weight: 500;
        border-radius: 8px; padding: 0.45rem 1rem; transition: all 0.15s ease;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .stButton > button[kind="primary"] {
        background: var(--cyan); color: #0e2a30; font-weight: 600; border: none;
        box-shadow: 0 2px 8px rgba(127, 212, 232, 0.18);
    }
    .stButton > button[kind="primary"]:hover {
        background: #9adfef; box-shadow: 0 4px 16px rgba(127, 212, 232, 0.28); transform: translateY(-1px);
    }
    .stButton > button[kind="secondary"] { background: var(--card-2); color: var(--muted); border: 1px solid var(--border); }
    .stButton > button[kind="secondary"]:hover { background: #2a2b34; color: var(--fg); border-color: #454652; }

    /* -- Expander -- */
    [data-testid="stExpander"] { background: var(--card-2); border: 1px solid var(--border); border-radius: 10px; }
    [data-testid="stExpander"] summary { color: var(--muted); font-size: 0.85rem; }

    /* -- Metrics -- */
    [data-testid="stMetricValue"] { color: var(--fg); font-size: 1.5rem; font-weight: 700; }
    [data-testid="stMetricLabel"] { color: var(--muted-2); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.5px; }

    /* -- Slider -- */
    .stSlider > div > div > div > div { background: var(--cyan); }
    .stSlider label { color: var(--muted); font-size: 0.8rem; }

    /* -- Radio -- */
    .stRadio > label { color: var(--muted); font-size: 0.82rem; }
    .stRadio > div { gap: 0.3rem; }

    /* -- Progress -- */
    .stProgress > div > div { background: linear-gradient(90deg, var(--cyan), #4fb8d0); border-radius: 4px; }
    .stProgress > div { background: var(--card-2); }

    /* -- Divider -- */
    hr { border-color: var(--border) !important; margin: 0.75rem 0; }

    /* -- Alert boxes -- */
    .stAlert { border-radius: 8px; font-size: 0.83rem; }

    /* -- File uploader -- */
    [data-testid="stFileUploader"] { border: 1px dashed var(--border); border-radius: 10px; padding: 1rem; }

    /* -- Checkbox inline -- */
    .stCheckbox label { color: var(--muted-2); font-size: 0.78rem; }

    /* -- Selectbox -- */
    .stSelectbox label { font-size: 0.78rem; color: var(--muted-2); }

    /* -- Badges / status pills (used via st.markdown snippets) -- */
    .srx-pill { display: inline-block; padding: 0.15rem 0.6rem; border-radius: 999px; font-size: 0.72rem; font-weight: 600; }
    .srx-pill-cyan    { background: var(--cyan-dim);    color: var(--cyan); }
    .srx-pill-magenta { background: var(--magenta-dim); color: var(--magenta); }
    .srx-pill-amber   { background: var(--amber-dim);   color: var(--amber); }

    /* -- Scrollbar -- */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: var(--bg); }
    ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #454652; }
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


def _verify_apiframe(key):
    try:
        from services.thumbnail.midjourney_provider import verify_apiframe_key
        return verify_apiframe_key(key)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


# ─── Settings page (credentials + job status; moved out of the sidebar) ─────
def render_settings_page():
    st.markdown("# ⚙️ Settings")
    st.caption("API 키/쿠키 연결 관리. 값은 로컬 .env에만 저장되며 화면·로그에 노출되지 않습니다.")
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### 🔑 Suno")
        _credential_field("Suno 쿠키", "SUNO_COOKIE", "suno.com 쿠키", verify_fn=_verify_suno, persist_env=True)

        st.write("")
        st.markdown("##### 🤖 AI Composer")
        _credential_field("ChatGPT", "OPENAI_API_KEY", "sk-...", verify_fn=_verify_openai, persist_env=True)
        st.write("")
        _credential_field("Gemini", "GOOGLE_GEMINI_API_KEY", "AI...", verify_fn=_verify_gemini, persist_env=True)

    with col2:
        st.markdown("##### 🎨 Image Gen")
        _credential_field("Midjourney (Apiframe)", "APIFRAME_API_KEY", "afk_...", verify_fn=_verify_apiframe, persist_env=True)

    st.divider()

    # ── Job Status Panel ──────────────────────────────────────────────────
    try:
        from services.generation_job_manager import mark_interrupted_jobs, start_next_queued_job
        mark_interrupted_jobs()
        start_next_queued_job()
    except Exception:
        pass

    st.markdown("##### 🔄 작업 상태")
    try:
        from services.job_store import get_active_jobs, list_jobs
        from services.generation_job_manager import get_queued_jobs
        active = get_active_jobs()
        recent = list_jobs(limit=5)
        queued = get_queued_jobs()

        running = [j for j in active if j.get("status") == "running"]
        if running:
            st.markdown("<div style='color:#9a9ba6;font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;margin:0.3rem 0'>진행 중</div>", unsafe_allow_html=True)
            for j in running:
                pct = j.get("progress_percent", 0) or 0
                title = j.get("current_track_title", "")
                st.progress(pct / 100)
                st.caption(f"🎵 {title} · {j.get('completed_tracks',0)}/{j.get('total_tracks',0)}곡")

        if queued:
            st.markdown("<div style='color:#9a9ba6;font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;margin:0.3rem 0'>대기열</div>", unsafe_allow_html=True)
            for qi, j in enumerate(queued):
                st.caption(f"⏳ {qi+1}. {j.get('project','?')} · {j.get('total_tracks',0)}곡 대기 중")

        completed = [j for j in recent if j.get("status") in ("completed", "partially_failed")]
        if completed:
            st.markdown("<div style='color:#9a9ba6;font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;margin:0.3rem 0'>최근 작업</div>", unsafe_allow_html=True)
            for j in completed[:3]:
                status_icon = "✅" if j["status"] == "completed" else "⚠️"
                st.caption(f"{status_icon} {j.get('project','?')} · {j.get('completed_tracks',0)}/{j.get('total_tracks',0)}곡")

        if not running and not queued and not completed:
            st.caption("표시할 작업 이력이 없습니다.")
    except Exception:
        st.caption("job store를 불러올 수 없습니다.")


# ─── Sidebar: brand header + vertical nav ────────────────────────────────────
NAV_ITEMS = [
    ("dashboard", "🏠", "Dashboard"),
    ("song_lab", "🎵", "Song Lab"),
    ("thumbnail", "🖼️", "Thumbnail Studio"),
    ("video", "🎬", "Video Renderer"),
    ("youtube", "▶️", "YouTube Package"),
    ("qa", "✅", "Production QA"),
    ("um", "🎶", "UnitedMasters"),
    ("history", "📜", "History"),
    ("library", "📚", "Library"),
    ("project", "📁", "프로젝트 관리"),
    ("settings", "⚙️", "Settings"),
]

if "nav_page" not in st.session_state:
    st.session_state.nav_page = "dashboard"

with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center;padding:0.5rem 0 1rem">
        <div style="font-size:1.3rem;font-weight:700;color:#f4f4f6;letter-spacing:-0.5px">🎵 Seoul Records</div>
        <div style="font-size:0.65rem;color:#6b6c78;letter-spacing:2px;text-transform:uppercase;margin-top:2px">Production OS v{APP_VERSION}</div>
    </div>
    """, unsafe_allow_html=True)

    for key, icon, label in NAV_ITEMS:
        active = st.session_state.nav_page == key
        if st.button(f"{icon}  {label}", key=f"nav_{key}", use_container_width=True,
                     type="primary" if active else "secondary"):
            st.session_state.nav_page = key
            st.rerun()

# ─── Route ────────────────────────────────────────────────────────────────────
_page = st.session_state.nav_page
if _page == "settings":
    render_settings_page()
else:
    render_dashboard(_page)
