"""
app/tabs/thumbnail_studio.py — Thumbnail Studio (v0.6.0).

Independent tab for citypop YouTube thumbnail creation:
  Prompt Lab → Candidate Gallery → Brand Thumbnail → Exports

Workflow: generate Flow prompts → user makes images in Google Flow →
upload candidates → select favorites → apply Canva brand template.
Does NOT touch music generation.
"""
from __future__ import annotations

from pathlib import Path
import streamlit as st

from services.thumbnail.country_presets import list_countries, get_country_preset, get_title_defaults
from services.thumbnail.prompt_generator import generate_prompt_batch, build_prompt_batch
from services.thumbnail.prompt_composer import compose_english_prompt
from services.thumbnail import session_store as ss
from services.thumbnail import canva_branding as cb
from services.thumbnail import image_gen_deps as igd
from app.project_manager import list_song_projects


def render_thumbnail_studio():
    """Main entry — the Thumbnail Studio tab."""
    st.markdown("<h2 style='margin-bottom:0.3rem'>🖼️ Thumbnail Studio</h2>", unsafe_allow_html=True)
    st.caption("Citypop YouTube 썸네일 제작 · Google Flow 프롬프트 → 이미지 업로드 → 선택 → Canva 브랜딩")

    # Mode selector
    mode = st.radio(
        "모드",
        ["🎨 Prompt Lab", "🖼️ Candidate Gallery", "✨ Brand Thumbnail",
         "🆕 프리미엄 (형태별)", "📦 Exports"],
        horizontal=True, label_visibility="collapsed",
    )

    st.divider()

    if mode.startswith("🎨"):
        _render_prompt_lab()
    elif mode.startswith("🖼️"):
        _render_candidate_gallery()
    elif mode.startswith("✨"):
        _render_brand_thumbnail()
    elif mode.startswith("🆕"):
        _render_form_studio()
    else:
        _render_exports()


def _current_session() -> dict | None:
    sid = st.session_state.get("thumb_session_id")
    if sid:
        return ss.load_session(sid)
    return None


def _render_prompt_lab():
    """Mode 1 — generate Flow prompts."""
    st.markdown("#### 🎨 Prompt Lab — Google Flow 프롬프트 생성")

    col1, col2, col3 = st.columns(3)
    with col1:
        countries = list_countries()
        country_labels = [label for _, label in countries]
        country_idx = st.selectbox("국가", range(len(countries)),
                                   format_func=lambda i: country_labels[i], key="thumb_country")
        country_key = countries[country_idx][0]
    with col2:
        # v1.0.0-alpha.62: theme/mood is now a shared value across song ·
        # thumbnail · YouTube, chosen from a dropdown (with a 🎲 variation
        # button) so the thumbnail mood always matches the song's.
        from services import shared_mood as SM
        mood_options = SM.get_mood_options(st.session_state)
        if not mood_options:
            mood_options = ["rainy night drive"]
        tc1, tc2 = st.columns([5, 1])
        with tc1:
            cur = SM.get_shared_mood(st.session_state) or mood_options[0]
            if cur not in mood_options:
                mood_options = [cur] + mood_options
            theme = st.selectbox(
                "테마/무드 (곡·유튜브와 공유)", mood_options,
                index=mood_options.index(cur),
                key="thumb_theme_select",
                help="곡·썸네일·유튜브가 같은 무드를 쓰도록 공유됩니다. "
                     "🎲로 새 무드를 제안받을 수 있어요.")
            SM.set_shared_mood(st.session_state, theme)
        with tc2:
            if st.button("🎲", key="thumb_theme_variation",
                         help="시티팝 무드 제안", use_container_width=True):
                new = SM.add_variation(st.session_state)
                SM.set_shared_mood(st.session_state, new)
                st.rerun()
    with col3:
        volume = 1  # decoupled; put the Vol. number directly in the title text
        count = st.number_input("생성 개수", min_value=1, max_value=10, value=1, step=1,
                                key="thumb_count",
                                help="이미지를 몇 장 만들지. 5를 넣으면 5장 생성됩니다.")

    col4, col5 = st.columns(2)
    with col4:
        title = st.text_input("플레이리스트 제목 (Canva가 입힐 텍스트)",
                              value="CityPop Playlist", key="thumb_title")
    with col5:
        subtitle = st.text_input("부제목 (선택)", value="1990s Night Drive", key="thumb_subtitle")

    include_person = st.toggle(
        "👤 인물(여성) 포함 — 1990 레트로 시티팝 앨범자켓 스타일", value=True,
        key="thumb_include_person",
        help="켜면: 국가별 20대 초반 여성이 중앙에 있는 앨범자켓/구독유도형 썸네일. "
             "끄면: 인물 없는 순수 배경(도시 야경) 컴포지션 — 이전 스타일.",
    )
    if not include_person:
        st.caption("ℹ️ 인물 없이 배경(도시 야경)만 생성됩니다. 타이틀 안전영역은 "
                   "좌/우/상/하 중 다양하게 배치됩니다.")

    # v1.0.0-alpha.71: optional thumbnail FORM (A~F) — injects that form's
    # composition constraint into the generated image prompt (see
    # services/thumbnail/prompt_generator.generate_flow_prompt(form=...))
    # so the background actually has the negative space html_renderer.py's
    # layout needs. "선택 안 함" keeps the exact pre-alpha.71 prompt.
    from services.thumbnail.html_renderer import FORMS as HR_FORMS
    form_options = ["선택 안 함 (기존 방식)"] + [
        f"{k} · {v['label']} ({v['rec']})" for k, v in HR_FORMS.items()
    ]
    form_idx = st.selectbox(
        "🆕 썸네일 형태 (선택 시 프리미엄 HTML 렌더러용 구도로 이미지 생성)",
        range(len(form_options)), format_func=lambda i: form_options[i],
        key="thumb_form_idx",
        help="형태를 고르면 배경 이미지 생성 프롬프트에 그 형태 전용 구도 제약이 "
             "추가되어(좌우 여백, 중앙 여백 등) 아래 '🆕 프리미엄 (형태별)' 모드에서 "
             "텍스트를 올릴 자리가 실제로 비게 됩니다.",
    )
    selected_form = list(HR_FORMS.keys())[form_idx - 1] if form_idx > 0 else None

    # ── v1.0.0-alpha.77: Korean free-form description → English prompt box ──
    # Describe the exact image (pose, clothing, objects, setting) in Korean; an
    # LLM composes one polished English prompt that weaves it into the existing
    # country/mood/form styling. Leaving it empty keeps the legacy behavior
    # (country/mood/person dropdowns → N varied scenes).
    st.markdown("##### ✍️ 원하는 이미지 서술 (선택) — 한글로 자유롭게")
    # Staging-key pattern (see alpha.64): the 🎲 button can't write the
    # text_area's own key after the widget is instantiated, so it stages the
    # suggestion in a *_pending key and we move it in before the widget renders.
    if "thumb_freeform_ko_pending" in st.session_state:
        st.session_state["thumb_freeform_ko"] = st.session_state.pop("thumb_freeform_ko_pending")
    fc1, fc2 = st.columns([9, 1])
    with fc1:
        freeform_ko = st.text_area(
            "이미지 내용 (비우면 기존 방식: 국가/무드/인물 조합으로 N장 다양하게 생성)",
            key="thumb_freeform_ko",
            placeholder="예: 비 오는 밤 홍대 골목, 짧은 흑발 보브에 베이지 트렌치코트를 입은 여성이 "
                        "워크맨을 들고 서 있음. 네온 간판이 젖은 바닥에 반사됨.",
            height=170,
        ).strip()
    with fc2:
        st.write("")  # nudge the button down to align with the box
        if st.button("🎲", key="thumb_freeform_dice", use_container_width=True,
                     help=f"선택한 무드('{theme}') 기반 시티팝 씬을 한글로 제안"):
            from services.thumbnail.prompt_composer import suggest_korean_prompt
            st.session_state["thumb_freeform_ko_pending"] = suggest_korean_prompt(
                theme, country_key, include_person=include_person)
            st.rerun()

    if st.button("🌐 영어 프롬프트 만들기 / 미리보기", key="thumb_compose_en",
                 help="한글 서술이 있으면 Gemini로 영어 이미지 프롬프트를 생성합니다. "
                      "비어 있으면 기본 템플릿 프롬프트를 미리보기로 채웁니다."):
        composed = compose_english_prompt(freeform_ko, country_key, theme,
                                          include_person=include_person, form=selected_form)
        st.session_state["thumb_en_prompt"] = composed["main_prompt"]
        st.session_state["thumb_en_prompt_source"] = composed["prompt_source"]
        st.rerun()

    en_prompt = st.text_area(
        "영어 프롬프트 (편집 가능 · 한글 서술이 있으면 이 박스가 생성의 최종 소스)",
        key="thumb_en_prompt",
        height=200,
        help="여기 내용을 직접 수정할 수 있습니다. 한글 서술이 있으면 이 텍스트가 "
             "그대로 이미지 provider에 전달됩니다.",
    )
    _src = st.session_state.get("thumb_en_prompt_source")
    if freeform_ko:
        if _src == "llm":
            st.caption("🟢 Gemini가 한글 서술을 반영해 생성 · 이 박스가 생성의 유일한 소스 "
                       "(생성 개수만큼 이 프롬프트로 만듦)")
        elif _src in ("fallback_nokey", "fallback_error"):
            reason = "Gemini API 키 없음" if _src == "fallback_nokey" else "Gemini 호출 실패"
            st.caption(f"⚠️ {reason} → 기본 템플릿 프롬프트로 폴백. 위 박스를 직접 영어로 "
                       "수정하면 그대로 사용됩니다. (사이드바 🤖 AI Composer에 Gemini 키 입력 시 자동 변환)")
        else:
            st.caption("ℹ️ '영어 프롬프트 만들기'를 누르면 한글 서술을 반영해 변환합니다. "
                       "누르지 않고 생성해도 자동 변환됩니다.")
    else:
        st.caption("ℹ️ 한글 서술이 비어 있어 **기존 방식**(국가/무드/인물 → N개 다양한 씬)으로 "
                   "생성됩니다. 이 박스는 참고용 미리보기입니다.")

    # ── Project link + real image generation ──────────────────────────────
    col_p, col_r = st.columns([1, 1])
    with col_p:
        projects = list_song_projects()
        proj_options = ["(프로젝트 없음 — 독립 세션)"] + [
            f"{p['name']} ({p['song_count']}곡)" for p in projects
        ]
        proj_idx = st.selectbox(
            "프로젝트 (선택 시 같은 폴더의 thumbnails/ 에 저장)",
            range(len(proj_options)),
            format_func=lambda i: proj_options[i],
            key="thumb_project",
            help="Song Lab 프로젝트를 고르면 음원(songs/)과 분리된 thumbnails/ 폴더에 이미지가 저장됩니다.",
        )
        project_folder = None if proj_idx == 0 else projects[proj_idx - 1]["path"]
    with col_r:
        _ENGINE_OPTIONS = {
            "Gemini (Nano Banana)": {
                "key": "gemini",
                "dep_fn": igd.check_image_gen_dependencies,
                "toggle_label": "실제 이미지 생성 (Gemini · Nano Banana)",
                "not_ready_hint": "좌측 사이드바 🤖 AI Composer → Gemini 칸에 API 키를 입력하면 켜집니다.",
                "ready_caption": None,  # uses dep['model']/dep['backend'] (see below)
                "per_image_time": None,
            },
            "Nano Banana 2 (Apiframe · 기존 연결 재사용)": {
                "key": "apiframe_nanobanana",
                "dep_fn": igd.check_apiframe_nanobanana_dependencies,
                "toggle_label": "실제 이미지 생성 (Nano Banana 2 · Apiframe)",
                "not_ready_hint": "좌측 사이드바 🎨 Image Gen 칸에 Apiframe API 키를 입력하면 켜집니다.",
                "ready_caption": "🟢 실제 생성 ON · Nano Banana 2 (Apiframe · 기존 연결 재사용) "
                                 "· 1장당 약 30초~2분 소요 (일시적 용량 부족 시 자동 재시도)",
                "per_image_time": None,
            },
            "ChatGPT (GPT Image 2 · 기존 연결 재사용)": {
                "key": "gpt_image",
                "dep_fn": igd.check_gpt_image_dependencies,
                "toggle_label": "실제 이미지 생성 (GPT Image 2)",
                "not_ready_hint": "좌측 사이드바 🤖 AI Composer → ChatGPT 칸에 API 키를 입력하면 켜집니다.",
                "ready_caption": "🟢 실제 생성 ON · GPT Image 2 (OpenAI · 기존 ChatGPT 연결 재사용) "
                                 "· 1장당 약 10~30초 소요 (요청 제한 시 자동 재시도)",
                "per_image_time": None,
            },
            "Midjourney (LinkrAPI)": {
                "key": "midjourney_linkr",
                "dep_fn": igd.check_midjourney_linkr_dependencies,
                "toggle_label": "실제 이미지 생성 (Midjourney · LinkrAPI)",
                "not_ready_hint": "좌측 사이드바 🎨 Image Gen 칸에 LinkrAPI API 키(lkr_)를 입력하면 켜집니다.",
                "ready_caption": "🟢 실제 생성 ON · Midjourney (LinkrAPI) · ⚠️ 미드저니는 그리드→업스케일 "
                                 "2단계라 1장당 약 1~3분 걸릴 수 있습니다 (진행 로그로 상태 확인 가능)",
                "per_image_time": None,
            },
        }
        engine_label = st.selectbox(
            "이미지 엔진",
            list(_ENGINE_OPTIONS.keys()),
            key="thumb_engine",
            help=("Gemini: Google API 키로 직접 생성 (REST). "
                  "Nano Banana 2 / ChatGPT(GPT Image 2): 이미 연결한 Apiframe/ChatGPT 키를 "
                  "그대로 재사용해 생성 — 별도 키 불필요. "
                  "Midjourney (LinkrAPI): 본인 Midjourney 계정을 LinkrAPI로 구동 "
                  "(LINKRAPI_API_KEY 필요). 비동기 2단계라 느립니다(1장 1~3분). "
                  "(Midjourney/Apiframe 조합은 계정 풀 불안정으로 제외했습니다 — "
                  "필요시 다음 세션에서 다시 켤 수 있습니다.)"),
        )
        opt = _ENGINE_OPTIONS[engine_label]
        engine = opt["key"]
        dep = opt["dep_fn"]()
        use_real = st.toggle(
            opt["toggle_label"],
            value=dep["ready"],
            disabled=not dep["ready"],
            key="thumb_use_real",
            help=("실제 이미지를 API로 생성합니다." if dep["ready"]
                  else f"준비 안 됨 → {dep['key_hint']}"),
        )
        if not dep["ready"]:
            st.caption(f"⚠️ 실제 생성 비활성 → 목업으로 진행. {opt['not_ready_hint']}")
        elif use_real:
            if opt["ready_caption"]:
                st.caption(opt["ready_caption"])
            else:
                st.caption(f"🟢 실제 생성 ON · 모델 {dep['model']} ({dep['backend'].upper()})")

    # Optional: explicit new-session button
    use_queue = st.toggle(
        "🔄 백그라운드 대기열로 생성", value=(count > 1 and use_real),
        key="thumb_use_queue",
        help="켜면: 별도 프로세스에서 생성하며 화면이 즉시 반응합니다 — 여러 장/실제 API 생성 시 추천. "
             "진행 상태는 Dashboard/Settings의 '작업 상태'에서 실시간 확인 가능합니다. "
             "끄면: 이 화면에서 완료까지 기다립니다(1장·목업 생성에 적합).",
    )
    col_gen, col_new = st.columns([3, 1])
    with col_new:
        force_new = st.button("🆕 새 세션", use_container_width=True,
                              help="새 썸네일 세션을 시작합니다 (기존 세션 자산은 보존됨)")
    with col_gen:
        gen_label = f"🔄 {count}개 이미지 생성 (대기열)" if use_queue else f"🎨 {count}개 이미지 생성"
        do_generate = st.button(gen_label, type="primary", use_container_width=True)

    if force_new:
        # Start a fresh session immediately
        sess = ss.create_session(country_key, theme, title, volume, subtitle,
                                 project_folder=project_folder)
        st.session_state["thumb_session_id"] = sess["session_id"]
        st.session_state.pop("thumb_prompts", None)
        st.session_state.pop("brand_results", None)
        st.success(f"🆕 새 세션 시작: {sess['session_id']}")
        st.rerun()

    if do_generate:
        # Decide whether to reuse the current session or create a new one.
        # If inputs changed vs the saved session_manifest, start a fresh
        # session so the manifest stays consistent. Old session + its
        # uploads/candidates/branding are preserved on disk (not deleted).
        sid = st.session_state.get("thumb_session_id")
        current_sess = ss.load_session(sid) if sid else None

        if not sid or not ss.inputs_match_session(
            current_sess, country_key, theme, title, volume, subtitle
        ):
            sess = ss.create_session(country_key, theme, title, volume, subtitle,
                                     project_folder=project_folder)
            sid = sess["session_id"]
            st.session_state["thumb_session_id"] = sid
            # Clear stale prompt/brand display from the previous session
            st.session_state.pop("brand_results", None)

        # Hybrid (v1.0.0-alpha.77): if the user wrote a Korean description, the
        # (possibly edited) English box is the single source for all `count`
        # candidates; otherwise fall back to the legacy varied-scene batch.
        if freeform_ko:
            override = (st.session_state.get("thumb_en_prompt") or "").strip()
            if not override:
                composed = compose_english_prompt(freeform_ko, country_key, theme,
                                                  include_person=include_person, form=selected_form)
                override = composed["main_prompt"]
                st.session_state["thumb_en_prompt"] = override
                st.session_state["thumb_en_prompt_source"] = composed["prompt_source"]
            prompts = build_prompt_batch(country_key, theme, count, include_person=include_person,
                                         form=selected_form, english_override=override,
                                         freeform_ko=freeform_ko)
        else:
            prompts = build_prompt_batch(country_key, theme, count, include_person=include_person,
                                         form=selected_form)
        if not use_real:
            mode_label = "목업"
        elif engine == "apiframe_nanobanana":
            mode_label = "실제 (Nano Banana 2 · Apiframe)"
        elif engine == "gpt_image":
            mode_label = "실제 (GPT Image 2 · OpenAI)"
        else:
            mode_label = "실제 (Gemini)"

        if use_queue:
            from services.thumbnail_job_manager import start_thumbnail_job
            job = start_thumbnail_job(
                sid, prompts,
                settings={"use_real": use_real, "model": None, "engine": engine},
            )
            st.session_state["thumb_prompts"] = prompts
            if job.get("queued"):
                st.warning(f"⏳ 대기열에 추가됨 — 다른 작업(job {job['queued_behind']}) 완료 후 "
                           f"Settings에서 다시 시도하세요.")
            else:
                st.success(f"🔄 백그라운드로 {count}장 생성 시작됨 ({mode_label}) · "
                           f"job_id={job['job_id']} · Dashboard/Settings에서 진행 상태 확인 가능")
        else:
            with st.spinner(f"{count}장 이미지 생성 중… ({mode_label})"):
                cands = ss.generate_images(sid, prompts, use_real=use_real, engine=engine)
            st.session_state["thumb_prompts"] = prompts
            ok = sum(1 for c in cands if c.get("status") == "image_generated")
            fail = len(cands) - ok
            where = "프로젝트 thumbnails/ 폴더" if project_folder else "세션 폴더"
            if fail and ok == 0:
                first_err = next((c.get("gen_error") for c in cands if c.get("gen_error")), "")
                st.error(f"❌ 이미지 생성 실패 ({fail}개). 사유: {first_err}")
            elif fail:
                st.warning(f"⚠️ 이미지 {ok}개 생성 / {fail}개 실패 → Candidate Gallery에서 확인. (저장: {where})")
            else:
                st.success(
                    f"✅ {ok}개 이미지 생성 완료! ({mode_label} · 저장: {where}) "
                    f"→ **Candidate Gallery** 탭에서 선택하세요. (세션: {sid})"
                )

    # Show generated images (inline preview) FIRST, then the prompts for reference.
    prompts = st.session_state.get("thumb_prompts", [])
    sid = st.session_state.get("thumb_session_id")
    if prompts and sid:
        cands = ss.load_candidates(sid)
        gen = [c for c in cands if c.get("uploaded_image_path")]
        failed = [c for c in cands if c.get("status") == "generation_failed"]

        st.divider()
        st.markdown(f"#### 🖼️ 생성된 이미지 ({len(gen)}/{len(cands)})")
        if gen:
            ncol = min(3, len(gen))
            cols = st.columns(ncol)
            for idx, c in enumerate(gen):
                fp = c["uploaded_image_path"]
                with cols[idx % ncol]:
                    if fp and Path(fp).exists():
                        st.image(fp, use_container_width=True,
                                 caption=f"{c['candidate_id']} · {c.get('concept', '')}")
                    else:
                        st.warning(f"{c['candidate_id']}: 파일을 찾을 수 없음")
            if gen[0].get("gen_provider") == "mock":
                st.caption("ℹ️ 목업(placeholder) 이미지입니다. 실제 생성: 사이드바에서 API 키 입력 "
                           "(Gemini → 🤖 AI Composer / Nano Banana 2 → 🎨 Image Gen / "
                           "GPT Image 2 → 🤖 AI Composer) → "
                           "위의 '실제 이미지 생성' 토글 ON.")
            st.caption("→ **🖼️ Candidate Gallery** 탭에서 이미지를 선택하면 Brand Thumbnail(Canva)로 넘어갑니다.")
        if failed:
            st.error(f"❌ {len(failed)}개 생성 실패 — 사유: {failed[0].get('gen_error') or '알 수 없음'}")
        if not gen and not failed:
            st.info("아직 생성된 이미지가 없습니다. 위에서 배치 수를 고르고 생성하세요.")

    if prompts:
        st.divider()
        st.markdown(f"**프롬프트 ({len(prompts)}개 · 참고/재현용)**")
        st.caption("각 이미지에 사용된 프롬프트입니다. 이미지에는 텍스트/로고가 없습니다 (제목은 Canva가 입힙니다).")

        for i, p in enumerate(prompts, 1):
            with st.expander(f"#{i} · {p['scene']} · {p['title_safe_area']}", expanded=(i == 1)):
                st.markdown("**메인 프롬프트:**")
                st.code(p["main_prompt"], language=None)
                st.markdown("**네거티브 프롬프트:**")
                st.code(p["negative_prompt"], language=None)
                cc1, cc2 = st.columns(2)
                with cc1:
                    st.caption(f"🎯 타이틀 세이프 영역: {p['title_safe_area']}")
                    st.caption(f"📐 구도: {p['composition_note'][:60]}...")
                with cc2:
                    # Color palette swatches
                    swatches = "".join(
                        f"<span style='display:inline-block;width:24px;height:24px;"
                        f"background:{c};border-radius:4px;margin-right:4px'></span>"
                        for c in p["color_palette"]
                    )
                    st.markdown(f"🎨 팔레트: {swatches}", unsafe_allow_html=True)
                    st.caption(f"✨ Canva 액센트: {p['canva_accent_color']}")


def _render_candidate_gallery():
    """Mode 2 — pick a session from the image Library (or the current one),
    upload Flow images, and manage candidates. Prompt Lab is no longer a
    prerequisite: any session in the sidebar Library's 이미지 라이브러리 can be
    opened here directly (v1.0.0-alpha.43)."""
    from services.library_labels import list_image_library_sessions

    st.markdown("#### 🖼️ Candidate Gallery — Flow 이미지 업로드 & 선택")

    # ── Library session picker (identical labels to 좌측 Library) ─────────
    lib_sessions = list_image_library_sessions(limit=30)
    current_sid = st.session_state.get("thumb_session_id")

    if lib_sessions:
        option_ids = [s["session_id"] for s in lib_sessions]
        option_labels = {s["session_id"]: s["library_label"] for s in lib_sessions}
        if current_sid in option_ids:
            options = option_ids
            default_idx = option_ids.index(current_sid)
        else:
            options = ["__none__"] + option_ids
            option_labels["__none__"] = "(이미지 라이브러리에서 세션 선택)"
            default_idx = 0
        chosen = st.selectbox(
            "📚 이미지 라이브러리 세션", options, index=default_idx,
            format_func=lambda s: option_labels.get(s, s),
            key="gallery_lib_session",
            help="좌측 Library의 이미지 라이브러리와 동일한 목록입니다. "
                 "Prompt Lab을 거치지 않아도 기존 세션의 이미지를 바로 선택할 수 있습니다.",
        )
        if chosen != "__none__" and chosen != current_sid:
            st.session_state["thumb_session_id"] = chosen
            st.session_state.pop("brand_results", None)
            st.rerun()

    sess = _current_session()
    if not sess:
        if lib_sessions:
            st.info("위에서 이미지 라이브러리 세션을 선택하거나, Prompt Lab에서 새로 생성하세요.")
        else:
            st.info("아직 세션이 없습니다. Prompt Lab에서 프롬프트를 생성하세요.")
        return

    st.caption(f"세션: {sess['session_id']} · {sess['country']} · {sess['theme']}")

    candidates = ss.load_candidates(sess["session_id"])
    if not candidates:
        st.info("프롬프트가 없습니다. Prompt Lab에서 생성하세요.")
        return

    # Upload section
    st.markdown("**📤 Flow 이미지 업로드**")
    st.caption("Google Flow에서 생성·다운로드한 이미지를 각 프롬프트에 업로드하세요.")

    upload_cols = st.columns(2)
    for idx, cand in enumerate(candidates):
        with upload_cols[idx % 2]:
            cid = cand["candidate_id"]
            st.markdown(f"**{cid}** · {cand.get('concept', '')}")
            uploaded = st.file_uploader(
                f"이미지 업로드 ({cid})", type=["png", "jpg", "jpeg", "webp"],
                key=f"upload_{cid}", label_visibility="collapsed",
            )
            if uploaded is not None:
                suffix = Path(uploaded.name).suffix or ".png"
                path = ss.upload_flow_image_bytes(
                    sess["session_id"], cid, uploaded.getvalue(), suffix
                )
                st.success(f"✅ 업로드됨")

    st.divider()

    # Gallery of uploaded images
    candidates = ss.load_candidates(sess["session_id"])  # reload
    uploaded_cands = [c for c in candidates if c.get("uploaded_image_path")]

    if uploaded_cands:
        st.markdown(f"**🖼️ 업로드된 후보 ({len(uploaded_cands)}개)**")
        gallery_cols = st.columns(3)
        for idx, cand in enumerate(uploaded_cands):
            with gallery_cols[idx % 3]:
                img_path = cand["uploaded_image_path"]
                if img_path and Path(img_path).exists():
                    st.image(img_path, use_container_width=True)
                cid = cand["candidate_id"]

                # Rating
                rating = st.radio(
                    "평가", ["Keep", "Maybe", "Reject"],
                    index=["Keep", "Maybe", "Reject"].index(cand["rating"]) if cand.get("rating") in ["Keep", "Maybe", "Reject"] else 0,
                    key=f"rating_{cid}", horizontal=True, label_visibility="collapsed",
                )
                if rating != cand.get("rating", "Keep"):
                    ss.set_candidate_rating(sess["session_id"], cid, rating)
                    st.rerun()

                # Select for branding
                is_rejected = cand.get("status") == "rejected"
                selected = st.checkbox(
                    "✨ 브랜딩 선택", value=cand.get("selected_for_branding", False),
                    key=f"select_{cid}", disabled=is_rejected,
                )
                if selected != cand.get("selected_for_branding"):
                    ss.select_for_branding(sess["session_id"], cid, selected)
                    st.rerun()
    else:
        st.info("아직 업로드된 이미지가 없습니다. 위에서 Flow 이미지를 업로드하세요.")


def _render_brand_thumbnail():
    """Mode 3 — apply Canva branding to selected images."""
    st.markdown("#### ✨ Brand Thumbnail — 선택 이미지에 브랜드 적용")

    sess = _current_session()
    if not sess:
        st.info("먼저 Prompt Lab에서 세션을 시작하세요.")
        return

    selected = ss.get_selected_candidates(sess["session_id"])
    if not selected:
        st.warning("⚠️ 브랜딩할 이미지가 선택되지 않았습니다. Candidate Gallery에서 이미지를 선택하세요.")
        return

    st.success(f"✅ {len(selected)}개 이미지가 브랜딩 대상으로 선택됨")

    # ── Preview of selected candidates ──
    preview_cols = st.columns(min(len(selected), 4))
    for idx, cand in enumerate(selected):
        with preview_cols[idx % len(preview_cols)]:
            img_p = cand.get("uploaded_image_path", "")
            if img_p and Path(img_p).exists():
                st.image(img_p, use_container_width=True,
                         caption=cand["candidate_id"])

    st.divider()

    # ── Brand settings ──
    # Fixed top/bottom lines; city name (English) + local-language line editable.
    BRAND_TEXT = "Seoul Records"      # top eyebrow (fixed)
    BOTTOM_LINE = "CityPop Playlist"  # bottom line (fixed)

    # Language selector: pick a country → auto-fills the local line in that language.
    # City name stays as typed (English).
    from services.thumbnail.country_presets import list_countries
    _countries = list_countries()
    _country_map = {label: key for key, label in _countries}
    _lang_labels = [label for _, label in _countries]

    col1, col2 = st.columns(2)
    with col1:
        _defs = get_title_defaults(sess["country"])
        # Initialize once; re-seed when the language dropdown changes, not the session country.
        if "_brand_init" not in st.session_state:
            st.session_state["brand_title"] = _defs["city"]
            st.session_state["brand_cjk"] = _defs["night_local"]
            st.session_state["_brand_init"] = True

        title = st.text_input("도시/국가명 (가장 크게, 영어)", key="brand_title",
                              help="자유롭게 입력 (예: BANGKOK, TOKYO, SEOUL).")

        # Local-language dropdown + text input
        lang_default_idx = next((i for i, (k, _) in enumerate(_countries) if k == sess["country"]), 0)
        lang_choice = st.selectbox("현지 언어 선택", _lang_labels,
                                   index=lang_default_idx, key="brand_lang",
                                   help="국가를 선택하면 현지어로 자동 변환됩니다.")
        _lang_key = _country_map.get(lang_choice, "korea")
        _lang_defs = get_title_defaults(_lang_key)
        if st.session_state.get("_brand_lang_prev") != _lang_key:
            st.session_state["brand_cjk"] = _lang_defs["night_local"]
            st.session_state["_brand_lang_prev"] = _lang_key

        cjk_subtext = st.text_input("현지어 줄 (밤의 음악 등)", key="brand_cjk",
                                    help="위 언어 선택 시 자동 변환 · 직접 수정도 가능.")
        brand_text = BRAND_TEXT
        subtitle = BOTTOM_LINE
    with col2:
        st.caption(f"📌 상단 고정: **{BRAND_TEXT}**")
        st.caption(f"📌 하단 고정: **{BOTTOM_LINE}**")
        canva_mode = st.selectbox("출력 모드",
                                  ["🎬 자동 합성 (앱 내 렌더링)", "Canva Manual (수동)", "Canva Autofill"],
                                  key="canva_mode",
                                  help="자동 합성: 앱이 제목까지 그려서 완성 썸네일을 "
                                       "바로 만듭니다 (Canva 구독/템플릿 불필요).")

    # YouTube sticker controls (optional — off by default for the premium minimal look)
    st.caption("유튜브 스티커 (선택 · 기본 꺼짐 — 끄면 미니멀 고급 썸네일)")
    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1:
        show_eq = st.checkbox("📊 이퀄라이저", value=False, key="brand_eq")
    with sc2:
        show_sub = st.checkbox("🔴 구독 버튼", value=False, key="brand_sub")
    with sc3:
        show_like = st.checkbox("♥ 좋아요", value=False, key="brand_like")
    with sc4:
        title_center = st.checkbox("제목 중앙 배치", value=True, key="brand_title_center")

    # Title color + size + fixed-line colors
    tc1, tc2, tc3, tc4 = st.columns([1, 1, 1, 2])
    with tc1:
        title_color = st.color_picker("제목 색상", value="#FFFFFF", key="brand_title_color")
    with tc2:
        eyebrow_color = st.color_picker("상단 색상", value="#FFFFFF", key="brand_eyebrow_color",
                                        help="Seoul Records 텍스트 색상")
    with tc3:
        _default_accent = selected[0].get("canva_accent_color", "#ff4d6d") if selected else "#ff4d6d"
        subtitle_color = st.color_picker("하단 색상", value=_default_accent,
                                         key="brand_subtitle_color",
                                         help="CityPop Playlist 텍스트 색상 (기본 = 엑센트)")
    with tc4:
        title_scale = st.slider("제목 크기", 0.80, 1.60, 1.10, 0.05,
                                key="brand_title_scale",
                                help="1.0 = 기본 · 값이 클수록 제목이 커집니다.")

    if st.button("✨ 선택 이미지로 브랜드 썸네일 만들기", type="primary", use_container_width=True):
        results = []
        for cand in selected:
            # Generate payload
            payload = cb.generate_canva_payload(
                sess["session_id"], cand, title, subtitle, brand_text,
                sess["volume"], sess["country"], sess["theme"],
            )
            cb.save_canva_payload(sess["session_id"], cand["candidate_id"], payload)

            if "자동" in canva_mode:
                branded = cb.mock_render_branded_thumbnail(
                    sess["session_id"], cand, title, subtitle, brand_text,
                    cand.get("canva_accent_color", "#ff4d6d"),
                    show_equalizer=show_eq, show_subscribe=show_sub, show_like=show_like,
                    title_layout="center" if title_center else "lower-left",
                    title_color=title_color, title_scale=title_scale,
                    cjk_subtext=cjk_subtext,
                    eyebrow_color=eyebrow_color, subtitle_color=subtitle_color,
                )
                results.append((cand, branded, payload))
            else:
                results.append((cand, None, payload))

        st.session_state["brand_results"] = results
        st.success(f"✅ {len(results)}개 브랜드 썸네일 처리 완료!")

    # Show results
    results = st.session_state.get("brand_results", [])
    if results:
        st.divider()
        for cand, branded, payload in results:
            cols = st.columns([2, 1])
            with cols[0]:
                if branded and Path(branded).exists():
                    st.image(branded, use_container_width=True,
                             caption=f"{cand['candidate_id']} — 브랜드 썸네일")
                else:
                    st.info(f"{cand['candidate_id']} — Canva payload 생성됨 (수동 적용)")
            with cols[1]:
                st.caption("Canva 템플릿 변수:")
                st.json(payload["variables"], expanded=False)
                if branded and Path(branded).exists():
                    if st.button("📦 최종 내보내기", key=f"export_{cand['candidate_id']}"):
                        final = cb.export_final_thumbnail(sess["session_id"], branded)
                        if final:
                            st.success(f"✅ 내보냄: {Path(final).name}")


def _render_form_studio():
    """
    Mode — 🆕 프리미엄 (형태별) (v1.0.0-alpha.71).

    New HTML/CSS + Playwright renderer (services/thumbnail/html_renderer.py,
    the JazzNe-benchmarked 6-form design system) applied to a Candidate
    Gallery selection. Independent of the existing PIL-based ✨ Brand
    Thumbnail flow — canva_branding.py is untouched; this is purely additive.
    """
    from services.thumbnail import html_renderer as hr

    st.markdown("#### 🆕 프리미엄 썸네일 (형태별 HTML 렌더러)")
    st.caption("JazzNe 벤치마킹 6형태 디자인 시스템 · Playwright 헤드리스 렌더링")

    sess = _current_session()
    if not sess:
        st.info("먼저 Prompt Lab에서 세션을 시작하세요.")
        return

    selected = ss.get_selected_candidates(sess["session_id"])
    if not selected:
        st.warning("⚠️ 렌더링할 이미지가 선택되지 않았습니다. Candidate Gallery에서 이미지를 선택하세요.")
        return

    st.success(f"✅ {len(selected)}개 이미지 선택됨")

    # ── 1. Form ──────────────────────────────────────────────────────────
    form_keys = list(hr.FORMS.keys())
    form_labels = [f"{k} · {hr.FORMS[k]['label']} ({hr.FORMS[k]['rec']})" for k in form_keys]
    # Default to whatever form was picked in Prompt Lab (if any), so the
    # form-matched image generated there is the natural starting point here.
    prompt_lab_form_idx = st.session_state.get("thumb_form_idx", 0)
    default_idx = max(prompt_lab_form_idx - 1, 0)
    form_idx = st.radio(
        "1 · 형태", range(len(form_keys)), format_func=lambda i: form_labels[i],
        horizontal=True, index=default_idx, key="form_studio_form_idx",
    )
    form = form_keys[form_idx]

    # Auto-apply the form's recommended font whenever the form changes.
    if st.session_state.get("_form_studio_prev_form") != form:
        st.session_state["form_studio_title_font_idx"] = hr.FORMS[form]["recFont"]
        st.session_state["_form_studio_prev_form"] = form

    # ── 2. Ratio ─────────────────────────────────────────────────────────
    ratio_label = st.radio("2 · 비율", ["16:9 (썸네일)", "1:1 (커버)"],
                           horizontal=True, key="form_studio_ratio")
    ratio = "169" if ratio_label.startswith("16") else "11"

    # ── 3. Fonts ─────────────────────────────────────────────────────────
    fc1, fc2 = st.columns(2)
    with fc1:
        title_font_idx = st.selectbox(
            "3 · 제목 폰트", range(len(hr.FONTS)), format_func=lambda i: hr.FONTS[i]["name"],
            key="form_studio_title_font_idx",
        )
        title_font_css = hr.FONTS[title_font_idx]["css"]
        st.caption(f"◆ {form}형 추천: {hr.FONTS[hr.FORMS[form]['recFont']]['name']}")
    with fc2:
        kr_font_idx = st.selectbox(
            "한글 폰트 (트랙리스트)", range(len(hr.KR_FONTS)), format_func=lambda i: hr.KR_FONTS[i]["name"],
            key="form_studio_kr_font_idx",
        )
        kr_font_css = hr.KR_FONTS[kr_font_idx]["css"]

    # ── 4. Text ──────────────────────────────────────────────────────────
    st.markdown("**4 · 텍스트**")
    kicker = st.text_input("키커 (상단 소형)", value="CITYPOP PLAYLIST", key="form_studio_kicker")
    tt1, tt2 = st.columns(2)
    with tt1:
        title1 = st.text_input("제목 1", value=sess.get("title", "Seoul"), key="form_studio_t1")
    with tt2:
        title2 = st.text_input("제목 2", value="Nights", key="form_studio_t2")
    badge = st.text_input("뱃지 텍스트 (D형 전용)", value="NEON SEOUL", key="form_studio_badge")
    tracks_raw = st.text_input("트랙리스트 (/ 로 구분)", value="", key="form_studio_tracks",
                               help="비워두면 트랙리스트 없이 렌더링됩니다.")
    tracks = [t.strip() for t in tracks_raw.split("/") if t.strip()]

    # ── 5. Colors ────────────────────────────────────────────────────────
    st.markdown("**5 · 색상**")
    cc1, cc2 = st.columns(2)
    with cc1:
        title_color = st.color_picker("제목 색", value="#f6efe2", key="form_studio_title_color")
    with cc2:
        point_color = st.color_picker("키커/포인트 색", value="#e4be6a", key="form_studio_point_color")

    spine_kwargs = {}
    if ratio == "11" and form in hr.SPINE_FORMS:
        st.markdown("**6 · 스파인 (1:1 전용)**")
        sc1, sc2 = st.columns(2)
        with sc1:
            spine_kwargs["spine_bg"] = st.color_picker(
                "스파인 배경색", value="#1a1420", key="form_studio_spine_bg")
        with sc2:
            spine_kwargs["spine_text"] = st.color_picker(
                "스파인 글씨색", value="#f4efe4", key="form_studio_spine_text")

    st.divider()

    # ── Background candidate + render ───────────────────────────────────
    cand_labels = [c["candidate_id"] for c in selected]
    cand_idx = st.selectbox("배경으로 쓸 후보 이미지", range(len(selected)),
                            format_func=lambda i: cand_labels[i], key="form_studio_cand")
    cand = selected[cand_idx]
    bg_path = cand.get("uploaded_image_path", "")

    if bg_path and Path(bg_path).exists():
        st.image(bg_path, caption=f"배경 후보: {cand['candidate_id']}", width=320)
    else:
        st.warning("선택한 후보에 이미지 파일이 없습니다.")

    if st.button("🎨 렌더링 (Playwright)", type="primary", use_container_width=True,
                key="form_studio_render_btn", disabled=not (bg_path and Path(bg_path).exists())):
        with st.spinner("HTML/CSS 조립 후 헤드리스 브라우저로 렌더링 중..."):
            try:
                out_dir = ss.session_path(sess["session_id"]) / "exports"
                out_dir.mkdir(parents=True, exist_ok=True)
                out_name = f"form_{form}_{ratio}_{cand['candidate_id']}.png"
                out = hr.render_thumbnail(
                    form=form, ratio=ratio, bg_image_path=bg_path,
                    kicker=kicker, title1=title1, title2=title2, badge=badge, tracks=tracks,
                    title_font_css=title_font_css, kr_font_css=kr_font_css,
                    title_color=title_color, point_color=point_color,
                    out_path=str(out_dir / out_name),
                    **spine_kwargs,
                )
                st.session_state["form_studio_last_render"] = out
                st.success(f"✅ 렌더 완료: {Path(out).name}")
            except Exception as e:
                st.error(f"렌더 실패: {type(e).__name__}: {e}")
                st.caption(
                    "Playwright/Chromium이 설치되지 않았다면: `pip install playwright` 후 "
                    "`playwright install chromium`을 한 번 실행하세요."
                )

    last = st.session_state.get("form_studio_last_render")
    if last and Path(last).exists():
        st.divider()
        st.markdown("**미리보기**")
        st.image(last, use_container_width=True)

    # ── Register as FINAL deliverables (16:9 + 1:1) ──────────────────────────
    # v1.0.0-alpha.81: the Premium (form) render is already a finished thumbnail
    # at the standard resolution (html_renderer outputs 1920x1080 / 3000x3000).
    # This renders BOTH ratios with the current form/text/color settings and
    # writes them to the STANDARD export filenames + asset manifest, so the
    # 📦 Exports view, Production QA, Video Renderer and YouTube Package all pick
    # them up (they scan for youtube_thumbnail_16x9* / streaming_cover_1x1* +
    # the manifest). Fixes the Premium↔Exports disconnect.
    st.divider()
    st.caption("위 형태·텍스트·색상 그대로 **16:9 썸네일 + 1:1 커버**를 최종 산출물로 등록합니다 "
               "→ 📦 Exports · Production QA · Video Renderer · YouTube Package에서 인식됩니다.")
    if st.button("✅ 최종 산출물로 등록 (16:9 & 1:1 동시 렌더)", type="primary",
                 use_container_width=True, key="form_studio_register_btn",
                 disabled=not (bg_path and Path(bg_path).exists())):
        from services.thumbnail import asset_exporter as ae
        from services.thumbnail import asset_types as AT
        exports_dir = ss.session_path(sess["session_id"]) / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)

        def _render_ratio(r: str, asset_type: str) -> str:
            skw = {}
            if r == "11" and form in hr.SPINE_FORMS:
                skw["spine_bg"] = st.session_state.get("form_studio_spine_bg", "#1a1420")
                skw["spine_text"] = st.session_state.get("form_studio_spine_text", "#f4efe4")
            out_path = exports_dir / ae.export_filename(sess["session_id"], asset_type)
            return hr.render_thumbnail(
                form=form, ratio=r, bg_image_path=bg_path,
                kicker=kicker, title1=title1, title2=title2, badge=badge, tracks=tracks,
                title_font_css=title_font_css, kr_font_css=kr_font_css,
                title_color=title_color, point_color=point_color,
                out_path=str(out_path), **skw,
            )

        with st.spinner("16:9 · 1:1 두 비율을 렌더링하고 최종 산출물로 등록 중..."):
            try:
                p169 = _render_ratio("169", AT.YOUTUBE_THUMBNAIL_16X9)
                p11 = _render_ratio("11", AT.STREAMING_COVER_1X1)
                ae.register_exports(sess["session_id"])
                st.session_state["form_studio_last_render"] = p169
                st.success("✅ 최종 등록 완료 — 16:9 썸네일 + 1:1 커버가 Exports · Production QA · "
                           "Video · YouTube에서 인식됩니다.")
                rc1, rc2 = st.columns(2)
                with rc1:
                    st.image(p169, caption="YouTube 썸네일 16:9", use_container_width=True)
                with rc2:
                    st.image(p11, caption="스트리밍 커버 1:1", use_container_width=True)
            except Exception as e:
                st.error(f"등록 실패: {type(e).__name__}: {e}")
                st.caption("Playwright/Chromium 미설치 시: `pip install playwright` 후 "
                           "`playwright install chromium` 실행.")


def _render_exports():
    """Mode 4 — export the 3 separated deliverables + crop tool."""
    from services.thumbnail import asset_exporter as ae
    from services.thumbnail import asset_types as AT
    from services.thumbnail.video_renderer_rules import select_video_background

    st.markdown("#### 📦 Exports — 최종 산출물 3종 분리")
    st.caption("썸네일(광고판) · MP4 배경(무대) · 1:1 커버(앨범 자켓)를 각각 분리해 내보냅니다.")

    sess = _current_session()
    if not sess:
        st.info("아직 세션이 없습니다. Prompt Lab에서 시작하세요.")
        return

    sid = sess["session_id"]

    # Pick a source background — prefer a branded thumbnail, else a selected candidate
    selected = ss.get_selected_candidates(sid)
    branded_dir = ss.session_path(sid) / "branded"
    branded_imgs = sorted(branded_dir.glob("branded_thumbnail_*.png")) if branded_dir.exists() else []

    # Build source options. For exports, we always need the CLEAN (no-text) background
    # to render titles fresh — using a branded thumbnail as bg would double the text.
    source_options = {}   # label → clean bg (16:9)
    square_for = {}       # label → clean bg (1:1)

    # Map branded thumbnails back to their raw candidate background.
    for cand in selected:
        raw = cand.get("uploaded_image_path", "")
        sq = cand.get("image_1x1", "")
        cid = cand["candidate_id"]
        if raw:
            source_options[f"선택 이미지: {cid}"] = raw
            if sq:
                square_for[f"선택 이미지: {cid}"] = sq

    if not source_options:
        st.warning("⚠️ 먼저 Candidate Gallery에서 이미지를 선택하거나 Brand Thumbnail을 만드세요.")
        return

    src_label = st.selectbox("소스 배경 이미지", list(source_options.keys()))
    bg_path = source_options[src_label]
    square_bg_path = square_for.get(src_label, "")  # native 1:1 → distortion-free cover
    if square_bg_path:
        st.caption("💿 1:1 커버는 동일 장면의 네이티브 정사각 이미지를 사용합니다 (좌우 왜곡 없음).")

    # Branding text
    from services.thumbnail.country_presets import get_country_preset, get_title_defaults
    from services.thumbnail import canva_branding as cb
    country_label = get_country_preset(sess["country"])["label"].split(" (")[0]
    accent = get_country_preset(sess["country"])["accent"]

    col1, col2 = st.columns(2)
    with col1:
        _defs = get_title_defaults(sess["country"])
        if st.session_state.get("_exp_country") != sess["country"]:
            st.session_state["exp_title"] = _defs["city"]
            st.session_state["exp_cjk"] = _defs["night_local"]
            st.session_state["_exp_country"] = sess["country"]
        title = st.text_input("도시/국가명 (가장 크게)", key="exp_title",
                              help="국가별 자동 제안 · 수정 가능.")
        exp_cjk = st.text_input("현지어 줄 (밤의 음악 등)", key="exp_cjk",
                                help="해당 국가 언어로 자동 제안 · 수정 가능.")
        brand_text = "Seoul Records"      # top (fixed)
        subtitle = "CityPop Playlist"     # bottom (fixed)
        st.caption("📌 상단 **Seoul Records** · 하단 **CityPop Playlist** 고정")
    with col2:
        crop_mode = st.selectbox("1:1 커버 크롭 모드",
                                 ["smart_title_safe", "center_crop", "fit_blur", "manual"],
                                 format_func=lambda m: {
                                     "smart_title_safe": "스마트 타이틀 세이프",
                                     "center_crop": "중앙 크롭",
                                     "fit_blur": "블러 배경 맞춤",
                                     "manual": "수동",
                                 }.get(m, m), key="exp_crop")

    ec1, ec2, ec3, ec4 = st.columns([1, 1, 1, 2])
    with ec1:
        exp_title_color = st.color_picker("제목 색상", value="#FFFFFF", key="exp_title_color")
    with ec2:
        exp_eyebrow_color = st.color_picker("상단 색상", value="#FFFFFF", key="exp_eyebrow_color",
                                            help="Seoul Records 텍스트 색상")
    with ec3:
        exp_subtitle_color = st.color_picker("하단 색상", value=accent, key="exp_subtitle_color",
                                             help="CityPop Playlist 색상 (기본 = 엑센트)")
    with ec4:
        exp_title_scale = st.slider("제목 크기", 0.80, 1.60, 1.10, 0.05,
                                    key="exp_title_scale",
                                    help="1.0 = 기본 · 값이 클수록 제목이 커집니다.")

    st.divider()

    # Export buttons
    bcol1, bcol2, bcol3, bcol4 = st.columns(4)
    with bcol1:
        if st.button("🖼️ YouTube 썸네일", use_container_width=True):
            p = ae.export_youtube_thumbnail(sid, bg_path, title, subtitle, brand_text,
                                            accent, exp_title_color, exp_title_scale, exp_cjk,
                                            exp_eyebrow_color, exp_subtitle_color)
            if p:
                ae.write_asset_manifest(sid, _rebuild_manifest(sid, ae, AT))
                st.success("✅ YouTube 썸네일 16:9")
    with bcol2:
        if st.button("🎬 영상 배경", use_container_width=True):
            p = ae.export_video_playback_background(sid, bg_path, brand_text)
            if p:
                ae.write_asset_manifest(sid, _rebuild_manifest(sid, ae, AT))
                st.success("✅ Video 재생 배경 16:9")
    with bcol3:
        if st.button("💿 1:1 커버", use_container_width=True):
            yt = ss.session_path(sid) / "exports" / ae.export_filename(sid, AT.YOUTUBE_THUMBNAIL_16X9)
            p = ae.export_streaming_cover(sid, str(yt), bg_path, title, subtitle,
                                          brand_text, accent, crop_mode,
                                          exp_title_color, exp_title_scale, exp_cjk,
                                          exp_eyebrow_color, exp_subtitle_color,
                                          square_bg_path)
            if p:
                ae.write_asset_manifest(sid, _rebuild_manifest(sid, ae, AT))
                st.success("✅ 스트리밍 커버 1:1")
    with bcol4:
        if st.button("📦 전체 내보내기", type="primary", use_container_width=True):
            results = ae.export_all_required_assets(sid, bg_path, title, subtitle,
                                                    brand_text, accent, crop_mode,
                                                    exp_title_color, exp_title_scale, exp_cjk,
                                                    exp_eyebrow_color, exp_subtitle_color,
                                                    square_bg_path)
            st.success(f"✅ 3종 전체 내보내기 완료!")

    st.divider()

    # Output checklist
    st.markdown("**📋 필수 산출물 체크리스트**")
    exports_dir = ss.session_path(sid) / "exports"
    checklist = {
        AT.YOUTUBE_THUMBNAIL_16X9: ("YouTube Thumbnail 16:9", "광고판 · Playlist 타이틀 있음"),
        AT.VIDEO_PLAYBACK_BACKGROUND_16X9: ("Video Playback Background 16:9", "무대 · 깨끗한 배경, 중앙 타이틀 없음"),
        AT.STREAMING_COVER_1X1: ("Streaming Cover 1:1", "앨범 자켓 · Playlist 타이틀 유지"),
    }
    for atype, (label, desc) in checklist.items():
        fpath = exports_dir / ae.export_filename(sid, atype)
        check = "✅" if fpath.exists() else "⬜"
        st.markdown(f"{check} **{label}** — {desc}")

    # Preview exported assets
    manifest = ae.load_asset_manifest(sid)
    if manifest:
        st.divider()
        st.markdown("**🖼️ 내보낸 산출물 미리보기**")
        for a in manifest:
            fpath = a.get("path", "")
            if fpath and Path(fpath).exists():
                cols = st.columns([2, 1])
                with cols[0]:
                    st.image(fpath, use_container_width=True)
                with cols[1]:
                    st.caption(f"**타입:** {a['asset_type']}")
                    st.caption(f"**비율:** {a['aspect_ratio']}")
                    st.caption(f"**용도:** {', '.join(a['usage'])}")
                    flags = []
                    if a["contains_playlist_title"]: flags.append("Playlist 타이틀")
                    if a["contains_waveform"]: flags.append("파형")
                    if a["contains_cta_sticker"]: flags.append("CTA")
                    st.caption(f"**포함:** {', '.join(flags) if flags else '없음 (깨끗함)'}")

    # Video renderer hint
    st.divider()
    sel = select_video_background(sid)
    if sel["asset_type"]:
        if sel["is_clean_playback"]:
            st.success(f"🎬 Video Renderer 배경: **{sel['asset_type']}** (깨끗한 재생 배경 ✓)")
        else:
            st.warning(f"⚠️ {sel['warning']}")


def _rebuild_manifest(sid, ae, AT):
    """Rebuild the asset manifest from whatever exports currently exist on disk."""
    from services.thumbnail.session_store import session_path
    exports_dir = session_path(sid) / "exports"
    assets = []
    for atype in AT.REQUIRED_OUTPUT_TYPES:
        fpath = exports_dir / ae.export_filename(sid, atype)
        if fpath.exists():
            assets.append(ae._make_asset_entry(sid, atype, str(fpath)))
    return assets


