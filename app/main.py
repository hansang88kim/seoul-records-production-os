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
<style>
    /* Base */
    .stApp { background-color: #0b1120; }
    .block-container { padding-top: 1.5rem; max-width: 1200px; }

    /* Typography */
    h1 { color: #d4c48a; font-weight: 700; letter-spacing: -0.5px; }
    h2 { color: #c8b97a; font-weight: 600; }
    h3 { color: #b0a06a; font-weight: 600; font-size: 1.1rem; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 0.5rem; }
    .stTabs [data-baseweb="tab"] {
        color: #6b7fa0;
        font-size: 0.9rem;
        padding: 0.6rem 1rem;
        border-radius: 8px 8px 0 0;
    }
    .stTabs [aria-selected="true"] {
        color: #d4c48a;
        background: rgba(212, 196, 138, 0.08);
        border-bottom: 2px solid #d4c48a;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: #0d1529;
        border-right: 1px solid #1a2744;
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 { font-size: 0.95rem; }

    /* Cards */
    [data-testid="stExpander"] {
        background: #111b30;
        border: 1px solid #1a2744;
        border-radius: 10px;
    }

    /* Buttons */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #c8b97a, #a89050);
        color: #0b1120;
        font-weight: 600;
        border: none;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #d4c48a, #b8a060);
    }

    /* Metrics */
    [data-testid="stMetricValue"] { color: #e0d9c0; font-size: 1.4rem; }
    [data-testid="stMetricLabel"] { color: #6b7fa0; }

    /* Progress */
    .stProgress > div > div { background: #c8b97a; }

    /* Divider */
    hr { border-color: #1a2744 !important; }
</style>
""", unsafe_allow_html=True)

# ─── Sidebar: Suno 인증 ─────────────────────────────────────────────────────
suno_bin = _os.getenv("SUNO_CLI_BIN", "suno")

with st.sidebar:
    # Logo area
    st.markdown("## 🎵 Seoul Records")
    st.caption(f"Production OS v{APP_VERSION}")
    st.divider()

    # Suno Auth
    st.markdown("##### 🔑 Suno 인증")

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

    col_auth, col_credits = st.columns(2)
    with col_auth:
        if st.button("🔐 인증", key="sidebar_auth", use_container_width=True):
            if new_cookie.strip():
                _os.environ["SUNO_COOKIE"] = new_cookie.strip()
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
                try:
                    proc = _sp.run([suno_bin, "auth", "--cookie", new_cookie.strip()], timeout=30)
                    if proc.returncode == 0:
                        st.success("✅ 완료")
                    else:
                        st.error("❌ 실패")
                except FileNotFoundError:
                    st.error(f"suno 없음")
            else:
                st.warning("쿠키 입력 필요")

    with col_credits:
        if st.button("💰 크레딧", key="sidebar_credits", use_container_width=True):
            try:
                proc = _sp.run(
                    [suno_bin, "credits", "--json"],
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=15,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    import json as _json
                    data = _json.loads(proc.stdout)
                    credits = data.get("data", data).get("credits_left", "?")
                    st.success(f"💰 {credits}")
                else:
                    st.error("확인 실패")
            except Exception:
                st.error("연결 실패")

    st.divider()

render_dashboard()
