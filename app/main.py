"""
Seoul Records Production OS — Main Streamlit App
Entry point: streamlit run app/main.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from app.config import APP_NAME, APP_VERSION
from app.dashboard import render_dashboard

st.set_page_config(
    page_title=f"{APP_NAME} v{APP_VERSION}",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Global CSS
st.markdown("""
<style>
    .stApp { background-color: #0a0f1e; }
    .block-container { padding-top: 1rem; }
    h1, h2, h3 { color: #c8b97a; }
    .stTabs [data-baseweb="tab"] { color: #a0b4d0; }
    .stTabs [aria-selected="true"] { color: #c8b97a; border-bottom-color: #c8b97a; }
    .metric-card {
        background: #111827;
        border: 1px solid #1e3050;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.25rem 0;
    }
    .status-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ─── Sidebar: Suno Cookie Auth ────────────────────────────────────────────────
import os as _os
import subprocess as _sp

with st.sidebar:
    st.markdown("### 🔑 Suno 인증")

    suno_bin = _os.getenv("SUNO_CLI_BIN", "suno")

    # Cookie input
    new_cookie = st.text_input(
        "Cookie 붙여넣기",
        type="password",
        placeholder="브라우저에서 복사한 Cookie 값",
        key="sidebar_suno_cookie",
    )

    col_auth, col_credits = st.columns(2)

    with col_auth:
        if st.button("🔐 인증", key="sidebar_auth", use_container_width=True):
            if new_cookie.strip():
                _os.environ["SUNO_COOKIE"] = new_cookie.strip()
                # Write to .env for persistence
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
                        st.success("✅ 인증 완료")
                    else:
                        st.error("❌ 인증 실패")
                except FileNotFoundError:
                    st.error(f"suno 없음: {suno_bin}")
            else:
                st.warning("쿠키를 입력하세요")

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
                    st.success(f"{credits} 크레딧")
                else:
                    st.error("확인 실패")
            except Exception:
                st.error("연결 실패")

    # Show current status
    current = _os.getenv("SUNO_COOKIE", "")
    if current:
        st.caption(f"🟢 쿠키 설정됨 ({len(current)}자)")
    else:
        st.caption("🔴 쿠키 미설정")

    st.divider()

render_dashboard()
