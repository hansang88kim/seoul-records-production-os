"""
app/tabs/production_qa_tab.py — Pilot Production QA Mode (v0.8.4).

A readiness dashboard that scans outputs/ and shows what's ready, what's
missing, the next recommended action, the pilot render sequence, and a report
export. Read-only — never modifies any production asset.
"""
from __future__ import annotations

from pathlib import Path
import streamlit as st

from services.production import production_scanner as scanner
from services.production import production_checklist as checklist
from services.production import production_status_models as M


def render_production_qa():
    st.markdown("## ✅ Production QA")
    st.caption("outputs 폴더를 스캔해 YouTube CityPop Playlist 제작 준비 상태를 한눈에 확인합니다.")

    # ── Top bar: scope + refresh + export ────────────────────────────
    tcol1, tcol2, tcol3 = st.columns([2, 1, 1])
    with tcol1:
        scope = st.selectbox(
            "스캔 범위",
            ["전체 outputs 스캔", "최신 제작물", "Thumbnail 세션", "Video 렌더 작업", "YouTube 패키지"],
            key="pqa_scope",
            help="기본은 전체 outputs 스캔입니다.",
        )
    with tcol2:
        refresh = st.button("🔄 다시 스캔", use_container_width=True)
    with tcol3:
        export = st.button("📤 리포트 내보내기", use_container_width=True)

    # Scan (cached in session unless refreshed)
    if refresh or "pqa_checklist" not in st.session_state:
        snap = scanner.scan_all()
        st.session_state["pqa_checklist"] = checklist.build_checklist(snap)
    cl = st.session_state["pqa_checklist"]
    snap = cl["snapshot"]

    # Detected counts
    st.caption(
        f"감지: MP3 {snap['songs']['mp3_count']}개 · "
        f"썸네일 {'O' if snap['thumbnails']['youtube_thumbnail'] else 'X'} · "
        f"final_video {snap['video']['final_video_count']}개 · "
        f"YouTube 패키지 {'O' if snap['youtube_package']['package_manifest'] else 'X'}"
    )

    if export:
        result = checklist.export_report(cl)
        st.success(f"✅ 리포트 생성: {result['report_id']}")
        st.caption(f"폴더: {result['report_dir']}")
        for name, path in result["files"].items():
            st.caption(f"• {name}: {Path(path).name}")

    st.divider()

    # ── Three columns: scores | checklist | warnings ─────────────────
    left, center, right = st.columns([1, 2, 1])

    # LEFT: readiness scores + next action
    with left:
        st.markdown("### 📊 준비도")
        st.metric("전체 준비도", f"{cl['overall_readiness']}%")
        st.progress(cl["overall_readiness"] / 100)
        score_labels = {
            "song_readiness": "🎵 음악",
            "visual_readiness": "🖼️ 비주얼",
            "video_readiness": "🎬 영상",
            "youtube_package_readiness": "▶️ 패키지",
            "upload_readiness": "📤 업로드",
            "unitedmasters_readiness": "🎶 UnitedMasters",
        }
        for key, label in score_labels.items():
            sc = cl["scores"][key]
            st.caption(f"{label}: {sc}%")
            st.progress(sc / 100)

        st.markdown("### ➡️ 다음 추천 작업")
        st.info(cl["next_action"])

    # CENTER: grouped checklist
    with center:
        st.markdown("### 📋 체크리스트")
        status_icon = {
            M.STATUS_READY: "✅", M.STATUS_COMPLETED: "✅", M.STATUS_MISSING: "❌",
            M.STATUS_WARNING: "⚠️", M.STATUS_OPTIONAL: "▫️", M.STATUS_NEEDS_REVIEW: "🔎",
        }
        for group, items in cl["groups"].items():
            with st.expander(group, expanded=(group in ("Songs", "Video render"))):
                for it in items:
                    icon = status_icon.get(it["status"], "•")
                    line = f"{icon} {it['label']} — {it['status']}"
                    st.write(line)
                    if it.get("detail"):
                        st.caption(f"    {it['detail']}")

    # RIGHT: warnings + missing + pilot sequence
    with right:
        st.markdown("### ⚠️ 경고 / 누락")
        blockers = [w for w in cl["warnings"] if w["level"] == "blocker"]
        warns = [w for w in cl["warnings"] if w["level"] == "warning"]
        opts = [w for w in cl["warnings"] if w["level"] == "optional"]
        if blockers:
            for w in blockers:
                st.error(w["message"])
        if warns:
            for w in warns:
                st.warning(w["message"])
        if opts:
            with st.expander(f"선택 권장 ({len(opts)})", expanded=False):
                for w in opts:
                    st.caption(f"▫️ {w['message']}")
        if not (blockers or warns or opts):
            st.success("경고 없음 — 모든 산출물이 준비되었습니다.")

    # ── Pilot render sequence guide ──────────────────────────────────
    st.divider()
    st.markdown("### 🚀 Pilot 제작 순서")
    seq = checklist.pilot_sequence_status(snap)
    for i, s in enumerate(seq, 1):
        mark = "✅" if s["status"] == M.STATUS_COMPLETED else "🔎"
        cols = st.columns([3, 2, 1])
        cols[0].write(f"{mark} {i}. {s['step']}")
        cols[1].caption(f"산출물: {s['expected_output']}")
        cols[2].caption(f"→ {s['tab']}")
