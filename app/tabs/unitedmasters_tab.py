"""
app/tabs/unitedmasters_tab.py — UnitedMasters Distribution Package Studio (v0.9.0).

Builds a manual-upload distribution package from the Video Renderer playlist
order + streaming cover. MP3 = source/draft audio (distribution_ready=False);
WAV/FLAC masters flip a track to distribution-ready. No fake WAV, no credential
storage, no CAPTCHA bypass — manual upload workflow only.
"""
from __future__ import annotations

from pathlib import Path
import streamlit as st

from services.unitedmasters import source_scanner as SRC
from services.unitedmasters import track_builder as TB
from services.unitedmasters import cover_validator as CV
from services.unitedmasters import package_service as PS


def render_unitedmasters():
    st.markdown("## 🎶 UnitedMasters")
    st.caption("Video Renderer 플레이리스트 순서 + Streaming Cover로 배포 제출 패키지를 만듭니다. "
               "MP3는 소스/초안 음원이며, 실제 배포에는 WAV/FLAC 마스터가 필요합니다.")

    # ── Top: source selection ────────────────────────────────────────
    tcol1, tcol2 = st.columns(2)
    with tcol1:
        plans = SRC.find_playlist_plans()
        if not plans:
            st.warning("⚠️ Video Renderer의 playlist_plan.json을 찾을 수 없습니다. "
                       "먼저 Video Renderer에서 플레이리스트를 만드세요.")
            return
        plan_labels = {f"{Path(p['path']).parent.name} ({p['entries_count']}곡)": p["path"]
                       for p in plans}
        sel_plan_label = st.selectbox("Video Renderer 플레이리스트", list(plan_labels.keys()),
                                      key="um_plan")
        plan_path = plan_labels[sel_plan_label]
        import json
        playlist_plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    with tcol2:
        covers = SRC.find_streaming_covers()
        if covers:
            cover_path = st.selectbox("Streaming Cover 1:1", covers,
                                      format_func=lambda c: Path(c).name, key="um_cover")
        else:
            st.warning("⚠️ streaming_cover_1x1을 찾을 수 없습니다. Thumbnail Studio에서 1:1 커버를 내보내세요.")
            cover_path = None

    # Build the tracklist (with any attached masters from session)
    masters = st.session_state.get("um_masters", {})
    tracks = TB.build_tracklist(playlist_plan, masters)

    st.divider()
    left, center, right = st.columns([1, 2, 1])

    # ── LEFT: release metadata form ──────────────────────────────────
    with left:
        st.markdown("### 📝 릴리스 메타데이터")
        artist = st.text_input("아티스트", "Seoul Records", key="um_artist")
        title = st.text_input("릴리스 제목", "Korea CityPop Playlist Vol.1", key="um_title")
        genre = st.text_input("주 장르", "City Pop", key="um_genre")
        language = st.text_input("언어", "Korean", key="um_lang")
        label = st.text_input("레이블", "Seoul Records", key="um_label")
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
                st.rerun()

        for t in tracks:
            val = TB.validate_audio(t)
            badge = {"Distribution Ready": "✅", "MP3-only Warning": "⚠️",
                     "Missing WAV/FLAC": "❌"}.get(val["status"], "•")
            st.write(f"**{t['track_no']}. {t['title']}** — "
                     f"{int(t['duration_sec'])//60}:{int(t['duration_sec'])%60:02d} · {badge} {val['status']}")
            st.caption(f"    MP3: {Path(t['mp3_path']).name if t['mp3_path'] else '없음'}")
            if t["master_path"]:
                st.caption(f"    마스터: {Path(t['master_path']).name}")
            else:
                st.caption("    ⚠️ WAV/FLAC 마스터 필요 — 실제 배포 전 첨부하세요")

        # Attach WAV/FLAC masters
        with st.expander("🎚️ WAV/FLAC 마스터 첨부 (경로 입력)"):
            st.caption("배포용 마스터(WAV/FLAC)의 로컬 경로를 트랙 순서대로 입력하세요. "
                       "MP3는 WAV로 변환되지 않으며, 가짜 WAV를 만들지 않습니다.")
            new_masters = dict(masters)
            for t in tracks:
                key = f"um_master_{t['track_no']}"
                path = st.text_input(f"{t['track_no']}. {t['title']} 마스터 경로",
                                     value=masters.get(t["mp3_path"], ""), key=key)
                if path and Path(path).exists() and Path(path).suffix.lower() in (".wav", ".flac"):
                    new_masters[t["mp3_path"]] = path
                elif path and not Path(path).exists():
                    st.caption(f"    ⚠️ 파일을 찾을 수 없습니다: {path}")
            if st.button("첨부 적용", key="um_attach"):
                st.session_state["um_masters"] = new_masters
                st.rerun()

    # ── RIGHT: cover + readiness + actions ───────────────────────────
    with right:
        st.markdown("### 🖼️ 커버 검증")
        if cover_path:
            cov = CV.validate_cover(cover_path)
            if cov["status"] == "Cover Ready":
                st.success(f"✅ {cov['width']}x{cov['height']} · {cov['format']}")
            else:
                st.warning("⚠️ 커버 경고")
                for w in cov.get("warnings", []):
                    st.caption(f"    {w}")
            if Path(cover_path).exists():
                st.image(cover_path, width=180)
        else:
            st.caption("커버가 선택되지 않았습니다.")

        st.markdown("### 📦 배포 준비도")
        dist_ready = TB.tracklist_distribution_ready(tracks)
        if dist_ready:
            st.success("✅ Distribution Ready (모든 트랙에 WAV/FLAC 마스터)")
        else:
            st.warning("⚠️ MP3-only — 실제 배포에는 WAV/FLAC 마스터가 필요합니다.")
            st.caption("MP3는 YouTube 소스 음원입니다. 마스터 첨부 후 Ready로 전환됩니다.")

        st.markdown("### 🚀 액션")
        if st.button("📦 UnitedMasters 패키지 생성", type="primary",
                     use_container_width=True, key="um_create"):
            meta = PS.default_release_metadata(title, artist)
            meta.update({"primary_genre": genre, "language": language, "label_name": label,
                         "copyright_year": int(cyear), "copyright_owner": label,
                         "publishing_owner": label, "release_date_desired": rdate,
                         "explicit_content": explicit})
            manifest = PS.create_package(playlist_plan, cover_path or "", meta, masters)
            st.session_state["um_package"] = manifest
            st.success(f"✅ 패키지 생성: {manifest['package_id']} · {manifest['status']}")

        pkg = st.session_state.get("um_package")
        if pkg:
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
