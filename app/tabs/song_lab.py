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

    # ── Pre-check: cookie present? ───────────────────────────────────────
    cookie = os.getenv("SUNO_COOKIE", "").strip()
    if not cookie:
        status_container.error("❌ SUNO_COOKIE가 설정되지 않았습니다.")
        st.warning("사이드바 🔑 Suno에서 쿠키를 입력하고 연결하세요.")
        return

    try:
        # create_song handles auth (cookie → auth → credits verify) on every call,
        # then generates. It raises ProviderError('auth_required') if auth fails.
        status_container.info(
            "🔐 인증 + 크레딧 확인 → 🚀 생성 중... "
            "(CAPTCHA 자동 3회 재시도, Chrome 창에서 해결 대기, 최대 10분)"
        )

        task_id = provider.create_song(
            title=params["title"],
            style=params["style"],
            lyrics=params["lyrics"],
            options=options,
        )

        elapsed = int(time.time() - start_time)

        # Find downloaded files — check both our dir and provider's actual dir
        mp3s = sorted(dl_dir.glob("*.mp3"))
        if not mp3s and getattr(provider, "_last_download_dir", None):
            actual_dir = Path(provider._last_download_dir)
            mp3s = sorted(actual_dir.glob("*.mp3"))
            if mp3s:
                dl_dir = actual_dir

        if mp3s:
            status_container.success(f"✅ 생성 완료! {len(mp3s)}곡 ({elapsed}초)")
        else:
            status_container.warning(f"⚠️ Suno 생성은 됐지만 파일을 못 찾았습니다 ({elapsed}초). task_id: {task_id}")

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

        # Show detailed error
        err_details = getattr(e, "details", {})
        status_container.error(f"❌ 생성 실패 ({elapsed}초): {err_msg}")
        if err_details:
            with st.expander("에러 상세"):
                st.json({k: str(v) for k, v in err_details.items()})

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
            st.error("🔑 Suno 인증 실패 — 쿠키가 만료되었습니다.")
            st.info("사이드바 🔑 Suno → [편집] → 새 쿠키 입력 → 연결 후 다시 생성하세요.")
        elif err_status == "captcha_required":
            st.warning(
                "🧩 CAPTCHA 로딩 실패 (자동 3회 재시도했으나 실패)\n\n"
                "Suno 서버의 hCaptcha가 간헐적으로 로딩되지 않는 문제입니다. "
                "**해결 방법:**\n"
                "1. Chrome에서 suno.com/create 를 직접 열어 로그인 상태와 CAPTCHA가 뜨는지 확인\n"
                "2. 다시 Send to Suno 클릭 (보통 잠시 후 풀립니다)\n"
                "3. 계속 실패하면 쿠키를 새로 발급받아 입력"
            )
            # Store params so user can retry easily
            st.session_state["retry_params"] = params


def render_song_lab():
    """Render the Song Lab tab."""

    # ── Mode Selector ────────────────────────────────────────────────────
    mode = st.radio(
        "모드",
        ["⚡ Quick Single", "🤖 Auto Batch", "💿 Project Album", "📂 Manual Import"],
        horizontal=True,
        key="song_lab_mode",
        label_visibility="collapsed",
    )

    st.divider()

    if "Manual Import" in mode:
        _render_manual_import()
    elif "Auto Batch" in mode:
        _render_auto_batch()
    elif "Project Album" in mode:
        _render_project_album()
    else:
        _render_quick_single()


def _generate_one_auto(concept: str, ai_provider_name: str, base_params: dict) -> dict:
    """
    Generate ONE complete song automatically: AI writes title/style/lyrics,
    then Suno generates. Returns a result dict with status.
    Each call re-authenticates with Suno.
    """
    from providers.ai.base import get_ai_provider
    from providers.suno.suno_cli_provider import SunoCliProvider

    result = {"concept": concept, "status": "drafted", "title": "", "error": ""}

    # ── Step 1: AI writes the song ───────────────────────────────────────
    try:
        ai = get_ai_provider(ai_provider_name)
        pkg = ai.generate_song_package(concept)
        result["title"] = pkg.title
        result["style"] = pkg.style
        result["lyrics"] = pkg.lyrics
    except Exception as e:
        result["status"] = "failed"
        result["error"] = f"AI 생성 실패: {e}"
        return result

    # ── Step 2: Build Suno params ────────────────────────────────────────
    # Exclude styles go to the --exclude flag (Suno's Exclude styles box),
    # NOT merged into the style text (that would make Suno ADD them).
    from app.ui.composer_panel import DEFAULT_EXCLUDE
    exclude_list = [s.strip() for s in DEFAULT_EXCLUDE.split(",") if s.strip()]

    params = {
        "title": pkg.title,
        "lyrics": pkg.lyrics,
        "style": pkg.style,  # clean style only
        "exclude_styles": exclude_list,  # → --exclude flag
        "model": base_params.get("model", "v5.5"),
        "vocal_gender": base_params.get("vocal_gender", "Female"),
        "instrumental": base_params.get("instrumental", False),
        "weirdness": base_params.get("weirdness", 35),
        "style_influence": base_params.get("style_influence", 70),
    }

    # ── Step 3: Suno generates (re-auths internally) ─────────────────────
    try:
        provider = SunoCliProvider()
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_title = pkg.title.replace("/", "_").replace("\\", "_").replace(":", "_").replace(" ", "-")
        dl_dir = _get_outputs_dir() / "suno_downloads" / f"{ts}_{safe_title}"
        dl_dir.mkdir(parents=True, exist_ok=True)

        options = dict(params)
        options["download_dir"] = str(dl_dir)
        options.pop("title", None)
        options.pop("lyrics", None)
        options.pop("style", None)

        task_id = provider.create_song(pkg.title, pkg.style, pkg.lyrics, options)

        mp3s = sorted(dl_dir.glob("*.mp3"))
        if not mp3s and getattr(provider, "_last_download_dir", None):
            mp3s = sorted(Path(provider._last_download_dir).glob("*.mp3"))
            if mp3s:
                dl_dir = Path(provider._last_download_dir)

        if mp3s:
            result["status"] = "generated"
            result["file_count"] = len(mp3s)
            # Save to generated songs list
            for i, mp3 in enumerate(mp3s):
                cid = ["A", "B", "C", "D"][i] if i < 4 else str(i)
                _save_generated_song({
                    "title": pkg.title, "candidate_id": cid, "status": "completed",
                    "provider": "suno_cli", "model": params["model"],
                    "duration": None, "file_type": "mp3", "file_path": str(mp3),
                    "distribution_eligible": False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "style": pkg.style,
                })
        else:
            result["status"] = "no_files"
            result["error"] = f"생성됐지만 파일 못 찾음 (task: {task_id})"

    except Exception as e:
        err_status = getattr(e, "status", "failed")
        result["status"] = "failed"
        result["error"] = f"[{err_status}] {e}"

    return result


def _render_auto_batch():
    """Auto Batch mode — generate N songs automatically."""
    from providers.ai.base import get_available_ai_providers

    st.markdown("<h2 style='margin-bottom:0.5rem'>🤖 Auto Batch 생성</h2>", unsafe_allow_html=True)
    st.caption("컨셉과 곡 수를 입력하면 AI가 매번 새 제목/스타일/가사를 만들고, Suno가 자동 생성합니다.")

    # Provider
    providers = get_available_ai_providers()
    available = [p for p in providers if p["available"]]

    col_concept, col_provider, col_count = st.columns([3, 1, 1])
    with col_concept:
        concept = st.text_input(
            "컨셉 / 무드",
            placeholder="예: 서울 밤거리, 이별, 1990s 시티팝",
            key="auto_concept",
        )
    with col_provider:
        prov_idx = st.selectbox(
            "AI", range(len(available)),
            format_func=lambda i: available[i]["label"],
            key="auto_provider_idx",
        ) if available else None
    with col_count:
        count = st.number_input("곡 수", min_value=1, max_value=20, value=5, step=1, key="auto_count")

    # Base settings
    with st.expander("⚙️ 공통 설정 (모델 / 보컬)", expanded=False):
        col_m, col_v = st.columns(2)
        with col_m:
            model = st.selectbox("모델", ["v5.5", "v5", "v4.5", "v4", "v3.5"], index=0, key="auto_model")
        with col_v:
            vocal = st.selectbox("보컬", ["Female", "Male", "Instrumental"], index=0, key="auto_vocal")

    if count >= 10:
        st.warning(f"⚠️ {count}곡 생성은 시간이 오래 걸립니다 (곡당 1~3분, CAPTCHA 대기 포함). 크레딧도 충분한지 확인하세요.")

    # Cookie check
    cookie = os.getenv("SUNO_COOKIE", "").strip()
    if not cookie:
        st.error("❌ SUNO_COOKIE 미설정 — 사이드바에서 쿠키를 연결하세요.")
        return

    ai_ok = bool(available) and bool(concept.strip())

    # Start button
    if st.button(f"🚀 {count}곡 자동 생성 시작", type="primary", disabled=not ai_ok,
                 use_container_width=True, key="auto_start"):
        base_params = {"model": model, "vocal_gender": vocal,
                       "instrumental": vocal == "Instrumental"}
        ai_provider_name = available[prov_idx]["name"]

        progress = st.progress(0.0)
        status = st.empty()
        results_box = st.container()

        results = []
        for n in range(int(count)):
            status.info(f"🎵 {n+1}/{count}곡 생성 중... (인증 → AI 작곡 → Suno 생성)")
            res = _generate_one_auto(concept.strip(), ai_provider_name, base_params)
            results.append(res)
            progress.progress((n + 1) / count)

            with results_box:
                icon = {"generated": "✅", "failed": "❌", "no_files": "⚠️"}.get(res["status"], "•")
                st.write(f"{icon} **{n+1}. {res.get('title', '?')}** — {res['status']}"
                         + (f" · {res['error']}" if res.get("error") else ""))

        ok = sum(1 for r in results if r["status"] == "generated")
        status.success(f"✅ 완료: {ok}/{count}곡 생성 성공")

    st.divider()
    st.markdown("<h3>📋 생성된 곡</h3>", unsafe_allow_html=True)
    render_song_list(_load_generated_songs())


def _render_quick_single():
    """Quick Single mode — generate 1 song without project setup."""

    col_composer, col_results = st.columns([1, 1], gap="large")

    with col_composer:
        st.markdown("<h2 style='margin-bottom:0.5rem'>🎵 Song Composer</h2>", unsafe_allow_html=True)
        params = render_composer_panel()

        if params:
            _run_generation(params)
            st.rerun()

    with col_results:
        st.markdown("<h2 style='margin-bottom:0.5rem'>📋 생성 결과</h2>", unsafe_allow_html=True)
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
