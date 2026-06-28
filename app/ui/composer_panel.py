"""
app/ui/composer_panel.py — Song Lab Composer Panel (v0.5)
AI Composer + Song Form + Confirm/Generate flow.
"""
from __future__ import annotations
import os
import streamlit as st
from providers.ai.base import get_ai_provider, get_available_ai_providers, SongPromptPackage

DEFAULT_EXCLUDE = (
    "sax lead, strong sax, drum fill-ins, tom fills, snare rolls, "
    "trot, enka, EDM, bleepy sounds, toy percussion"
)

# Suno-style negative prompt: prepend "-" to each exclude term
def _format_exclude_as_negatives(exclude_str: str) -> str:
    """Convert 'sax lead, trot' → '-sax lead, -trot' for inline style use."""
    items = [s.strip() for s in exclude_str.split(",") if s.strip()]
    return ", ".join(f"-{item}" for item in items)
CITYPOP_STYLE_PRESET = (
    "Bright summer Korean city pop with J-pop nostalgic energy (early 80s Seoul), "
    "crisp upbeat groove (BPM 114), sparkling electric piano, shimmering analog synths, "
    "tight rhythmic funk guitar, punchy slap bass, clean bright drums, "
    "expressive low female vocals with retro reverb and subtle vibrato, "
    "refreshing yet wistful mood, bittersweet urban loneliness in a fast-changing city, "
    "nostalgic Seoul summer night feeling, neon-lit melancholy"
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
    """Render full composer: AI Composer + Song Form + Confirm + Generate."""

    # ═══════════════════════════════════════════════════════════════════════
    # AI COMPOSER
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("#### 🤖 AI Composer")

    # Provider selector
    providers = get_available_ai_providers()
    provider_labels = []
    for p in providers:
        label = p["label"]
        if not p["available"] and p["name"] != "mock":
            label += " (키 미설정)"
        provider_labels.append(label)

    col_provider, col_concept = st.columns([1, 3])
    with col_provider:
        selected_idx = st.selectbox(
            "AI", range(len(providers)),
            format_func=lambda i: provider_labels[i],
            key="ai_provider_idx",
            label_visibility="collapsed",
        )
        selected_provider = providers[selected_idx]

    with col_concept:
        concept = st.text_input(
            "컨셉 / 무드",
            placeholder="예: 비 오는 서울 밤, 이별 후 택시 안에서, 루프탑에서 보는 야경",
            key="ai_concept",
            label_visibility="collapsed",
        )

    # Availability warning
    if not selected_provider["available"] and selected_provider["name"] != "mock":
        key_name = "OPENAI_API_KEY" if selected_provider["name"] == "openai" else "GOOGLE_GEMINI_API_KEY"
        st.warning(f"⚠️ {selected_provider['label']} 사용 불가: `{key_name}` 미설정")
        # Inline key input
        api_key = st.text_input(f"{key_name}", type="password", key=f"inline_{key_name}")
        if api_key.strip():
            os.environ[key_name] = api_key.strip()
            st.rerun()

    # Generate buttons
    col_all, col_title, col_style, col_lyrics = st.columns(4)
    ai_ok = selected_provider["available"] and bool(concept.strip())
    provider = get_ai_provider(selected_provider["name"]) if ai_ok else None

    with col_all:
        if st.button("✨ 전체 생성", disabled=not ai_ok, use_container_width=True, key="ai_gen_all"):
            if provider:
                with st.spinner("AI 작곡 중..."):
                    try:
                        pkg = provider.generate_song_package(concept.strip())
                        st.session_state["form_title"] = pkg.title
                        st.session_state["form_lyrics"] = pkg.lyrics
                        st.session_state["form_style"] = pkg.style
                        st.session_state["prompt_confirmed"] = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"생성 실패: {e}")

    with col_title:
        if st.button("제목만", disabled=not ai_ok, use_container_width=True, key="ai_gen_title"):
            if provider and not st.session_state.get("lock_title"):
                with st.spinner("..."):
                    try:
                        st.session_state["form_title"] = provider.generate_title(concept.strip())
                        st.session_state["prompt_confirmed"] = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"실패: {e}")

    with col_style:
        if st.button("스타일만", disabled=not ai_ok, use_container_width=True, key="ai_gen_style"):
            if provider and not st.session_state.get("lock_style"):
                with st.spinner("..."):
                    try:
                        st.session_state["form_style"] = provider.generate_style(concept.strip())
                        st.session_state["prompt_confirmed"] = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"실패: {e}")

    with col_lyrics:
        if st.button("가사만", disabled=not ai_ok, use_container_width=True, key="ai_gen_lyrics"):
            if provider and not st.session_state.get("lock_lyrics"):
                with st.spinner("..."):
                    try:
                        st.session_state["form_lyrics"] = provider.generate_lyrics(concept.strip())
                        st.session_state["prompt_confirmed"] = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"실패: {e}")

    if not concept.strip():
        st.caption("💡 컨셉을 입력하면 AI가 곡을 작곡합니다")

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════
    # SONG FORM
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("#### 📝 Song Form")

    # Initialize style with preset on first load
    if "form_style" not in st.session_state:
        st.session_state["form_style"] = CITYPOP_STYLE_PRESET

    # Title
    col_t, col_tl = st.columns([6, 1])
    with col_t:
        title = st.text_input(
            "제목", placeholder="예: 밤이 지나면", key="form_title",
        )
    with col_tl:
        st.checkbox("🔒", key="lock_title", label_visibility="collapsed")

    # Lyrics
    col_l, col_ll = st.columns([6, 1])
    with col_l:
        lyrics = st.text_area(
            "가사", height=200, placeholder=LYRICS_PLACEHOLDER, key="form_lyrics",
        )
    with col_ll:
        st.checkbox("🔒", key="lock_lyrics", label_visibility="collapsed")

    # Lyric length + estimated duration indicator
    if lyrics.strip():
        lyric_chars = sum(
            len(l.strip().replace("(", "").replace(")", ""))
            for l in lyrics.split("\n")
            if l.strip() and not l.strip().startswith("[")
        )
        # Reference: ~340 chars ≈ 3:30 at citypop tempo (calibrated)
        est_sec = int(lyric_chars / 115 * 60) + 15  # +15 for intro/outro
        est_min, est_s = divmod(est_sec, 60)
        if lyric_chars > 360:
            st.warning(f"⚠️ 가사 {lyric_chars}자 · 예상 ~{est_min}:{est_s:02d} (너무 김 — 340자 이하로)")
        elif lyric_chars < 240:
            st.caption(f"가사 {lyric_chars}자 · 예상 ~{est_min}:{est_s:02d} (조금 짧음)")
        else:
            st.caption(f"✅ 가사 {lyric_chars}자 · 예상 ~{est_min}:{est_s:02d} (3:30 적정)")

    # Style
    col_s, col_sl = st.columns([6, 1])
    with col_s:
        style = st.text_area(
            "스타일 태그", height=60, key="form_style",
        )
    with col_sl:
        st.checkbox("🔒", key="lock_style", label_visibility="collapsed")

    style_len = len(style)
    if style_len > 1000:
        st.error(f"⚠️ 스타일 {style_len}자 — Suno 제한 1000자 초과")
    else:
        st.caption(f"{style_len}/1000 · 제외 스타일은 생성 시 자동으로 -prefix 추가됨")

    # Exclude
    exclude = st.text_input("제외 스타일", value=DEFAULT_EXCLUDE, key="form_exclude")

    # Controls
    col_m, col_v = st.columns(2)
    with col_m:
        model = st.selectbox("모델", SUNO_MODELS, index=0, key="form_model")
    with col_v:
        vocal = st.selectbox("보컬", ["Female", "Male", "Instrumental"], index=0, key="form_vocal")

    col_w, col_i = st.columns(2)
    with col_w:
        weirdness = st.slider("Weirdness", 0, 100, 35, key="form_weirdness")
    with col_i:
        style_influence = st.slider("Style Influence", 0, 100, 70, key="form_influence")

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════
    # CONFIRM + GENERATE
    # ═══════════════════════════════════════════════════════════════════════
    has_content = bool(title.strip()) and bool(lyrics.strip()) and bool(style.strip())
    is_confirmed = st.session_state.get("prompt_confirmed", False)

    col_confirm, col_generate = st.columns(2)

    with col_confirm:
        if st.button(
            "✅ Confirm Prompt" if not is_confirmed else "✅ Confirmed",
            disabled=not has_content or is_confirmed,
            use_container_width=True,
            key="btn_confirm",
        ):
            st.session_state["prompt_confirmed"] = True
            st.rerun()

    with col_generate:
        if st.button(
            "🚀 Send to Suno",
            type="primary",
            disabled=not is_confirmed,
            use_container_width=True,
            key="btn_generate",
        ):
            # Combine style + negative excludes into one tags string (Suno format)
            negatives = _format_exclude_as_negatives(exclude)
            combined_style = style.strip()
            if negatives:
                combined_style = f"{combined_style}, {negatives}"

            return {
                "title": title.strip(),
                "lyrics": lyrics.strip(),
                "style": combined_style,
                "exclude_styles": [],  # already merged into style
                "model": model,
                "vocal_gender": vocal if vocal != "Instrumental" else "Auto",
                "instrumental": vocal == "Instrumental",
                "weirdness": weirdness,
                "style_influence": style_influence,
            }

    if not has_content:
        st.caption("💡 제목, 가사, 스타일을 입력하세요")
    elif not is_confirmed:
        st.caption("💡 내용을 확인한 후 Confirm을 눌러주세요")
    else:
        st.caption("✅ 준비 완료 — Send to Suno를 눌러 생성하세요")

    return None
