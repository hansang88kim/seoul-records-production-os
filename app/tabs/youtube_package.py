"""
app/tabs/youtube_package.py — YouTube Package Studio (v0.8.0).

Builds a YouTube upload package from final_video.mp4 + youtube_thumbnail_16x9
+ chapters.txt. Manual package first; API upload is optional and private by
default (mock client only in this version).

Does NOT modify music generation, Thumbnail Studio, or Video Renderer.
"""
from __future__ import annotations

from pathlib import Path
import streamlit as st

from services.youtube import asset_scanner as AS
from services.youtube import metadata_generator as MG
from services.youtube import thumbnail_validator as TV
from services.youtube import youtube_package_service as YPS
from services.youtube import youtube_api_client as YAC

# v1.0.0-alpha.97: upload MP3s → auto-build the timestamp tracklist (chapters).
_CHAP_AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg")


def _chap_upload_dir() -> Path:
    from services.video.playlist_builder import _outputs_root
    d = _outputs_root() / "youtube_chapter_uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _audio_duration(path: str) -> float:
    """Duration for any audio container (mutagen is format-generic)."""
    try:
        import mutagen
        f = mutagen.File(path)
        return float(getattr(getattr(f, "info", None), "length", 0) or 0)
    except Exception:
        return 0.0


def _scan_chapter_uploads() -> list[dict]:
    """Track dicts {path,name,duration_sec} for uploaded chapter audio."""
    d = _chap_upload_dir()
    out = []
    for f in sorted(d.iterdir()) if d.exists() else []:
        if f.suffix.lower() in _CHAP_AUDIO_EXTS:
            out.append({"path": str(f), "name": f.name,
                        "duration_sec": _audio_duration(str(f))})
    return out


def _render_mp3_chapter_builder():
    """v1.0.0-alpha.97: upload MP3/audio → compute cumulative timestamps and
    build a YouTube chapters.txt (the '⏱ Tracklist / MM:SS title / (반복 N)'
    format), reusing build_playlist_plan + format_chapters_txt. Returns a
    chapters-asset dict {path,name,parent} when one has been generated, else
    None (so the caller falls back to the auto-scanned chapters.txt)."""
    from services.video.playlist_builder import build_playlist_plan, format_chapters_txt

    from services.youtube.metadata_generator import _clean_track_title

    with st.expander("🎵 MP3 업로드 (→ 설명에 트랙리스트 자동 포함)", expanded=False):
        st.caption("음원을 올리면 각 곡 길이로 누적 타임스탬프를 계산해, 'YouTube 메타데이터 "
                   "생성' 시 설명·챕터에 트랙리스트로 자동 들어갑니다. 아래 ▲▼로 순서를 "
                   "조정하면 그 순서 그대로 반영됩니다. (지금 업로드한 파일만 사용됩니다.)")
        up = st.file_uploader(
            "음원 업로드 (mp3·wav·flac·m4a·aac·ogg · 여러 개)",
            type=[e.lstrip(".") for e in _CHAP_AUDIO_EXTS],
            accept_multiple_files=True, key="yt_chap_upload",
        )

        # v1.0.0-alpha.113: base everything ONLY on the files currently in the
        # uploader (not old files accumulated in the folder). Save them to disk
        # (needed to read durations), then work from this session's filenames.
        d = _chap_upload_dir()
        cur_names: list[str] = []
        for uf in (up or []):
            dest = d / uf.name
            if not dest.exists():
                dest.write_bytes(uf.getbuffer())
            cur_names.append(uf.name)

        if not cur_names:
            st.info("아직 업로드된 음원이 없습니다.")
            st.session_state.pop("yt_chap_track_order", None)
            return None

        # Maintain the user's manual order in session_state: keep known order,
        # append newly-added files, drop removed ones.
        order = [n for n in st.session_state.get("yt_chap_track_order", []) if n in cur_names]
        order += [n for n in cur_names if n not in order]
        st.session_state["yt_chap_track_order"] = order

        # ── Reorder list (▲▼) — replaces the old multiselect ────────────────
        st.markdown("**트랙 순서 (▲▼로 조정)**")
        for i, name in enumerate(order):
            ct, cu, cd = st.columns([6, 1, 1])
            with ct:
                st.markdown(f"<div style='padding-top:6px;font-size:0.86rem'>"
                            f"{i+1:02d}. {_clean_track_title(name)}</div>",
                            unsafe_allow_html=True)
            with cu:
                if st.button("▲", key=f"yt_chap_up_{name}", disabled=(i == 0),
                             use_container_width=True):
                    order[i-1], order[i] = order[i], order[i-1]
                    st.session_state["yt_chap_track_order"] = order
                    st.rerun()
            with cd:
                if st.button("▼", key=f"yt_chap_dn_{name}", disabled=(i == len(order)-1),
                             use_container_width=True):
                    order[i+1], order[i] = order[i], order[i+1]
                    st.session_state["yt_chap_track_order"] = order
                    st.rerun()

        chosen = [{"path": str(d / n), "name": n, "duration_sec": _audio_duration(str(d / n))}
                  for n in order]

        c1, c2 = st.columns(2)
        with c1:
            target = st.radio("목표 길이", [60, 65, 70], horizontal=True,
                              format_func=lambda m: f"{m}분", key="yt_chap_target")
        with c2:
            repeat = st.checkbox("목표 길이까지 반복 (반복분도 타임스탬프에 표시)",
                                value=True, key="yt_chap_repeat")

        # per-track durations that couldn't be read → warn (would break timing)
        missing = [t["name"] for t in chosen if not t.get("duration_sec", 0) > 0]
        if missing:
            st.warning("길이를 읽지 못한 파일이 있어 타임스탬프에서 제외됩니다: "
                       + ", ".join(missing[:5]) + ("…" if len(missing) > 5 else ""))

        # v1.0.0-alpha.99: no separate "타임스탬프 생성/미리보기" step — as soon as
        # audio is uploaded the tracklist is built and fed into 메타데이터 생성, where
        # it appears inside the SEO description (and the 챕터 section). The tracklist
        # is NOT shown standalone here (removed per request).
        plan = build_playlist_plan(chosen, target, repeat)
        path = _chap_upload_dir() / "uploaded_chapters.txt"
        path.write_text("⏱ Tracklist\n" + format_chapters_txt(plan), encoding="utf-8")
        tot = int(plan["total_seconds"])
        st.success(f"✅ {len(plan['chapters'])}곡 · {tot // 60}:{tot % 60:02d} — "
                   f"'YouTube 메타데이터 생성' 시 설명에 자동 포함됩니다.")
        return {"path": str(path), "name": "uploaded_chapters.txt (업로드 MP3)",
                "parent": "업로드"}


def render_youtube_package():
    """YouTube Package Studio entry point."""
    st.markdown("## ▶️ YouTube Package Studio")
    st.caption("final_video.mp4 + 썸네일 + 챕터로 YouTube 업로드 패키지를 생성합니다 "
               "(기본: 수동 패키지, API 업로드는 선택).")

    left, center, right = st.columns([1, 1.4, 1])

    # ─────────────────────────── LEFT: asset selection ──────────────
    with left:
        st.markdown("### 1️⃣ 자산 선택")

        videos = AS.scan_final_videos()
        thumbs = AS.scan_youtube_thumbnails()
        chapters_files = AS.scan_chapters()

        # v1.0.0-alpha.68: project filter — same multiselect pattern as
        # Video Renderer's "📁 프로젝트 폴더 선택". Narrows all three
        # dropdowns below to one (or more) project's own output, so e.g.
        # project A's video doesn't get paired with project B's thumbnail
        # by accident when several projects have rendered assets on disk.
        from app.project_manager import list_song_projects
        slug_to_name = {p["slug"]: p["name"] for p in list_song_projects()}
        all_assets = videos + thumbs + chapters_files
        available_slugs = sorted({
            AS.infer_project_slug(a["path"], a.get("name")) for a in all_assets
        } - {""})
        if available_slugs:
            sel_projects = st.multiselect(
                "📁 프로젝트 필터 (선택 시 그 프로젝트 산출물만 아래 드롭다운에 남음)",
                available_slugs, format_func=lambda s: slug_to_name.get(s, s),
                key="yt_pkg_sel_projects",
                help="비워두면 outputs/ 전체의 산출물을 보여줍니다.",
            )
            if sel_projects:
                videos = [v for v in videos
                          if AS.infer_project_slug(v["path"], v.get("name")) in sel_projects]
                thumbs = [t for t in thumbs
                          if AS.infer_project_slug(t["path"], t.get("name")) in sel_projects]
                chapters_files = [c for c in chapters_files
                                  if AS.infer_project_slug(c["path"], c.get("name")) in sel_projects]

        if videos:
            vlabels = [f"{v['name']} ({v['size_mb']}MB · {v['parent']})" for v in videos]
            vid_idx = st.selectbox("최종 영상", range(len(videos)),
                                   format_func=lambda i: vlabels[i], key="yt_vid")
            sel_video = videos[vid_idx]
        else:
            st.warning("final_video.mp4를 찾을 수 없습니다. Video Renderer에서 먼저 렌더하세요.")
            sel_video = None

        if thumbs:
            tlabels = [f"{t['name']} ({t['size_mb']}MB · {t['session']})" for t in thumbs]
            th_idx = st.selectbox("YouTube 썸네일", range(len(thumbs)),
                                  format_func=lambda i: tlabels[i], key="yt_thumb")
            sel_thumb = thumbs[th_idx]
        else:
            st.warning("youtube_thumbnail_16x9를 찾을 수 없습니다. Thumbnail Studio에서 내보내세요.")
            sel_thumb = None

        # v1.0.0-alpha.97: MP3 업로드로 타임스탬프 트랙리스트 자동 생성. 생성돼
        # 있으면 그 챕터를 우선 사용하고, 없으면 기존 자동 스캔 chapters.txt 사용.
        uploaded_chapters = _render_mp3_chapter_builder()
        if uploaded_chapters:
            sel_chapters = uploaded_chapters
            st.caption(f"챕터: {uploaded_chapters['name']} (업로드 MP3에서 생성됨)")
        elif chapters_files:
            clabels = [f"{c['name']} ({c['parent']})" for c in chapters_files]
            ch_idx = st.selectbox("챕터 파일", range(len(chapters_files)),
                                  format_func=lambda i: clabels[i], key="yt_chap")
            sel_chapters = chapters_files[ch_idx]
        else:
            st.info("chapters.txt가 없습니다 (선택). 위에서 MP3를 올려 자동 생성하거나, "
                    "없어도 패키지는 생성됩니다.")
            sel_chapters = None

        st.markdown("### 📤 업로드 모드")
        upload_mode_label = st.radio(
            "모드",
            ["수동 패키지만", "API 비공개 업로드 (기본)", "API 미등록(unlisted) 업로드"],
            index=1,  # v1.0.0-alpha.58: default to API private upload
            key="yt_mode",
            help="기본은 API 비공개 업로드입니다. API 업로드는 OAuth가 필요하며 "
                 "업로드는 항상 private로 진행됩니다. 로컬 패키지만 원하면 "
                 "'수동 패키지만'을 선택하세요.",
        )
        mode_map = {
            "수동 패키지만": YPS.UPLOAD_MODE_MANUAL,
            "API 비공개 업로드 (기본)": YPS.UPLOAD_MODE_API_PRIVATE,
            "API 미등록(unlisted) 업로드": YPS.UPLOAD_MODE_API_UNLISTED,
        }
        upload_mode = mode_map[upload_mode_label]
        if upload_mode != YPS.UPLOAD_MODE_MANUAL:
            st.caption(YAC.get_unverified_project_note())

        # Asset previews
        if sel_video:
            st.markdown("**영상 정보**")
            dur = int(sel_video.get("duration_sec", 0))
            st.caption(f"경로: {Path(sel_video['path']).name}")
            st.caption(f"길이: {dur//60}:{dur%60:02d} · 크기: {sel_video['size_mb']}MB")
        if sel_thumb and Path(sel_thumb["path"]).exists():
            st.image(sel_thumb["path"], caption="선택된 썸네일", use_container_width=True)

    # ─────────────────────────── CENTER: metadata ───────────────────
    with center:
        st.markdown("### 2️⃣ 메타데이터 생성")

        mcol1, mcol2 = st.columns(2)
        with mcol1:
            playlist_title = st.text_input("플레이리스트 제목 (선택)", key="yt_title_in",
                                           placeholder="비워두면 자동 생성")
            country = st.text_input("국가/도시 (선택)", value="Korea", key="yt_country")
        with mcol2:
            volume = st.number_input("Volume 번호", 1, 999, 1, key="yt_vol")
            duration_min = st.number_input("길이 (분)", 1, 600, 60, key="yt_dur")
        # v1.0.0-alpha.62: mood/theme is shared with the song + thumbnail.
        # v1.0.0-alpha.98: 🎲 dice suggests a city-pop mood; the SEO description
        # is written around this mood.
        from services import shared_mood as SM
        # staging-key pattern: the dice can't write yt_mood after the widget is
        # created, so it stages the suggestion and we apply it before rendering.
        if "yt_mood_pending" in st.session_state:
            st.session_state["yt_mood"] = st.session_state.pop("yt_mood_pending")
        _shared = SM.get_shared_mood(st.session_state)
        mcc1, mcc2 = st.columns([9, 1])
        with mcc1:
            mood = st.text_input("무드/테마 (곡·썸네일과 공유)", key="yt_mood",
                                 value=_shared,
                                 placeholder="예: 감성 터지는 청량한 여름밤",
                                 help="곡/썸네일에서 고른 무드가 자동으로 채워집니다. "
                                      "이 무드가 제목·설명·태그에 반영됩니다. 🎲로 제안받기.")
        with mcc2:
            if st.button("🎲", key="yt_mood_dice", use_container_width=True,
                         help="시티팝 무드를 하나 제안합니다."):
                from services.youtube.seo_description import suggest_mood
                st.session_state["yt_mood_pending"] = suggest_mood(
                    st.session_state.get("yt_mood", ""))
                st.rerun()
        if mood:
            SM.set_shared_mood(st.session_state, mood)

        # v1.0.0-alpha.60: song language → auto-translate the description
        # frame (tags stay English). Korean = no translation.
        lang_labels = {
            "korean": "한국어 (번역 안 함 · 기본)",
            "japanese": "日本語 (일본어로 번역)",
            "thai": "ไทย (태국어로 번역)",
            "vietnamese": "Tiếng Việt (베트남어로 번역)",
            "indonesian": "Bahasa Indonesia (인도네시아어로 번역)",
        }
        yt_language = st.selectbox(
            "곡 언어 / 설명 번역", list(lang_labels.keys()),
            format_func=lambda k: lang_labels[k], key="yt_language",
            help="곡이 외국어일 경우 설명 틀을 해당 언어로 자동 번역합니다 "
                 "(OpenAI/Gemini). 트랙리스트는 그대로 유지되고, 태그는 항상 "
                 "영어입니다. API 키가 없으면 한국어 원본이 유지됩니다.",
        )

        chapters_path = sel_chapters["path"] if sel_chapters else ""

        if st.button("🎯 YouTube 메타데이터 생성", type="primary", use_container_width=True):
            with st.spinner("메타데이터 생성 중… (외국어면 설명 번역에 시간이 걸릴 수 있습니다)"):
                meta = MG.generate_all_metadata(
                    playlist_title, country, int(volume), mood, chapters_path,
                    int(duration_min), language=yt_language)
            st.session_state["yt_meta"] = meta
            # v1.0.0-alpha.110: keep the sticky preview text_area in sync so a
            # re-generate (e.g. after reordering tracks) actually updates it.
            st.session_state["yt_desc_preview"] = meta["description"]
            if meta.get("description_translated"):
                st.success(f"✅ 설명을 {meta['description_language']}로 번역했습니다.")
            elif yt_language != "korean":
                st.warning("⚠️ 번역에 실패했거나 API 키가 없어 한국어 원본을 "
                           "사용합니다. Settings에서 OpenAI 또는 Gemini 키를 "
                           "확인하세요.")

        meta = st.session_state.get("yt_meta")
        if meta:
            st.markdown("**제목**")
            st.code(meta["title"], language=None)
            rc1, rc2, rc3 = st.columns(3)
            with rc1:
                if st.button("🔄 제목", use_container_width=True, key="yt_regen_title"):
                    # v1.0.0-alpha.98: SEO city-pop playlist title (DJ HANA removed).
                    from services.youtube.seo_description import generate_seo_title
                    meta["title"] = generate_seo_title(
                        country or "Korea", int(volume), mood,
                        len(meta.get("chapters", [])))
                    st.session_state["yt_meta"] = meta
                    st.rerun()
            with rc2:
                if st.button("🔄 설명", use_container_width=True, key="yt_regen_desc"):
                    # v1.0.0-alpha.98: regenerate the SEO description (LLM-written,
                    # mood-aware). Tracklist stays verbatim from the real uploaded
                    # audio (chapters); translated to the song language if non-Korean.
                    from services.youtube.seo_description import generate_seo_description
                    desc = generate_seo_description(meta.get("chapters", []),
                                                    mood=mood, country=country or "Korea",
                                                    volume=int(volume))
                    lang = st.session_state.get("yt_language", "korean")
                    from services.youtube.description_translator import (
                        translate_description, needs_translation)
                    if needs_translation(lang):
                        with st.spinner("설명 번역 중…"):
                            res = translate_description(desc, lang)
                        desc = res["description"]
                        meta["description_translated"] = res["translated"]
                        meta["description_language"] = res["language"]
                    meta["description"] = desc
                    st.session_state["yt_meta"] = meta
                    # v1.0.0-alpha.110: the preview text_area has a key, so it is
                    # sticky — sync it or it keeps showing the OLD description.
                    st.session_state["yt_desc_preview"] = desc
                    st.rerun()
            with rc3:
                if st.button("🔄 태그", use_container_width=True, key="yt_regen_tags"):
                    meta["tags"] = MG.generate_tags(country, mood, int(volume))
                    st.session_state["yt_meta"] = meta
                    st.rerun()

            st.markdown("**설명 미리보기**")
            st.session_state.setdefault("yt_desc_preview", meta["description"])
            st.text_area("description", height=240,
                         key="yt_desc_preview", label_visibility="collapsed")

            st.markdown("**태그 / 해시태그**")
            st.caption(", ".join(meta["tags"]))
            st.caption(" ".join(meta["hashtags"]))

            if meta.get("chapters_section"):
                st.markdown("**챕터**")
                st.code(meta["chapters_section"], language=None)

            st.markdown("**고정 댓글**")
            st.code(meta["pinned_comment"], language=None)

    # ─────────────────────────── RIGHT: validation + export ─────────
    with right:
        st.markdown("### 3️⃣ 검증 & 내보내기")

        # Thumbnail validation preview
        if sel_thumb and st.button("🔍 썸네일 검증", use_container_width=True, key="yt_validate"):
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                vr = TV.validate_thumbnail(sel_thumb["path"], td)
            st.session_state["yt_thumb_val"] = {
                "status": vr["status"], "message": vr["message"],
                "width": vr["width"], "height": vr["height"],
                "size_mb": vr["original_size_mb"], "aspect_ok": vr["aspect_ok"],
            }

        tv = st.session_state.get("yt_thumb_val")
        if tv:
            icon = {"ready": "✅", "too_large_compressed": "🗜️",
                    "wrong_aspect_ratio": "⚠️", "missing": "❌",
                    "bad_format": "❌"}.get(tv["status"], "•")
            st.markdown(f"{icon} **{tv['message']}**")
            st.caption(f"{tv['width']}x{tv['height']} · {tv['size_mb']}MB · "
                       f"16:9 {'OK' if tv['aspect_ok'] else '아님'}")

        st.divider()

        # Create package
        can_create = sel_video is not None and sel_thumb is not None
        if st.button("📦 업로드 패키지 생성", type="primary",
                     use_container_width=True, disabled=not can_create):
            meta = st.session_state.get("yt_meta")
            manifest = YPS.create_package(
                sel_video["path"], sel_thumb["path"], chapters_path,
                playlist_title=playlist_title, country=country, volume=int(volume),
                mood=mood, duration_min=int(duration_min), upload_mode=upload_mode,
                metadata_override=meta,
            )
            st.session_state["yt_package"] = manifest
            st.success(f"✅ 패키지 생성됨: {manifest['package_id']}")

        pkg = st.session_state.get("yt_package")
        if pkg:
            st.caption(f"상태: {pkg['status']} · 썸네일: {pkg.get('thumbnail_status')}")
            if pkg.get("warnings"):
                for w in pkg["warnings"]:
                    st.caption(f"⚠️ {w}")

            ecol1, ecol2 = st.columns(2)
            with ecol1:
                if st.button("🗜️ 수동 패키지 ZIP", use_container_width=True, key="yt_zip"):
                    zip_path = YPS.build_manual_package_zip(pkg["package_dir"])
                    if zip_path:
                        st.session_state["yt_zip_path"] = zip_path
                        st.success("ZIP 생성 완료")
            with ecol2:
                if st.button("📂 폴더 열기", use_container_width=True, key="yt_open"):
                    import subprocess, platform
                    folder = pkg["package_dir"]
                    try:
                        if platform.system() == "Windows":
                            subprocess.Popen(["explorer", folder])
                        elif platform.system() == "Darwin":
                            subprocess.Popen(["open", folder])
                        else:
                            subprocess.Popen(["xdg-open", folder])
                    except Exception:
                        st.caption(folder)

            # Optional API upload (mock client; private default)
            if upload_mode in (YPS.UPLOAD_MODE_API_PRIVATE, YPS.UPLOAD_MODE_API_UNLISTED):
                privacy = ("private" if upload_mode == YPS.UPLOAD_MODE_API_PRIVATE
                           else "unlisted")
                _render_oauth_and_upload(pkg, privacy)

        # Upload checklist (always shown for the package)
        if pkg:
            st.divider()
            st.markdown("**업로드 체크리스트**")
            checklist = Path(pkg["package_dir"]) / "upload_checklist.md"
            if checklist.exists():
                st.markdown(checklist.read_text(encoding="utf-8"))

    # Live upload progress (background jobs) — outside the columns
    _render_upload_progress_panel()


def _render_studio_manual_checklist(state: dict):
    """
    v1.0.0-alpha.59: After a successful upload, show the settings that the
    YouTube Data API CANNOT set and therefore must be done by hand in
    YouTube Studio. This is not a limitation of this app — YouTube simply
    does not expose these via the API: monetization on/off, the
    "video content self-rating" (ad-suitability) submission, the AI/altered-
    content disclosure, end screens, and cards. Surfacing them as a fixed
    checklist (with a one-click Studio link) means the user never has to
    remember what to configure after each upload.
    """
    import streamlit as st
    from services.youtube.metadata_generator import STUDIO_MANUAL_STEPS

    vid = state.get("video_id", "")
    with st.expander("📋 YouTube Studio에서 직접 설정할 항목 (API 자동화 불가)", expanded=True):
        st.caption("아래 항목은 YouTube가 API로 열어주지 않아 자동 설정이 "
                   "불가능합니다. 업로드된 영상을 Studio에서 열어 직접 설정하세요.")
        for step in STUDIO_MANUAL_STEPS:
            st.markdown(f"- {step}")
        if vid:
            st.markdown(f"[🎬 이 영상을 YouTube Studio에서 열기]"
                       f"(https://studio.youtube.com/video/{vid}/edit)")
            st.markdown(f"[💰 수익 창출 설정 열기]"
                       f"(https://studio.youtube.com/video/{vid}/monetization)")


def _render_oauth_and_upload(pkg: dict, privacy: str):
    """OAuth account section + checklist-gated background Private Upload."""
    from services.youtube import dependency_check as DEP

    st.divider()
    st.markdown("### 🔐 OAuth / 계정")
    st.warning("YouTube API 업로드는 기본적으로 private로 진행됩니다. "
               "공개 전 YouTube Studio에서 직접 확인하세요.")
    st.caption("client_secret.json 및 인증 토큰은 Settings 페이지와 상태를 공유합니다 — "
               "한 번 등록하면 여기서도 다시 업로드할 필요가 없습니다.")

    from app.ui.youtube_oauth_panel import render_oauth_account_panel
    status = render_oauth_account_panel(key_ns="yt_pkg")
    libs_ok = DEP.check_youtube_api_dependencies()["available"]

    # Checklist gate
    st.divider()
    st.markdown("### ✅ 업로드 전 확인")
    video_ok = bool(pkg.get("video_path") and Path(pkg["video_path"]).exists())
    title_ok = bool(pkg.get("title"))
    thumb_ok = bool(pkg.get("thumbnail_upload_ready_path")
                    and Path(pkg["thumbnail_upload_ready_path"]).exists())
    st.caption(f"{'✅' if video_ok else '❌'} final_video.mp4 존재")
    st.caption(f"{'✅' if title_ok else '❌'} 제목 생성됨")
    st.caption(f"{'✅' if thumb_ok else '⚠️'} 업로드용 썸네일 존재")
    st.caption("✅ 기본 공개 상태: private")

    reviewed = st.checkbox(
        "이 패키지를 검토했고, 영상이 비공개(private)로 업로드됨을 이해하며, "
        "저작권/권리 책임을 확인합니다.",
        key="yt_reviewed",
    )

    use_real = st.checkbox(
        "실제 YouTube API 사용 (미체크 시 mock)", value=False,
        key="yt_use_real", disabled=not libs_ok,
        help="실제 업로드는 OAuth 인증과 google-api-python-client가 필요합니다.",
    )
    if not libs_ok and use_real:
        # Defensive: if somehow checked, force mock
        use_real = False
    if not libs_ok:
        st.caption("⚠️ Google API 라이브러리가 없어 실제 업로드는 비활성화됩니다. "
                   "mock 업로드는 계속 사용할 수 있습니다.")

    # Real upload additionally requires the libraries to be installed
    can_upload = video_ok and title_ok and reviewed and (libs_ok or not use_real)

    if st.button(f"▶️ YouTube 업로드 ({privacy})", key="yt_upload",
                 use_container_width=True, type="primary", disabled=not can_upload):
        from services.youtube.upload_payload_service import build_upload_payload
        from services.youtube.upload_job_store import launch_upload_job
        payload = build_upload_payload(pkg.get("title", ""),
                                       _read_text(pkg, "description.txt"),
                                       pkg.get("tags", []), privacy_status=privacy)
        job = launch_upload_job(
            package_id=pkg.get("package_id", ""),
            video_path=pkg.get("video_path", ""),
            thumbnail_path=pkg.get("thumbnail_upload_ready_path", ""),
            title=pkg.get("title", ""), payload=payload,
            privacy_status=privacy, use_real=use_real,
        )
        st.session_state["yt_active_upload"] = job["upload_job_id"]
        st.success(f"📤 백그라운드 업로드 시작! (Job: {job['upload_job_id']})")
        st.info("UI는 멈추지 않습니다. 아래 '업로드 진행 상황'에서 확인하세요.")
        st.rerun()

    if not can_upload:
        st.caption("⚠️ 업로드 버튼은 체크리스트를 검토(reviewed)해야 활성화됩니다.")


def _read_text(pkg: dict, filename: str) -> str:
    try:
        p = Path(pkg["package_dir"]) / filename
        return p.read_text(encoding="utf-8") if p.exists() else ""
    except Exception:
        return ""


def _render_upload_progress_panel():
    """Live progress for the active/most-recent background upload job."""
    from services.youtube.upload_job_store import (
        load_upload_state, list_upload_jobs, get_upload_log,
    )
    job_id = st.session_state.get("yt_active_upload")
    state = load_upload_state(job_id) if job_id else None
    if not state:
        active = [j for j in list_upload_jobs(20)
                  if j.get("status") in ("queued", "authorizing", "uploading",
                                          "processing", "thumbnail_setting")]
        state = active[0] if active else None
    if not state:
        return

    st.divider()
    st.markdown("### 📤 업로드 진행 상황")
    status = state.get("status", "")
    pct = state.get("progress_percent", 0) or 0
    jid = state["upload_job_id"]

    if status in ("queued", "authorizing", "uploading", "processing", "thumbnail_setting"):
        st.progress(pct / 100)
        st.caption(f"상태: {status} · {pct:.0f}% · {state.get('last_message','')}")
        if st.button("🔄 새로고침", key="yt_refresh_upload"):
            st.rerun()
    elif status == "completed":
        st.success(f"✅ 업로드 완료 (private): {state.get('youtube_url','')}")
        ch = state.get("channel_title", "")
        ch_line = f" · 채널: **{ch}**" if ch else ""
        st.caption(f"video_id: {state.get('video_id')} · 썸네일: {state.get('thumbnail_set_status')}{ch_line}")
        if ch:
            st.info(f"이 영상은 **{ch}** 채널에 업로드되었습니다. "
                    "의도한 채널이 맞는지 확인하세요. (다른 채널로 올리려면 "
                    "'토큰 삭제' 후 재인증 시 채널 선택 화면에서 원하는 채널을 "
                    "고르세요.)")
        _render_studio_manual_checklist(state)
    elif status == "partial_success":
        thumb_err = state.get("thumbnail_error", "")
        ch = state.get("channel_title", "")
        ch_line = f"\n\n**채널:** {ch}" if ch else ""
        st.warning(f"⚠️ 업로드됨(private) · 썸네일 실패: {state.get('youtube_url','')}"
                   + ch_line
                   + (f"\n\n**사유:** {thumb_err}" if thumb_err else ""))
        vid = state.get("video_id", "")
        if vid:
            st.markdown(f"[🎬 YouTube Studio에서 이 영상 편집하기 (썸네일 수동 설정)]"
                       f"(https://studio.youtube.com/video/{vid}/edit)")
        if st.button("🖼️ 썸네일만 재시도", key="yt_retry_thumb"):
            from workers.youtube_upload_worker import run_thumbnail_retry
            run_thumbnail_retry(jid, use_mock=not st.session_state.get("yt_use_real", False))
            st.rerun()
        _render_studio_manual_checklist(state)
    elif status == "failed":
        st.error(f"❌ 업로드 실패: {state.get('last_message','')}")
        if st.button("🔁 업로드 재시도", key="yt_retry_upload"):
            st.session_state["yt_active_upload"] = None
            st.rerun()

    # Sanitized logs (last 20)
    log = get_upload_log(jid, last_n=20)
    if log:
        with st.expander("📄 업로드 로그 (최근 20, 토큰 제거됨)", expanded=False):
            st.code("\n".join(f"[{l.get('level','info')}] {l.get('message','')}" for l in log))


def _mock_upload(pkg: dict, privacy: str):
    """Run a MOCK upload (no real network). Private/unlisted only."""
    from services.youtube.upload_payload_service import build_upload_payload
    from services.youtube.youtube_api_client import (
        MockYouTubeClient, save_upload_result,
    )

    title = pkg.get("title", "")
    payload = build_upload_payload(title, "", pkg.get("tags", []), privacy_status=privacy)
    client = MockYouTubeClient(credentials={})  # no real token
    result = client.upload_video(pkg.get("video_path", ""), payload, privacy_status=privacy)
    # Thumbnail after video_id
    if pkg.get("thumbnail_upload_ready_path"):
        client.set_thumbnail(result["video_id"], pkg["thumbnail_upload_ready_path"])
    save_upload_result(pkg["package_dir"], result)
    st.success(f"✅ (Mock) 업로드 완료: {result['url']} · {result['privacy_status']}")
    st.caption("실제 업로드가 아닙니다 — v0.8.1에서 실제 OAuth 업로드가 추가됩니다.")
