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
        background: #080d1a;
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

# ─── Sidebar: Suno 인증 ─────────────────────────────────────────────────────
suno_bin = _os.getenv("SUNO_CLI_BIN", "suno")

with st.sidebar:
    # Logo area
    st.markdown(f"""
    <div style="text-align:center;padding:0.5rem 0 0.2rem">
        <div style="font-size:1.3rem;font-weight:700;color:#e8dcc0;letter-spacing:-0.5px">🎵 Seoul Records</div>
        <div style="font-size:0.65rem;color:#4a5a78;letter-spacing:2px;text-transform:uppercase;margin-top:2px">Production OS v{APP_VERSION}</div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    # Suno Auth
    st.markdown("<div style='color:#6a7a94;font-size:0.7rem;font-weight:500;text-transform:uppercase;letter-spacing:1.5px;margin:0.5rem 0 0.3rem'>🔑 Suno 인증</div>", unsafe_allow_html=True)

    current_cookie = _os.getenv("SUNO_COOKIE", "")
    if current_cookie:
        st.caption(f"🟢 쿠키 설정됨 ({len(current_cookie)}자)")
    else:
        st.caption("🔴 쿠키 미설정 — 아래에 입력하세요")

    new_cookie = st.text_input(
        "Cookie",
        type="password",
        placeholder="suno.com → F12 → Network → Cookie 복사",
        key="sidebar_suno_cookie",
        label_visibility="collapsed",
    )

    if st.button("🔐 인증 + 크레딧 확인", key="sidebar_auth", use_container_width=True):
        if new_cookie.strip():
            _os.environ["SUNO_COOKIE"] = new_cookie.strip()
            # Persist to .env
            env_path = Path(__file__).resolve().parent.parent / ".env"
            if env_path.exists():
                lines = env_path.read_text(encoding="utf-8").splitlines()
                updated = False
                for i, line in enumerate(lines):
                    if line.startswith("SUNO_COOKIE="):
                        lines[i] = f"SUNO_COOKIE={new_cookie.strip()}"
                        updated = True
                        break
                if not updated:
                    lines.append(f"SUNO_COOKIE={new_cookie.strip()}")
                env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            else:
                env_path.write_text(f"SUNO_COOKIE={new_cookie.strip()}\n", encoding="utf-8")

            # Full verify: auth + credits (same as manual CLI workflow)
            with st.spinner("인증 + 크레딧 확인 중..."):
                try:
                    from providers.suno.suno_cli_provider import SunoCliProvider
                    ready = SunoCliProvider().verify_ready()
                    if ready["ok"]:
                        st.success(f"✅ {ready['message']}")
                    else:
                        st.error(f"❌ {ready['message']}")
                except Exception as e:
                    st.error(f"❌ 오류: {type(e).__name__}")
        else:
            st.warning("쿠키를 입력하세요")

    # ── AI Composer API Keys ──────────────────────────────────────────────
    st.markdown("<div style='color:#6a7a94;font-size:0.7rem;font-weight:500;text-transform:uppercase;letter-spacing:1.5px;margin:0.5rem 0 0.3rem'>🤖 AI Composer</div>", unsafe_allow_html=True)

    # OpenAI
    current_openai = _os.getenv("OPENAI_API_KEY", "")
    st.caption("🟢 OpenAI (ChatGPT) 연결됨" if current_openai else "🔴 OpenAI (ChatGPT)")
    openai_key = st.text_input(
        "OpenAI", type="password", placeholder="sk-...",
        key="sidebar_openai_key", label_visibility="collapsed",
    )
    if st.button("🔗 OpenAI 연결", key="btn_openai_connect", use_container_width=True):
        if openai_key.strip():
            _os.environ["OPENAI_API_KEY"] = openai_key.strip()
            # Verify with a test call
            try:
                import requests as _req
                resp = _req.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {openai_key.strip()}"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    st.success("✅ OpenAI 인증 성공")
                else:
                    st.error(f"❌ 인증 실패 (HTTP {resp.status_code})")
            except Exception as e:
                st.error(f"❌ 연결 실패: {type(e).__name__}")
        else:
            st.warning("키를 입력하세요")

    # Gemini
    current_gemini = _os.getenv("GOOGLE_GEMINI_API_KEY", "")
    st.caption("🟢 Gemini 연결됨" if current_gemini else "🔴 Gemini")
    gemini_key = st.text_input(
        "Gemini", type="password", placeholder="AI...",
        key="sidebar_gemini_key", label_visibility="collapsed",
    )
    if st.button("🔗 Gemini 연결", key="btn_gemini_connect", use_container_width=True):
        if gemini_key.strip():
            _os.environ["GOOGLE_GEMINI_API_KEY"] = gemini_key.strip()
            try:
                import requests as _req
                # Try v1beta endpoint
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key.strip()}"
                resp = _req.get(url, timeout=15)
                if resp.status_code == 200:
                    st.success("✅ Gemini 인증 성공")
                elif resp.status_code == 400:
                    st.error("❌ API 키 형식이 올바르지 않습니다")
                elif resp.status_code == 403:
                    st.error("❌ API 키가 비활성화되었거나 권한이 없습니다. Google AI Studio에서 키를 확인하세요.")
                else:
                    try:
                        err = resp.json().get("error", {}).get("message", "")
                    except Exception:
                        err = resp.text[:200]
                    st.error(f"❌ HTTP {resp.status_code}: {err}")
            except _req.exceptions.ConnectionError:
                st.error("❌ 네트워크 연결 실패 — 인터넷 연결을 확인하세요")
            except _req.exceptions.Timeout:
                st.error("❌ 응답 시간 초과 — 다시 시도하세요")
            except Exception as e:
                st.error(f"❌ {type(e).__name__}: {e}")
        else:
            st.warning("키를 입력하세요")

    st.divider()

render_dashboard()
