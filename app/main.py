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

render_dashboard()
