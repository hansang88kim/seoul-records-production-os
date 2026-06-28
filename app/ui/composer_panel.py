"""
app/ui/composer_panel.py — Song Lab Composer Panel
All song generation inputs in one screen.
"""
from __future__ import annotations
import streamlit as st

# ─── Seoul Records Defaults ────────────────────────────────────────────────

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
    """
    Render the Song Lab composer panel.
    Returns dict of generation params when Generate is clicked, else None.
    """

    # ── Title ────────────────────────────────────────────────────────────
    title = st.text_input(
        "🎵 제목",
        placeholder="예: 밤이 지나면",
        key="composer_title",
    )

    # ── Lyrics ───────────────────────────────────────────────────────────
    st.markdown("##### 📝 가사")
    col_lyrics_btns = st.columns([1, 1, 1, 3])
    with col_lyrics_btns[0]:
        if st.button("📋 예시", key="lyrics_example", use_container_width=True):
            st.session_state["composer_lyrics"] = LYRICS_PLACEHOLDER
    with col_lyrics_btns[1]:
        if st.button("🗑️ 지우기", key="lyrics_clear", use_container_width=True):
            st.session_state["composer_lyrics"] = ""
    with col_lyrics_btns[2]:
        lock_lyrics = st.checkbox("🔒", key="lock_lyrics", help="가사 잠금")

    lyrics = st.text_area(
        "가사",
        value=st.session_state.get("composer_lyrics", ""),
        height=250,
        placeholder=LYRICS_PLACEHOLDER,
        key="composer_lyrics",
        disabled=lock_lyrics,
        label_visibility="collapsed",
    )

    # ── Style ────────────────────────────────────────────────────────────
    st.markdown("##### 🎨 스타일")
    col_style_btns = st.columns([1, 1, 3])
    with col_style_btns[0]:
        if st.button("🏙️ 시티팝", key="style_preset", use_container_width=True):
            st.session_state["composer_style"] = CITYPOP_STYLE_PRESET
    with col_style_btns[1]:
        lock_style = st.checkbox("🔒", key="lock_style", help="스타일 잠금")

    style = st.text_area(
        "스타일 태그 (200자 이내)",
        value=st.session_state.get("composer_style", CITYPOP_STYLE_PRESET),
        height=80,
        key="composer_style",
        disabled=lock_style,
        label_visibility="collapsed",
    )

    style_len = len(style)
    if style_len > 200:
        st.error(f"⚠️ 스타일 {style_len}자 — 200자 이내로 줄여야 합니다")
    else:
        st.caption(f"{style_len}/200자")

    # ── Exclude ──────────────────────────────────────────────────────────
    exclude = st.text_input(
        "🚫 제외 스타일",
        value=DEFAULT_EXCLUDE,
        key="composer_exclude",
    )

    # ── Controls Row 1: Model / Vocal ────────────────────────────────────
    col_model, col_vocal = st.columns(2)
    with col_model:
        model = st.selectbox("🤖 모델", SUNO_MODELS, index=0, key="composer_model")
    with col_vocal:
        vocal = st.selectbox("🎤 보컬", ["Female", "Male", "Instrumental"], index=0, key="composer_vocal")

    # ── Controls Row 2: Weirdness / Style Influence ──────────────────────
    col_weird, col_influence = st.columns(2)
    with col_weird:
        weirdness = st.slider("🌀 Weirdness", 0, 100, 35, key="composer_weirdness")
    with col_influence:
        style_influence = st.slider("🎯 Style Influence", 0, 100, 70, key="composer_influence")

    # ── Controls Row 3: Duration target / Variation ──────────────────────
    col_dur, col_var = st.columns(2)
    with col_dur:
        duration_target = st.selectbox(
            "⏱️ 목표 길이",
            ["3:00-3:30", "3:30-4:00", "4:00+"],
            index=1,
            key="composer_duration",
        )
    with col_var:
        variation = st.selectbox(
            "🎲 Variation",
            ["normal", "subtle", "high"],
            index=0,
            key="composer_variation",
        )

    # ── Generate Button ──────────────────────────────────────────────────
    st.markdown("")
    can_generate = bool(title.strip()) and bool(lyrics.strip()) and style_len <= 200

    if st.button(
        "🚀 Generate 1 Song",
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
            missing.append("스타일 200자 초과")
        if missing:
            st.caption(f"💡 필요: {', '.join(missing)}")

    return None
