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

from services.thumbnail.country_presets import list_countries, get_country_preset
from services.thumbnail.prompt_generator import generate_prompt_batch
from services.thumbnail import session_store as ss
from services.thumbnail import canva_branding as cb


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
        volume = st.number_input("Volume 번호", min_value=1, value=1, step=1, key="thumb_vol")

    col4, col5 = st.columns(2)
    with col4:
        title = st.text_input("플레이리스트 제목 (Canva가 입힐 텍스트)",
                              value=f"CityPop Playlist Vol.{volume}", key="thumb_title")
    with col5:
        subtitle = st.text_input("부제목 (선택)", value="1990s Night Drive", key="thumb_subtitle")

    batch = st.radio("배치 수", [1, 5, 10], horizontal=True, key="thumb_batch")

    if st.button(f"🎨 {batch}개 프롬프트 생성", type="primary", use_container_width=True):
        # Create or reuse session
        sid = st.session_state.get("thumb_session_id")
        if not sid:
            sess = ss.create_session(country_key, theme, title, volume, subtitle)
            sid = sess["session_id"]
            st.session_state["thumb_session_id"] = sid

        prompts = generate_prompt_batch(country_key, theme, batch)
        ss.save_prompts(sid, prompts)
        st.session_state["thumb_prompts"] = prompts
        st.success(f"✅ {batch}개 프롬프트 생성 완료! 아래에서 복사해 Google Flow에 붙여넣으세요.")

    # Show generated prompts
    prompts = st.session_state.get("thumb_prompts", [])
    if prompts:
        st.divider()
        st.markdown(f"**생성된 프롬프트 ({len(prompts)}개)**")
        st.caption("각 프롬프트를 복사해 Google Flow / Nano Banana에 붙여넣고 이미지를 생성하세요. "
                   "이미지에는 텍스트/로고가 없습니다 (제목은 Canva가 입힙니다).")

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
    col1, col2 = st.columns(2)
    with col1:
        country_label = get_country_preset(sess["country"])["label"].split(" (")[0]
        title = st.text_input("메인 제목",
                              value=cb.build_main_title(country_label, sess["volume"], sess.get("title", "")),
                              key="brand_title")
        subtitle = st.text_input("부제목", value=sess.get("subtitle", ""), key="brand_subtitle")
    with col2:
        brand_text = st.text_input("브랜드 텍스트", value="Seoul Records", key="brand_text")
        canva_mode = st.selectbox("Canva 모드",
                                  ["Mock Canva (로컬 테스트)", "Canva Manual (수동)", "Canva Autofill"],
                                  key="canva_mode")

    if st.button("✨ 선택 이미지로 브랜드 썸네일 만들기", type="primary", use_container_width=True):
        results = []
        for cand in selected:
            # Generate payload
            payload = cb.generate_canva_payload(
                sess["session_id"], cand, title, subtitle, brand_text,
                sess["volume"], sess["country"], sess["theme"],
            )
            cb.save_canva_payload(sess["session_id"], cand["candidate_id"], payload)

            if canva_mode.startswith("Mock"):
                branded = cb.mock_render_branded_thumbnail(
                    sess["session_id"], cand, title, subtitle, brand_text,
                    cand.get("canva_accent_color", "#ff4d6d"),
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
    """Mode 4 — view final exports."""
    st.markdown("#### 📦 Exports — 최종 썸네일")

    sess = _current_session()
    if not sess:
        st.info("아직 세션이 없습니다.")
        return

    exports_dir = ss.session_path(sess["session_id"]) / "exports"
    if not exports_dir.exists():
        st.info("아직 내보낸 썸네일이 없습니다.")
        return

    finals = sorted(exports_dir.glob("final_thumbnail_*.png"))
    branded_dir = ss.session_path(sess["session_id"]) / "branded"
    branded = sorted(branded_dir.glob("branded_thumbnail_*.png")) if branded_dir.exists() else []

    if not finals and not branded:
        st.info("아직 썸네일이 없습니다. Brand Thumbnail에서 생성하세요.")
        return

    if finals:
        st.markdown(f"**📦 최종 내보내기 ({len(finals)}개)**")
        cols = st.columns(2)
        for idx, f in enumerate(finals):
            with cols[idx % 2]:
                st.image(str(f), use_container_width=True, caption=f.name)

    if branded:
        st.markdown(f"**✨ 브랜드 썸네일 ({len(branded)}개)**")
        cols = st.columns(2)
        for idx, f in enumerate(branded):
            with cols[idx % 2]:
                st.image(str(f), use_container_width=True, caption=f.name)

    # Session info
    st.divider()
    if st.button("📂 세션 폴더 열기"):
        import subprocess, platform
        folder = str(ss.session_path(sess["session_id"]))
        if platform.system() == "Windows":
            subprocess.Popen(["explorer", folder])
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
