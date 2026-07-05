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

# ─── Global CSS — "심야 스튜디오" design system (v1.0.0-alpha.44) ────────────
# Deep indigo Seoul-night surface, glass rack-panel cards, and ONE signature:
# the neon tape-stripe — a rose→aqua→gold hairline across the top of the app,
# under the sidebar wordmark, and as the active-nav left rail. Everything else
# stays quiet. Native widget tints (radio/checkbox/slider/toggle) come from
# .streamlit/config.toml. Legacy var names (--cyan/--magenta/--amber/--fg …)
# are kept as aliases so existing inline snippets keep working.
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Noto+Sans+KR:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
    :root {
        /* Surfaces */
        --bg:        #0b0d14;
        --bg-2:      #10131d;
        --panel:     #12151f;
        --well:      #141a28;
        --card:      rgba(148, 163, 255, 0.045);
        --card-2:    #151a26;
        --border:    rgba(148, 163, 255, 0.13);
        --border-2:  rgba(148, 163, 255, 0.22);

        /* Ink */
        --ink:       #eef1f8;
        --fg:        #eef1f8;
        --muted:     #9aa3b8;
        --muted-2:   #5d647a;

        /* Neon duo + highlight (city-pop signage) */
        --aqua:      #67e0f0;
        --aqua-dim:  rgba(103, 224, 240, 0.12);
        --rose:      #ff6ea0;
        --rose-dim:  rgba(255, 110, 160, 0.12);
        --gold:      #eecf8a;
        --gold-dim:  rgba(238, 207, 138, 0.12);
        --success:   #5fd39a;
        --danger:    #f07860;

        /* Legacy aliases (pre-alpha.44 inline snippets) */
        --cyan:        var(--aqua);
        --cyan-dim:    var(--aqua-dim);
        --magenta:     var(--rose);
        --magenta-dim: var(--rose-dim);
        --amber:       var(--gold);
        --amber-dim:   var(--gold-dim);

        --tape: linear-gradient(90deg, var(--rose), var(--aqua) 55%, var(--gold));
        --font-display: 'Space Grotesk', 'Noto Sans KR', system-ui, sans-serif;
        --font-body:    'Noto Sans KR', 'Space Grotesk', system-ui, sans-serif;
        --font-mono:    'JetBrains Mono', ui-monospace, 'Cascadia Mono', monospace;
        --radius: 14px;
        --shadow: 0 10px 30px rgba(3, 5, 12, 0.45);
    }

    /* ── Base canvas: indigo night with faint neon wash ── */
    .stApp {
        font-family: var(--font-body);
        background:
            radial-gradient(900px 420px at 12% -8%, rgba(255,110,160,0.055), transparent 60%),
            radial-gradient(1000px 480px at 92% -10%, rgba(103,224,240,0.05), transparent 60%),
            var(--bg);
        background-attachment: fixed;
    }
    /* Signature — neon tape-stripe across the very top */
    .stApp::before {
        content: ""; position: fixed; top: 0; left: 0; right: 0; height: 2px;
        background: var(--tape); z-index: 999; opacity: 0.9; pointer-events: none;
    }
    [data-testid="stHeader"] { background: transparent; }
    .block-container { padding: 2.4rem 2.2rem 4.5rem; max-width: 1280px; }

    @media (prefers-reduced-motion: no-preference) {
        .block-container { animation: srx-fade 0.35s ease-out; }
        @keyframes srx-fade { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
    }

    /* ── Typography ── */
    h1, h2, h3, h4 { font-family: var(--font-display); color: var(--ink); }
    h1 { font-weight: 700; font-size: 1.65rem; letter-spacing: -0.02em; margin-bottom: 0.2rem; }
    h1::after {
        content: ""; display: block; width: 34px; height: 2px; margin-top: 0.55rem;
        background: var(--tape); border-radius: 2px;
    }
    h2 { font-weight: 600; font-size: 1.18rem; letter-spacing: -0.015em; }
    h3 { font-weight: 600; font-size: 1.0rem; }
    h4 { font-weight: 600; font-size: 0.93rem; letter-spacing: -0.01em; margin: 0.55rem 0 0.35rem; }
    h5 { color: var(--muted-2); font-weight: 600; font-size: 0.7rem;
         text-transform: uppercase; letter-spacing: 0.14em; margin-bottom: 0.5rem; }
    p, span, label, .stMarkdown { color: var(--muted); font-size: 0.88rem; line-height: 1.6; }
    .stCaption, small, [data-testid="stCaptionContainer"] { color: var(--muted-2) !important; font-size: 0.77rem; }
    a { color: var(--aqua); }
    code {
        font-family: var(--font-mono); font-size: 0.78em;
        background: var(--well); border: 1px solid var(--border);
        border-radius: 6px; padding: 0.08em 0.4em; color: var(--gold);
    }
    [data-testid="stCode"] pre, .stCode pre {
        background: var(--bg-2) !important; border: 1px solid var(--border);
        border-radius: 10px; font-family: var(--font-mono);
    }

    /* ── Glass rack-panel cards (bordered containers / metric panels) ── */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: linear-gradient(180deg, rgba(255,255,255,0.028), rgba(255,255,255,0.008)), var(--panel);
        border: 1px solid var(--border);
        border-top-color: rgba(200, 210, 255, 0.16);
        border-radius: var(--radius);
        box-shadow: var(--shadow);
    }

    /* ── In-page tabs → segmented control ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px; background: var(--bg-2); border-radius: 11px;
        padding: 3px; border: 1px solid var(--border); width: fit-content;
    }
    .stTabs [data-baseweb="tab"] {
        color: var(--muted-2); font-size: 0.82rem; font-weight: 500;
        padding: 0.45rem 1.1rem; border-radius: 8px; border: none; background: transparent;
    }
    .stTabs [data-baseweb="tab"]:hover { color: var(--ink); }
    .stTabs [aria-selected="true"] {
        color: var(--ink) !important; background: var(--well);
        box-shadow: inset 0 0 0 1px var(--border-2);
    }
    .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }

    /* ── Sidebar: rack rail + wordmark ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0c0f18 0%, #0a0c13 100%);
        border-right: 1px solid var(--border);
    }
    [data-testid="stSidebar"] .stButton > button {
        text-align: left; justify-content: flex-start; width: 100%;
        font-family: var(--font-body); font-size: 0.85rem;
        border-radius: 10px; padding: 0.5rem 0.85rem;
    }
    [data-testid="stSidebar"] .stButton > button[kind="secondary"] {
        background: transparent; color: var(--muted);
        border: 1px solid transparent; font-weight: 500; box-shadow: none;
    }
    [data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {
        background: rgba(148, 163, 255, 0.06); color: var(--ink);
        border-color: transparent; transform: none;
    }
    /* Active nav item — quiet plate + tape left-rail */
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background: linear-gradient(90deg, rgba(103,224,240,0.10), rgba(103,224,240,0.02));
        color: var(--ink); font-weight: 600;
        border: 1px solid var(--border); border-left: 2px solid var(--aqua);
        box-shadow: none;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
        background: linear-gradient(90deg, rgba(103,224,240,0.14), rgba(103,224,240,0.03));
        transform: none; box-shadow: none;
    }

    /* ── Inputs / wells ── */
    .stTextInput input, .stTextArea textarea, .stNumberInput input,
    .stSelectbox [data-baseweb="select"] > div,
    .stMultiSelect [data-baseweb="select"] > div {
        background: var(--well) !important; border: 1px solid var(--border) !important;
        border-radius: 10px !important; color: var(--ink) !important;
        font-size: 0.85rem; font-family: var(--font-body);
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: var(--aqua) !important;
        box-shadow: 0 0 0 1px rgba(103, 224, 240, 0.35) !important;
    }
    [data-testid="stWidgetLabel"] p { color: var(--muted); font-size: 0.79rem; font-weight: 500; }
    [data-testid="stNumberInput"] button {
        background: var(--card-2); border-color: var(--border); color: var(--muted);
    }
    /* Dropdown menus */
    div[data-baseweb="popover"] ul, div[data-baseweb="menu"] {
        background: var(--card-2) !important; border: 1px solid var(--border-2);
        border-radius: 10px; box-shadow: var(--shadow);
    }
    div[data-baseweb="popover"] li { color: var(--muted); font-size: 0.84rem; }
    div[data-baseweb="popover"] li:hover,
    div[data-baseweb="popover"] li[aria-selected="true"] {
        background: var(--aqua-dim) !important; color: var(--ink) !important;
    }

    /* ── Multiselect chips — neon-edge, not alarm-red ── */
    .stMultiSelect [data-baseweb="tag"] {
        background: var(--aqua-dim) !important;
        border: 1px solid rgba(103, 224, 240, 0.35) !important;
        border-radius: 999px !important; color: var(--aqua) !important;
    }
    .stMultiSelect [data-baseweb="tag"] span,
    .stMultiSelect [data-baseweb="tag"] svg { color: var(--aqua) !important; fill: var(--aqua); }

    /* ── Buttons ── */
    .stButton > button, [data-testid="stFileUploader"] button {
        font-family: var(--font-body); font-size: 0.82rem; font-weight: 500;
        border-radius: 10px; padding: 0.46rem 1.05rem; transition: all 0.16s ease;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #79e7f4 0%, #4cc4de 100%);
        color: #07222b; font-weight: 700; border: none;
        box-shadow: 0 3px 14px rgba(103, 224, 240, 0.22);
    }
    .stButton > button[kind="primary"]:hover {
        filter: brightness(1.06);
        box-shadow: 0 6px 20px rgba(103, 224, 240, 0.32);
        transform: translateY(-1px);
    }
    .stButton > button[kind="secondary"], [data-testid="stFileUploader"] button {
        background: rgba(148, 163, 255, 0.05); color: var(--muted);
        border: 1px solid var(--border);
    }
    .stButton > button[kind="secondary"]:hover {
        background: rgba(148, 163, 255, 0.09); color: var(--ink);
        border-color: var(--border-2);
    }
    .stButton > button:disabled { opacity: 0.45; filter: none; transform: none; }

    /* ── Expander ── */
    [data-testid="stExpander"] {
        background: var(--panel); border: 1px solid var(--border); border-radius: 12px;
    }
    [data-testid="stExpander"] summary {
        color: var(--muted); font-size: 0.85rem; border-radius: 12px;
    }
    [data-testid="stExpander"] summary:hover { color: var(--ink); background: rgba(148,163,255,0.04); }

    /* ── Metrics ── */
    [data-testid="stMetricValue"] {
        color: var(--ink); font-family: var(--font-display);
        font-size: 1.55rem; font-weight: 700; letter-spacing: -0.01em;
    }
    [data-testid="stMetricLabel"] {
        color: var(--muted-2); font-size: 0.7rem;
        text-transform: uppercase; letter-spacing: 0.1em;
    }

    /* ── Slider / radio / checkbox / toggle labels ── */
    .stSlider label, .stRadio > label, .stCheckbox label { color: var(--muted); font-size: 0.8rem; }
    .stRadio [role="radiogroup"] { gap: 0.35rem; }
    .stRadio [role="radiogroup"] label {
        padding: 0.18rem 0.55rem; border-radius: 8px; transition: background 0.15s ease;
    }
    .stRadio [role="radiogroup"] label:hover { background: rgba(148, 163, 255, 0.05); }
    .stCheckbox label { color: var(--muted-2); font-size: 0.79rem; }

    /* ── Progress: tape gradient ── */
    .stProgress > div > div { background: var(--tape); border-radius: 4px; }
    .stProgress > div { background: var(--well); border-radius: 4px; }

    /* ── Alerts: tinted glass ── */
    div[data-testid="stAlert"] {
        border-radius: 12px; font-size: 0.83rem;
        background: var(--panel); border: 1px solid var(--border);
    }
    div[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) {
        background: rgba(95, 211, 154, 0.07); border-color: rgba(95, 211, 154, 0.28);
    }
    div[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) {
        background: rgba(103, 224, 240, 0.06); border-color: rgba(103, 224, 240, 0.25);
    }
    div[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) {
        background: rgba(238, 207, 138, 0.07); border-color: rgba(238, 207, 138, 0.28);
    }
    div[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) {
        background: rgba(240, 120, 96, 0.07); border-color: rgba(240, 120, 96, 0.3);
    }

    /* ── File uploader ── */
    [data-testid="stFileUploader"] section {
        background: var(--bg-2); border: 1px dashed var(--border-2);
        border-radius: 12px;
    }
    [data-testid="stFileUploader"] section:hover { border-color: rgba(103, 224, 240, 0.45); }

    /* ── Divider / misc ── */
    hr { border-color: var(--border) !important; margin: 0.8rem 0; }
    [data-testid="stJson"] { background: var(--bg-2); border-radius: 10px; }
    [data-testid="stTooltipIcon"] svg { color: var(--muted-2); }

    /* ── Status pills ── */
    .srx-pill {
        display: inline-block; padding: 0.16rem 0.62rem; border-radius: 999px;
        font-size: 0.71rem; font-weight: 600; letter-spacing: 0.02em;
        border: 1px solid transparent;
    }
    .srx-pill-cyan    { background: var(--aqua-dim); color: var(--aqua); border-color: rgba(103,224,240,0.3); }
    .srx-pill-magenta { background: var(--rose-dim); color: var(--rose); border-color: rgba(255,110,160,0.3); }
    .srx-pill-amber   { background: var(--gold-dim); color: var(--gold); border-color: rgba(238,207,138,0.3); }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(148, 163, 255, 0.16); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(148, 163, 255, 0.3); }
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
            st.markdown(f"<div style='color:var(--success);font-size:0.78rem;padding-top:6px'>● {label} 연결됨</div>", unsafe_allow_html=True)
        with col_edit:
            if st.button("편집", key=f"edit_{env_var}", use_container_width=True):
                st.session_state[state_key] = True
                st.rerun()
        return

    # Editing mode — show input + connect button
    st.markdown(f"<div style='color:var(--danger);font-size:0.78rem'>○ {label} 연결 필요</div>", unsafe_allow_html=True)
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
            st.markdown("<div style='color:var(--muted-2);font-size:0.68rem;font-weight:600;text-transform:uppercase;letter-spacing:0.14em;margin:0.3rem 0'>진행 중</div>", unsafe_allow_html=True)
            for j in running:
                pct = j.get("progress_percent", 0) or 0
                title = j.get("current_track_title", "")
                st.progress(pct / 100)
                st.caption(f"🎵 {title} · {j.get('completed_tracks',0)}/{j.get('total_tracks',0)}곡")

        if queued:
            st.markdown("<div style='color:var(--muted-2);font-size:0.68rem;font-weight:600;text-transform:uppercase;letter-spacing:0.14em;margin:0.3rem 0'>대기열</div>", unsafe_allow_html=True)
            for qi, j in enumerate(queued):
                st.caption(f"⏳ {qi+1}. {j.get('project','?')} · {j.get('total_tracks',0)}곡 대기 중")

        completed = [j for j in recent if j.get("status") in ("completed", "partially_failed")]
        if completed:
            st.markdown("<div style='color:var(--muted-2);font-size:0.68rem;font-weight:600;text-transform:uppercase;letter-spacing:0.14em;margin:0.3rem 0'>최근 작업</div>", unsafe_allow_html=True)
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
    <div style="padding:0.7rem 0.2rem 1.1rem">
        <div style="font-family:'Space Grotesk','Noto Sans KR',sans-serif;font-size:1.02rem;
                    font-weight:700;color:var(--ink);letter-spacing:0.16em;text-transform:uppercase">
            Seoul&nbsp;Records
        </div>
        <div style="height:2px;width:100%;margin:0.55rem 0 0.5rem;border-radius:2px;
                    background:linear-gradient(90deg,var(--rose),var(--aqua) 55%,var(--gold))"></div>
        <div style="display:flex;justify-content:space-between;align-items:baseline">
            <span style="font-size:0.62rem;color:var(--muted-2);letter-spacing:0.22em;
                         text-transform:uppercase">Production&nbsp;OS</span>
            <span style="font-family:'JetBrains Mono',monospace;font-size:0.62rem;
                         color:var(--muted-2)">v{APP_VERSION}</span>
        </div>
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
