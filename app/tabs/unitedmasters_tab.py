"""
app/tabs/unitedmasters_tab.py — UnitedMasters Distribution Package Studio (v0.9.0).

Builds a manual-upload distribution package from the Video Renderer playlist
order + streaming cover. MP3 = source/draft audio (distribution_ready=False);
WAV/FLAC masters flip a track to distribution-ready. No fake WAV, no credential
storage, no CAPTCHA bypass — manual upload workflow only.
"""
from __future__ import annotations

import json
from pathlib import Path
import streamlit as st

from services.unitedmasters import source_scanner as SRC
from services.unitedmasters import track_builder as TB
from services.unitedmasters import cover_validator as CV
from services.unitedmasters import package_service as PS


def render_unitedmasters():
    st.markdown("## 🎶 UnitedMasters")
    st.caption("확정한 재생 순서, 곡별 원본 WAV/FLAC, 승인한 커버로 웹 등록 패키지를 만듭니다.")
    with st.expander("웹 등록 작업지시서"):
        st.markdown(PS.UPLOAD_GUIDE.read_text(encoding="utf-8"))

    # ── Top: source selection ────────────────────────────────────────
    tcol1, tcol2 = st.columns(2)
    with tcol1:
        plans = SRC.find_playlist_plans()
        if not plans:
            st.warning("⚠️ Video Renderer의 playlist_plan.json을 찾을 수 없습니다. "
                       "먼저 Video Renderer에서 플레이리스트를 만드세요.")
            return
        plan_path = st.selectbox(
            "Video Renderer 플레이리스트", [p["path"] for p in plans], key="um_plan",
            format_func=lambda path: " / ".join(Path(path).parts[-3:-1]),
        )
        playlist_plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    with tcol2:
        covers = SRC.find_streaming_covers()
        cover_path = st.selectbox("Streaming Cover 1:1", [*covers, ""],
                                  format_func=lambda c: Path(c).name if c else "선택 안 함", key="um_cover")
        custom_cover = st.text_input(
            "승인한 커버 또는 가로 JPG/PNG 경로", key="um_custom_cover",
            help="가로 원본은 전체 프레임을 유지해 3000×3000 JPG로 준비합니다.",
        ).strip()
        cover_path = custom_cover or cover_path

    masters = st.session_state.get("um_masters", {})
    titles = st.session_state.get("um_titles", {})
    tracks = TB.build_tracklist(playlist_plan, masters, titles)

    st.divider()
    left, center, right = st.columns([1, 2, 1])

    # ── LEFT: release metadata form ──────────────────────────────────
    with left:
        st.markdown("### 📝 릴리스 메타데이터")
        artist = st.text_input("아티스트", "Seoul Records", key="um_artist")
        title = st.text_input("릴리스 제목", "Korea CityPop Playlist Vol.1", key="um_title")
        genre = st.text_input("주 장르", "City Pop", key="um_genre")
        language = st.text_input("언어", "Korean", key="um_lang")
        label = st.text_input("레이블 (선택)", key="um_label")
        release_type = st.selectbox("발매 유형", ["New Release", "Re-Release"], key="um_type")
        upc = st.text_input("UPC/EAN (선택)", key="um_upc")
        cyear = st.number_input("저작권 연도", 2000, 2100, 2026, key="um_cyear")
        rdate = st.text_input("희망 발매일 (YYYY-MM-DD)", "", key="um_rdate")
        explicit = st.checkbox("Explicit 콘텐츠", value=False, key="um_explicit")

    # ── CENTER: track table ──────────────────────────────────────────
    with center:
        st.markdown("### 🎵 트랙 (YouTube 렌더 순서)")
        synced = TB.order_matches_playlist(tracks, playlist_plan)
        if synced:
            st.success("✅ 트랙 순서가 Video Renderer 플레이리스트와 일치합니다.")
        else:
            st.warning("⚠️ UnitedMasters 트랙 순서가 Video Renderer 플레이리스트와 다릅니다.")
            if st.button("🔄 Video Renderer 순서로 동기화", key="um_sync"):
                st.session_state.pop("um_masters", None)
                st.session_state.pop("um_titles", None)
                st.rerun()

        for t in tracks:
            val = TB.validate_audio(t)
            badge = {"Distribution Ready": "✅", "MP3-only Warning": "⚠️",
                     "Missing WAV/FLAC": "❌"}.get(val["status"], "•")
            st.write(f"**{t['track_no']}. {t['title']}** — "
                     f"{int(t['duration_sec'])//60}:{int(t['duration_sec'])%60:02d} · {badge} {val['status']}")
            if t["master_path"]:
                audio = t["master_audio"]
                st.caption(f"원본 · {Path(t['master_path']).name} · "
                           f"{audio['sample_rate'] / 1000:g} kHz · {audio['bit_depth']}-bit")
            else:
                st.caption(val["warning"])

        with st.expander("곡 제목 및 원본 경로 편집"):
            new_masters = dict(masters)
            new_titles = dict(titles)
            with st.form(key=f"um_tracks_{plan_path}"):
                for t in tracks:
                    source = t["source_path"]
                    number = t["track_no"]
                    display_title = st.text_input(f"{number}. 표시 제목", value=t["title"],
                                                  key=f"um_title_{plan_path}_{number}").strip()
                    path = st.text_input(f"{number}. 원본 WAV/FLAC 경로", value=masters.get(source, ""),
                                         key=f"um_master_{plan_path}_{number}").strip()
                    new_titles[source] = display_title
                    new_masters[source] = path
                if st.form_submit_button("곡 정보 적용"):
                    st.session_state["um_titles"] = new_titles
                    st.session_state["um_masters"] = new_masters
                    st.rerun()

    # ── RIGHT: cover + readiness + actions ───────────────────────────
    with right:
        st.markdown("### 🖼️ 커버 검증")
        if cover_path:
            cov = CV.validate_cover(cover_path)
            if cov["status"] == "Cover Ready":
                st.success(f"✅ {cov['width']}x{cov['height']} · {cov['format']}")
            elif cov.get("width", 0) > cov.get("height", 0):
                st.info("가로 원본의 전체 프레임을 3000×3000 커버 안에 맞춥니다.")
            else:
                st.warning("⚠️ 커버 경고")
                for w in cov.get("warnings", []):
                    st.caption(f"    {w}")
            if cov.get("width"):
                st.image(cover_path, width=180)
        else:
            st.caption("커버가 선택되지 않았습니다.")

        st.markdown("### 📦 배포 준비도")
        dist_ready = TB.tracklist_distribution_ready(tracks)
        if dist_ready:
            st.success("✅ 곡별 WAV/FLAC 원본 검증 완료")
        else:
            st.warning("⚠️ 검수가 필요한 곡별 배포 파일이 있습니다.")

        st.markdown("### 🚀 액션")
        if st.button("📦 UnitedMasters 패키지 생성", type="primary",
                     use_container_width=True, key="um_create"):
            meta = PS.default_release_metadata(title, artist)
            meta.update({"primary_genre": genre, "language": language, "label_name": label,
                         "copyright_year": int(cyear), "copyright_owner": label or artist,
                         "publishing_owner": label or artist, "release_date_desired": rdate,
                         "explicit_content": explicit, "upc": upc,
                         "previously_released": release_type == "Re-Release"})
            manifest = PS.create_package(playlist_plan, cover_path or "", meta, masters,
                                         title_overrides=titles)
            st.session_state["um_package"] = manifest
            st.success(f"✅ 패키지 생성: {manifest['package_id']} · {manifest['status']}")

        pkg = st.session_state.get("um_package")
        if pkg:
            for warning in pkg.get("warnings", []):
                st.caption(warning)
            ready_cover = pkg.get("cover_upload_ready")
            if ready_cover and Path(ready_cover).is_file():
                st.image(ready_cover, caption="업로드용 1:1 커버", width=180)
            if st.button("🗜️ 수동 업로드 패키지 ZIP", use_container_width=True, key="um_zip"):
                zip_path = PS.build_manual_upload_zip(pkg["package_dir"])
                if zip_path:
                    st.success(f"ZIP 생성: {Path(zip_path).name}")
            st.link_button("🌐 UnitedMasters 열기", PS.UNITEDMASTERS_URL,
                           use_container_width=True)
            if st.button("📂 폴더 열기", use_container_width=True, key="um_open"):
                import subprocess, platform
                try:
                    folder = pkg["package_dir"]
                    if platform.system() == "Windows":
                        subprocess.Popen(["explorer", folder])
                    elif platform.system() == "Darwin":
                        subprocess.Popen(["open", folder])
                    else:
                        subprocess.Popen(["xdg-open", folder])
                except Exception:
                    st.caption(pkg["package_dir"])

    # ── Manual upload checklist ──────────────────────────────────────
    pkg = st.session_state.get("um_package")
    if pkg:
        st.divider()
        st.markdown("### ✅ 수동 업로드 체크리스트")
        checklist_path = Path(pkg["package_dir"]) / "metadata" / "unitedmasters_manual_upload_checklist.md"
        if checklist_path.exists():
            st.markdown(checklist_path.read_text(encoding="utf-8"))
