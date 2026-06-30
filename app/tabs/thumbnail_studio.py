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
from services.thumbnail.prompt_generator import generate_prompt_batch
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
        ["🎨 Prompt Lab", "🖼️ Candidate Gallery", "✨ Brand Thumbnail", "📦 Exports"],
        horizontal=True, label_visibility="collapsed",
    )

    st.divider()

    if mode.startswith("🎨"):
        _render_prompt_lab()
    elif mode.startswith("🖼️"):
        _render_candidate_gallery()
    elif mode.startswith("✨"):
        _render_brand_thumbnail()
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
        theme = st.text_input("테마/무드", value="rainy night drive", key="thumb_theme")
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
        dep = igd.check_image_gen_dependencies()
        use_real = st.toggle(
            "실제 이미지 생성 (Gemini · Nano Banana)",
            value=dep["ready"],
            disabled=not dep["ready"],
            key="thumb_use_real",
            help=("실제 이미지를 Gemini API로 생성합니다 (REST · 추가 설치 불필요)."
                  if dep["ready"]
                  else f"준비 안 됨 → {dep['key_hint']}"),
        )
        if not dep["ready"]:
            st.caption(
                "⚠️ 실제 생성 비활성 → 목업으로 진행. "
                "좌측 사이드바 🤖 AI Composer → Gemini 칸에 API 키를 입력하면 켜집니다."
            )
        elif use_real:
            st.caption(f"🟢 실제 생성 ON · 모델 {dep['model']} ({dep['backend'].upper()})")

    # Optional: explicit new-session button
    col_gen, col_new = st.columns([3, 1])
    with col_new:
        force_new = st.button("🆕 새 세션", use_container_width=True,
                              help="새 썸네일 세션을 시작합니다 (기존 세션 자산은 보존됨)")
    with col_gen:
        do_generate = st.button(f"🎨 {count}개 이미지 생성", type="primary",
                                use_container_width=True)

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

        prompts = generate_prompt_batch(country_key, theme, count)
        mode_label = "실제 (Gemini)" if use_real else "목업"
        with st.spinner(f"{count}장 이미지 생성 중… ({mode_label})"):
            cands = ss.generate_images(sid, prompts, use_real=use_real)
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
                st.caption("ℹ️ 목업(placeholder) 이미지입니다. 실제 생성: 좌측 사이드바 🤖 AI Composer → "
                           "Gemini 칸에 API 키 입력 → 위의 '실제 이미지 생성' 토글 ON (추가 설치 불필요).")
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
    """Mode 2 — upload Flow images and manage candidates."""
    st.markdown("#### 🖼️ Candidate Gallery — Flow 이미지 업로드 & 선택")

    sess = _current_session()
    if not sess:
        st.info("먼저 Prompt Lab에서 프롬프트를 생성하세요.")
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
                if rating != cand.get("rating"):
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

    # Brand settings
    # Fixed top/bottom lines (not editable); only the city name + local line below
    # are auto-suggested per country and editable (themes may change — 이별 노래 etc.).
    BRAND_TEXT = "Seoul Records"      # top eyebrow (fixed)
    BOTTOM_LINE = "CityPop Playlist"  # bottom line (fixed)
    col1, col2 = st.columns(2)
    with col1:
        country_label = get_country_preset(sess["country"])["label"].split(" (")[0]
        _defs = get_title_defaults(sess["country"])
        if st.session_state.get("_brand_country") != sess["country"]:
            st.session_state["brand_title"] = _defs["city"]
            st.session_state["brand_cjk"] = _defs["night_local"]
            st.session_state["_brand_country"] = sess["country"]
        title = st.text_input("도시/국가명 (가장 크게)", key="brand_title",
                              help="국가별 자동 제안 · 자유롭게 수정 가능 (테마에 맞게).")
        cjk_subtext = st.text_input("현지어 줄 (밤의 음악 등)", key="brand_cjk",
                                    help="해당 국가 언어로 자동 제안 · 수정 가능 (예: 이별, 드라이브 등).")
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

    # Title color + size
    tc1, tc2 = st.columns([1, 2])
    with tc1:
        title_color = st.color_picker("제목 색상", value="#FFFFFF", key="brand_title_color")
    with tc2:
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

    source_options = {}
    for b in branded_imgs:
        source_options[f"브랜드 썸네일: {b.name}"] = str(b)
    for cand in selected:
        p = cand.get("uploaded_image_path")
        if p:
            source_options[f"선택 이미지: {cand['candidate_id']}"] = p

    if not source_options:
        st.warning("⚠️ 먼저 Candidate Gallery에서 이미지를 선택하거나 Brand Thumbnail을 만드세요.")
        return

    src_label = st.selectbox("소스 배경 이미지", list(source_options.keys()))
    bg_path = source_options[src_label]

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

    ec1, ec2 = st.columns([1, 2])
    with ec1:
        exp_title_color = st.color_picker("제목 색상", value="#FFFFFF", key="exp_title_color")
    with ec2:
        exp_title_scale = st.slider("제목 크기", 0.80, 1.60, 1.10, 0.05,
                                    key="exp_title_scale",
                                    help="1.0 = 기본 · 값이 클수록 제목이 커집니다.")

    st.divider()

    # Export buttons
    bcol1, bcol2, bcol3, bcol4 = st.columns(4)
    with bcol1:
        if st.button("🖼️ YouTube 썸네일", use_container_width=True):
            p = ae.export_youtube_thumbnail(sid, bg_path, title, subtitle, brand_text,
                                            accent, exp_title_color, exp_title_scale, exp_cjk)
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
            yt = ss.session_path(sid) / "exports" / AT.EXPORT_FILENAMES[AT.YOUTUBE_THUMBNAIL_16X9]
            p = ae.export_streaming_cover(sid, str(yt), bg_path, title, subtitle,
                                          brand_text, accent, crop_mode,
                                          exp_title_color, exp_title_scale, exp_cjk)
            if p:
                ae.write_asset_manifest(sid, _rebuild_manifest(sid, ae, AT))
                st.success("✅ 스트리밍 커버 1:1")
    with bcol4:
        if st.button("📦 전체 내보내기", type="primary", use_container_width=True):
            results = ae.export_all_required_assets(sid, bg_path, title, subtitle,
                                                    brand_text, accent, crop_mode,
                                                    exp_title_color, exp_title_scale, exp_cjk)
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
        fpath = exports_dir / AT.EXPORT_FILENAMES[atype]
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
        fpath = exports_dir / AT.EXPORT_FILENAMES[atype]
        if fpath.exists():
            assets.append(ae._make_asset_entry(sid, atype, str(fpath)))
    return assets


