"""
app/ui/composer_panel.py — Song Lab Composer Panel
"""
from __future__ import annotations
import streamlit as st

DEFAULT_EXCLUDE = (
    "sax lead, strong sax, drum fill-ins, tom fills, snare rolls, "
    "trot, enka, EDM, bleepy sounds, toy percussion"
)

CITYPOP_STYLE_PRESET = (
    "Japanese citypop, CP-70 electric piano, DX7, chorus guitar, "
    "warm bass, soft synth, low thick female vocal, calm, intimate"
)

SUNO_MODELS = ["v5.5", "v5", "v4.5", "v4", "v3.5"]

LYRICS_PLACEHOLDER = """[Intro]
(4마디 음원 (instrumental only))

[Verse 1]
여기에 첫 번째 절 가사

[Pre-Chorus]
프리코러스 가사

[Chorus]
후렴 가사

[Verse 2]
두 번째 절 가사

[Bridge]
브릿지 가사

[Outro]
(4마디 음원 (instrumental only))"""


def render_composer_panel() -> dict | None:
    """Render composer panel. Returns params dict on Generate click, else None."""

    # ── Title ────────────────────────────────────────────────────────────
    title = st.text_input(
        "제목",
        placeholder="예: 밤이 지나면",
        key="composer_title",
        label_visibility="collapsed",
    )
    st.caption("🎵 제목")

    # ── Lyrics ───────────────────────────────────────────────────────────
    st.markdown("")
    col_lbl, col_btns = st.columns([1, 2])
    with col_lbl:
        st.caption("📝 가사")
    with col_btns:
        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            if st.button("예시 불러오기", key="lyrics_example"):
                st.session_state["composer_lyrics"] = LYRICS_PLACEHOLDER
        with c2:
            if st.button("전체 지우기", key="lyrics_clear"):
                st.session_state["composer_lyrics"] = ""
        with c3:
            lock_lyrics = st.checkbox("잠금", key="lock_lyrics")

    lyrics = st.text_area(
        "lyrics",
        value=st.session_state.get("composer_lyrics", ""),
        height=220,
        placeholder=LYRICS_PLACEHOLDER,
        key="composer_lyrics",
        disabled=lock_lyrics,
        label_visibility="collapsed",
    )

    # ── Style ────────────────────────────────────────────────────────────
    st.markdown("")
    col_slbl, col_sbtns = st.columns([1, 2])
    with col_slbl:
        st.caption("🎨 스타일 태그")
    with col_sbtns:
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("시티팝 프리셋", key="style_preset"):
                st.session_state["composer_style"] = CITYPOP_STYLE_PRESET
        with c2:
            lock_style = st.checkbox("잠금", key="lock_style")

    style = st.text_area(
        "style",
        value=st.session_state.get("composer_style", CITYPOP_STYLE_PRESET),
        height=70,
        key="composer_style",
        disabled=lock_style,
        label_visibility="collapsed",
    )
    style_len = len(style)
    if style_len > 200:
        st.error(f"⚠️ {style_len}자 — 200자 이하로 줄이세요")
    else:
        st.caption(f"{style_len}/200")

    # ── Exclude ──────────────────────────────────────────────────────────
    st.caption("🚫 제외할 스타일")
    exclude = st.text_input(
        "exclude",
        value=DEFAULT_EXCLUDE,
        key="composer_exclude",
        label_visibility="collapsed",
    )

    # ── Model + Vocal ────────────────────────────────────────────────────
    st.markdown("")
    col_m, col_v = st.columns(2)
    with col_m:
        model = st.selectbox("모델", SUNO_MODELS, index=0, key="composer_model")
    with col_v:
        vocal = st.selectbox("보컬", ["Female", "Male", "Instrumental"], index=0, key="composer_vocal")

    # ── Weirdness + Style Influence ──────────────────────────────────────
    col_w, col_i = st.columns(2)
    with col_w:
        weirdness = st.slider("Weirdness", 0, 100, 35, key="composer_weirdness")
    with col_i:
        style_influence = st.slider("Style Influence", 0, 100, 70, key="composer_influence")

    # ── Duration + Variation ─────────────────────────────────────────────
    col_d, col_var = st.columns(2)
    with col_d:
        duration_target = st.selectbox(
            "목표 길이", ["3:00-3:30", "3:30-4:00", "4:00+"],
            index=1, key="composer_duration",
        )
    with col_var:
        variation = st.selectbox(
            "Variation", ["normal", "subtle", "high"],
            index=0, key="composer_variation",
        )

    # ── Generate ─────────────────────────────────────────────────────────
    st.markdown("")
    can_generate = bool(title.strip()) and bool(lyrics.strip()) and style_len <= 200

    if st.button(
        "🚀 Generate",
        type="primary",
        use_container_width=True,
        disabled=not can_generate,
        key="btn_generate",
    ):
        return {
            "title": title.strip(),
            "lyrics": lyrics.strip(),
            "style": style.strip(),
            "exclude_styles": [s.strip() for s in exclude.split(",") if s.strip()],
            "model": model,
            "vocal_gender": vocal if vocal != "Instrumental" else "Auto",
            "instrumental": vocal == "Instrumental",
            "weirdness": weirdness,
            "style_influence": style_influence,
            "duration_target": duration_target,
            "variation": variation,
        }

    if not can_generate:
        missing = []
        if not title.strip():
            missing.append("제목")
        if not lyrics.strip():
            missing.append("가사")
        if style_len > 200:
            missing.append("스타일 초과")
        st.caption(f"💡 {', '.join(missing)}")

    return None
