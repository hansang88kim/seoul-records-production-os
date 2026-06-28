"""
app/tabs/song_lab.py — Song Lab Tab (v0.5)
Main song generation interface: Quick Single / Project Album / Manual Import
"""
from __future__ import annotations

import json
import os
import time
import subprocess
from pathlib import Path
from datetime import datetime, timezone

import streamlit as st
from app.ui.composer_panel import render_composer_panel
from app.ui.song_card import render_song_list


def _get_outputs_dir() -> Path:
    """Get outputs directory."""
    return Path(__file__).resolve().parent.parent.parent / "outputs"


def _load_generated_songs() -> list[dict]:
    """Load generated songs from session state + disk."""
    songs = st.session_state.get("generated_songs", [])
    return songs


def _save_generated_song(song: dict):
    """Add a song to the generated list."""
    if "generated_songs" not in st.session_state:
        st.session_state["generated_songs"] = []
    st.session_state["generated_songs"].insert(0, song)


def _run_generation(params: dict):
    """
    Run song generation via SunoCliProvider.
    Shows progress in the UI instead of freezing.
    """
    from providers.suno.suno_cli_provider import SunoCliProvider

    provider = SunoCliProvider()
    title = params["title"]

    # Create output directory
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_title = title.replace("/", "_").replace("\\", "_").replace(":", "_").replace(" ", "-")
    dl_dir = _get_outputs_dir() / "suno_downloads" / f"{ts}_{safe_title}"
    dl_dir.mkdir(parents=True, exist_ok=True)

    # Build options
    options = {
        "exclude_styles": params.get("exclude_styles", []),
        "vocal_gender": params.get("vocal_gender", "Female"),
        "instrumental": params.get("instrumental", False),
        "weirdness": params.get("weirdness", 35),
        "style_influence": params.get("style_influence", 70),
        "model": params.get("model", "v5.5"),
        "download_dir": str(dl_dir),
    }

    # Progress display
    progress_container = st.empty()
    status_container = st.empty()
    start_time = time.time()

    status_container.info("🔐 Suno 인증 중...")

    try:
        # Auto-auth
        provider._ensure_auth()
        status_container.info("🚀 Suno에 곡 생성 요청 중... CAPTCHA 해결이 필요할 수 있습니다.")

        # Generate — this blocks until complete (--wait)
        # Start a timer display in a separate approach
        # Since subprocess blocks, we show status before/after
        task_id = provider.create_song(
            title=params["title"],
            style=params["style"],
            lyrics=params["lyrics"],
            options=options,
        )

        elapsed = int(time.time() - start_time)
        status_container.success(f"✅ 생성 완료! ({elapsed}초 소요)")

        # Find downloaded files
        mp3s = sorted(dl_dir.glob("*.mp3"))
        songs = []
        labels = ["A", "B", "C", "D"]

        for i, mp3 in enumerate(mp3s):
            cid = labels[i] if i < len(labels) else str(i)
            # Get duration from file if possible
            duration = None
            try:
                import mutagen.mp3
                audio = mutagen.mp3.MP3(str(mp3))
                duration = audio.info.length
            except Exception:
                pass

            song = {
                "title": title,
                "candidate_id": cid,
                "status": "completed",
                "provider": "suno_cli",
                "model": params.get("model", "v5.5"),
                "duration": duration,
                "file_type": "mp3",
                "file_path": str(mp3),
                "distribution_eligible": False,  # MP3 = preview only
                "created_at": datetime.now(timezone.utc).isoformat(),
                "clip_id": mp3.stem,
                "style": params["style"],
                "vocal": params.get("vocal_gender", ""),
                "weirdness": params.get("weirdness", 35),
                "style_influence": params.get("style_influence", 70),
            }
            songs.append(song)
            _save_generated_song(song)

        if not mp3s:
            status_container.warning("⚠️ 생성은 됐지만 MP3 파일을 찾지 못했습니다.")

        # Save report
        report = {
            "title": title,
            "task_id": task_id,
            "songs": songs,
            "params": {k: v for k, v in params.items() if k != "lyrics"},
            "elapsed_seconds": elapsed,
            "download_dir": str(dl_dir),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        report_path = dl_dir / "generation_report.json"
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    except Exception as e:
        elapsed = int(time.time() - start_time)
        err_status = getattr(e, "status", "generation_failed")
        err_msg = str(e)

        status_container.error(f"❌ 생성 실패 ({elapsed}초): {err_msg}")

        song = {
            "title": title,
            "candidate_id": "—",
            "status": err_status,
            "provider": "suno_cli",
            "model": params.get("model", "v5.5"),
            "duration": None,
            "file_type": "—",
            "file_path": "",
            "distribution_eligible": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "error": err_msg,
        }
        _save_generated_song(song)

        if err_status == "auth_required":
            st.warning("🔑 Suno 인증이 필요합니다. 사이드바에서 쿠키를 입력해 주세요.")
        elif err_status == "captcha_required":
            st.warning("🧩 CAPTCHA가 해결되지 않았습니다. 다시 시도해 주세요.")


def render_song_lab():
    """Render the Song Lab tab."""

    # ── Mode Selector ────────────────────────────────────────────────────
    mode = st.radio(
        "모드",
        ["⚡ Quick Single", "💿 Project Album", "📂 Manual Import"],
        horizontal=True,
        key="song_lab_mode",
        label_visibility="collapsed",
    )

    st.divider()

    if "Manual Import" in mode:
        _render_manual_import()
    elif "Project Album" in mode:
        _render_project_album()
    else:
        _render_quick_single()


def _render_quick_single():
    """Quick Single mode — generate 1 song without project setup."""

    col_composer, col_results = st.columns([1, 1], gap="large")

    with col_composer:
        st.markdown("### 🎵 Song Composer")
        params = render_composer_panel()

        if params:
            _run_generation(params)
            st.rerun()

    with col_results:
        st.markdown("### 📋 생성 결과")
        songs = _load_generated_songs()
        render_song_list(songs)


def _render_project_album():
    """Project Album mode — uses existing project system."""
    if "current_project" not in st.session_state or st.session_state.current_project is None:
        st.info("💿 프로젝트를 먼저 생성하거나 열어주세요.")
        st.caption("왼쪽 사이드바에서 프로젝트를 선택하거나, 메인 화면에서 새 프로젝트를 만들 수 있습니다.")
        return

    manifest = st.session_state.current_project
    st.markdown(f"### 💿 {manifest.project_name}")
    st.caption(f"트랙 {manifest.track_count}곡 · {manifest.production_mode} 모드")

    col_composer, col_results = st.columns([1, 1], gap="large")

    with col_composer:
        st.markdown("#### Song Composer")
        params = render_composer_panel()
        if params:
            _run_generation(params)
            st.rerun()

    with col_results:
        st.markdown("#### 생성 결과")
        songs = _load_generated_songs()
        render_song_list(songs)


def _render_manual_import():
    """Manual Import mode — WAV upload."""
    st.markdown("### 📂 Manual WAV Import")
    st.caption(
        "suno.com에서 WAV를 직접 다운로드한 후 여기에 업로드하세요. "
        "WAV만 distribution master로 사용 가능합니다. MP3는 미리듣기 전용입니다."
    )

    uploaded = st.file_uploader(
        "WAV 파일 업로드",
        type=["wav"],
        accept_multiple_files=True,
        key="manual_wav_upload",
    )

    if uploaded:
        dl_dir = _get_outputs_dir() / "manual_imports" / datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dl_dir.mkdir(parents=True, exist_ok=True)

        for f in uploaded:
            save_path = dl_dir / f.name
            save_path.write_bytes(f.read())
            st.success(f"✅ 저장됨: {save_path.name}")

            song = {
                "title": f.name.replace(".wav", ""),
                "candidate_id": "imported",
                "status": "imported",
                "provider": "manual_import",
                "model": "—",
                "duration": None,
                "file_type": "wav",
                "file_path": str(save_path),
                "distribution_eligible": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            _save_generated_song(song)

    songs = _load_generated_songs()
    render_song_list(songs)
