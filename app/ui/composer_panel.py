"""
app/ui/composer_panel.py — Song Lab Composer Panel (v0.5)
AI Composer + Song Form + Confirm/Generate flow.
"""
from __future__ import annotations
import os
import streamlit as st
from providers.ai.base import get_ai_provider, get_available_ai_providers, SongPromptPackage

DEFAULT_EXCLUDE = (
    # Instruments / genre exclusions
    "sax lead, strong sax, drum fill-ins, excessive drum fills, busy drum fills, "
    "tom fills, snare rolls, drum rolls, cymbal crashes, "
    "trot, enka, EDM, rock, hard rock, bleepy sounds, toy percussion, "
    # Vocal exclusions — city pop is gentle and lyrical, NOT belted rock
    "high belting, belting, powerful belting, screaming vocals, shouting, "
    "loud high notes, soaring high notes, rock vocals, aggressive vocals, "
    "vocal runs, melisma, riffing"
)

# Suno-style negative prompt: prepend "-" to each exclude term
def _format_exclude_as_negatives(exclude_str: str) -> str:
    """Convert 'sax lead, trot' → '-sax lead, -trot' for inline style use."""
    items = [s.strip() for s in exclude_str.split(",") if s.strip()]
    return ", ".join(f"-{item}" for item in items)
CITYPOP_STYLE_PRESET = (
    "Authentic 1980s-1990s Japanese city pop, golden-age Tokyo sound, "
    "lush warm electric piano, glossy analog synths, smooth jazzy chord changes, "
    "silky funk guitar, melodic fretless bass, soft steady drums with minimal fills, "
    "C major, BPM 112, "
    "gentle restrained low female vocal, soft and lyrical, never belting, "
    "calm even dynamics throughout, warm reverb and tender vibrato, "
    "deeply nostalgic and bittersweet, mellow and laid-back, sophisticated and smooth, "
    "the wistful loneliness of city nights, vintage tape warmth, "
    "consistent soft dynamics, no loud climaxes, no high belting"
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
        cc1, cc2 = st.columns([5, 1])
        with cc1:
            concept = st.text_input(
                "컨셉 / 무드",
                placeholder="예: 비 오는 서울 밤, 이별 후 택시 안에서, 루프탑에서 보는 야경",
                key="ai_concept",
                label_visibility="collapsed",
            )
        with cc2:
            if st.button("🎲 변주", key="ai_concept_variation",
                         help="시티팝에 어울리는 컨셉 키워드를 하나씩 제안합니다.",
                         use_container_width=True):
                from services.concept_suggester import next_concept
                sug = next_concept(st.session_state,
                                   avoid=st.session_state.get("ai_concept", ""))
                st.session_state["ai_concept"] = sug
                st.rerun()

    # Language selector — picks the lyric language + city emotion
    from providers.ai.languages import language_choices
    lang_opts = language_choices()
    col_lang, col_langnote = st.columns([1, 3])
    with col_lang:
        lang_idx = st.selectbox(
            "언어", range(len(lang_opts)),
            format_func=lambda i: lang_opts[i][1],
            key="ai_language_idx",
            label_visibility="collapsed",
        )
    selected_language = lang_opts[lang_idx][0]
    with col_langnote:
        from providers.ai.languages import get_language
        _lg = get_language(selected_language)
        st.markdown(
            f"<div style='font-size:0.78rem;color:var(--muted);padding-top:6px'>"
            f"🌏 가사: {_lg['lyric_language']} · 도시 감성: {_lg['city']} "
            f"(스타일은 동일한 Japanese citypop)</div>",
            unsafe_allow_html=True,
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
                        pkg = provider.generate_song_package(concept.strip(), language=selected_language)
                        # Respect locks — don't overwrite locked fields
                        if not st.session_state.get("lock_title"):
                            st.session_state["form_title"] = pkg.title
                        if not st.session_state.get("lock_lyrics"):
                            st.session_state["form_lyrics"] = pkg.lyrics
                        if not st.session_state.get("lock_style"):
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
                        st.session_state["form_title"] = provider.generate_title(concept.strip(), language=selected_language)
                        st.session_state["prompt_confirmed"] = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"실패: {e}")

    with col_style:
        if st.button("스타일만", disabled=not ai_ok, use_container_width=True, key="ai_gen_style"):
            if provider and not st.session_state.get("lock_style"):
                with st.spinner("..."):
                    try:
                        st.session_state["form_style"] = provider.generate_style(concept.strip(), language=selected_language)
                        st.session_state["prompt_confirmed"] = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"실패: {e}")

    with col_lyrics:
        if st.button("가사만", disabled=not ai_ok, use_container_width=True, key="ai_gen_lyrics"):
            if provider and not st.session_state.get("lock_lyrics"):
                with st.spinner("..."):
                    try:
                        st.session_state["form_lyrics"] = provider.generate_lyrics(concept.strip(), language=selected_language)
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

    # Initialize style with preset on first load + lock it by default
    # so AI generation keeps the fixed Japanese citypop style.
    if "form_style" not in st.session_state:
        st.session_state["form_style"] = CITYPOP_STYLE_PRESET
    if "lock_style" not in st.session_state:
        st.session_state["lock_style"] = True  # default ON — keep preset fixed

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
    lyric_chars = sum(
        len(l.strip().replace("(", "").replace(")", ""))
        for l in lyrics.split("\n")
        if l.strip() and not l.strip().startswith("[")
    )
    # Reference: ~400 chars ≈ 3:30 at citypop tempo (calibrated to 명동 블루스)
    est_sec = int(lyric_chars / 118 * 60) + 15  # +15 for intro/outro instrumental
    est_min, est_s = divmod(est_sec, 60)
    if lyric_chars == 0:
        st.caption("0자 · 가사를 입력하세요 (목표: 320~400자)")
    elif lyric_chars > 400:
        st.warning(f"⚠️ 가사 본문 {lyric_chars}자 · 예상 ~{est_min}:{est_s:02d} (400자 이하로 줄이세요)")
    elif lyric_chars < 320:
        st.caption(f"가사 본문 {lyric_chars}자 · 예상 ~{est_min}:{est_s:02d} (320자 이상 권장)")
    else:
        st.caption(f"✅ 가사 본문 {lyric_chars}자 · 예상 ~{est_min}:{est_s:02d} (적정)")

    # Style
    col_slabel, col_spreset, col_sregen = st.columns([3, 1, 1])
    with col_slabel:
        st.markdown("<div style='font-size:0.85rem;color:var(--muted);padding-top:4px'>🎨 스타일 태그</div>", unsafe_allow_html=True)
    with col_spreset:
        if st.button("프리셋 적용", key="apply_preset", use_container_width=True,
                     help="고정 시티팝 스타일로 되돌리기"):
            st.session_state["form_style"] = CITYPOP_STYLE_PRESET
            st.rerun()
    with col_sregen:
        if st.button("🔀 변주", key="style_regen", use_container_width=True,
                     help="BPM/Key/보컬 톤만 살짝 변경 (장르 유지)"):
            current = st.session_state.get("form_style", CITYPOP_STYLE_PRESET)
            if current.strip():
                with st.spinner("스타일 변주 중..."):
                    from providers.ai.base import generate_style_variation
                    avail = [p for p in get_available_ai_providers() if p["available"] and p["name"] != "mock"]
                    pname = avail[0]["name"] if avail else "mock"
                    st.session_state["form_style"] = generate_style_variation(current, pname)
                    st.rerun()

    col_s, col_sl = st.columns([6, 1])
    with col_s:
        style = st.text_area(
            "스타일 태그", height=80, key="form_style",
            label_visibility="collapsed",
        )
    with col_sl:
        st.checkbox("🔒", key="lock_style", label_visibility="collapsed",
                    help="잠그면 AI 생성 시 스타일이 바뀌지 않습니다")

    style_len = len(style)
    is_locked = st.session_state.get("lock_style", True)
    lock_note = "🔒 고정됨 (AI 생성 시 유지)" if is_locked else "🔓 잠금 해제 (AI가 변경)"
    if style_len > 1000:
        st.error(f"⚠️ {style_len}/1000 — Suno 제한 초과 · {lock_note}")
    else:
        st.caption(f"{style_len}/1000 · {lock_note} · 제외 스타일 자동 -prefix")

    # Exclude (→ Suno's More Options → Exclude styles box)
    st.markdown("<div style='font-size:0.85rem;color:var(--muted);padding-top:4px'>🚫 제외 스타일 (Suno Exclude styles)</div>", unsafe_allow_html=True)
    exclude = st.text_input(
        "제외 스타일", value=DEFAULT_EXCLUDE, key="form_exclude",
        label_visibility="collapsed",
        help="여기 입력한 항목은 Suno의 'Exclude styles'로 전달됩니다 (스타일에 합쳐지지 않음). '-' 없이 입력하세요.",
    )
    st.caption("💡 '-' 기호 없이 입력하세요. Suno가 자동으로 제외 처리합니다.")

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
            # Send exclude styles SEPARATELY (→ Suno --exclude flag → Exclude styles box).
            # Do NOT merge into the style text — that makes Suno ADD those instruments.
            # Strip any leading "-" the user may have typed (the flag handles negation).
            _hyphens = "\u002d\u2010\u2011\u2012\u2013\u2014\u2212"
            exclude_list = [
                s.strip().lstrip(_hyphens).strip()
                for s in exclude.split(",")
                if s.strip().lstrip(_hyphens).strip()
            ]

            return {
                "title": title.strip(),
                "lyrics": lyrics.strip(),
                "style": style.strip(),  # clean style only, no negatives
                "exclude_styles": exclude_list,  # → --exclude flag
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
