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
        if videos:
            vlabels = [f"{v['name']} ({v['size_mb']}MB · {v['parent']})" for v in videos]
            vid_idx = st.selectbox("최종 영상", range(len(videos)),
                                   format_func=lambda i: vlabels[i], key="yt_vid")
            sel_video = videos[vid_idx]
        else:
            st.warning("final_video.mp4를 찾을 수 없습니다. Video Renderer에서 먼저 렌더하세요.")
            sel_video = None

        thumbs = AS.scan_youtube_thumbnails()
        if thumbs:
            tlabels = [f"{t['name']} ({t['size_mb']}MB · {t['session']})" for t in thumbs]
            th_idx = st.selectbox("YouTube 썸네일", range(len(thumbs)),
                                  format_func=lambda i: tlabels[i], key="yt_thumb")
            sel_thumb = thumbs[th_idx]
        else:
            st.warning("youtube_thumbnail_16x9를 찾을 수 없습니다. Thumbnail Studio에서 내보내세요.")
            sel_thumb = None

        chapters_files = AS.scan_chapters()
        if chapters_files:
            clabels = [f"{c['name']} ({c['parent']})" for c in chapters_files]
            ch_idx = st.selectbox("챕터 파일", range(len(chapters_files)),
                                  format_func=lambda i: clabels[i], key="yt_chap")
            sel_chapters = chapters_files[ch_idx]
        else:
            st.info("chapters.txt가 없습니다 (선택). 없어도 패키지는 생성됩니다.")
            sel_chapters = None

        st.markdown("### 📤 업로드 모드")
        upload_mode_label = st.radio(
            "모드",
            ["수동 패키지만 (기본)", "API 비공개 업로드", "API 미등록(unlisted) 업로드"],
            key="yt_mode",
            help="기본은 수동 패키지입니다. API 업로드는 OAuth가 필요하며 기본 비공개입니다.",
        )
        mode_map = {
            "수동 패키지만 (기본)": YPS.UPLOAD_MODE_MANUAL,
            "API 비공개 업로드": YPS.UPLOAD_MODE_API_PRIVATE,
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
        mood = st.text_input("무드/테마 (선택)", key="yt_mood",
                             placeholder="예: Rainy Night Drive")

        chapters_path = sel_chapters["path"] if sel_chapters else ""

        if st.button("🎯 YouTube 메타데이터 생성", type="primary", use_container_width=True):
            meta = MG.generate_all_metadata(
                playlist_title, country, int(volume), mood, chapters_path, int(duration_min))
            st.session_state["yt_meta"] = meta

        meta = st.session_state.get("yt_meta")
        if meta:
            st.markdown("**제목**")
            st.code(meta["title"], language=None)
            rc1, rc2, rc3 = st.columns(3)
            with rc1:
                if st.button("🔄 제목", use_container_width=True, key="yt_regen_title"):
                    meta["title"] = MG.generate_title(playlist_title, country, int(volume),
                                                      int(duration_min), mood)
                    st.session_state["yt_meta"] = meta
                    st.rerun()
            with rc2:
                if st.button("🔄 설명", use_container_width=True, key="yt_regen_desc"):
                    meta["description"] = MG.generate_description(
                        playlist_title, country, int(volume), mood,
                        meta.get("chapters", []), int(duration_min))
                    st.session_state["yt_meta"] = meta
                    st.rerun()
            with rc3:
                if st.button("🔄 태그", use_container_width=True, key="yt_regen_tags"):
                    meta["tags"] = MG.generate_tags(country, mood, int(volume))
                    st.session_state["yt_meta"] = meta
                    st.rerun()

            st.markdown("**설명 미리보기**")
            st.text_area("description", meta["description"], height=240,
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
                st.divider()
                privacy = ("private" if upload_mode == YPS.UPLOAD_MODE_API_PRIVATE
                           else "unlisted")
                st.caption(f"⚠️ API 업로드는 기본 {privacy}입니다. (현재 버전은 mock 클라이언트)")
                if st.button(f"▶️ YouTube 업로드 ({privacy})", use_container_width=True,
                             key="yt_upload"):
                    _mock_upload(pkg, privacy)

        # Upload checklist
        if pkg:
            st.divider()
            st.markdown("**업로드 체크리스트**")
            checklist = Path(pkg["package_dir"]) / "upload_checklist.md"
            if checklist.exists():
                st.markdown(checklist.read_text(encoding="utf-8"))


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
