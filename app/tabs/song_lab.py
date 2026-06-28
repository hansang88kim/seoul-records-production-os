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


def _mp3_duration(path) -> float:
    """Get mp3 duration in seconds (0 if unreadable)."""
    try:
        import mutagen.mp3
        return mutagen.mp3.MP3(str(path)).info.length or 0.0
    except Exception:
        return 0.0


def _snapshot_mp3s(folder) -> set:
    """Set of existing mp3 paths in a folder (before generation)."""
    try:
        return {str(p) for p in Path(folder).glob("*.mp3")}
    except Exception:
        return set()


def _keep_longest_new_mp3(folder, before: set):
    """
    After generation, find NEW mp3s (not in `before`), keep only the LONGEST,
    delete the rest. Suno makes 2 clips per request — we want just the longer.
    Returns the kept mp3 Path, or None if no new files.
    """
    folder = Path(folder)
    new_files = [p for p in folder.glob("*.mp3") if str(p) not in before]
    if not new_files:
        return None
    if len(new_files) == 1:
        return new_files[0]
    # Pick the longest by duration
    new_files.sort(key=_mp3_duration, reverse=True)
    longest = new_files[0]
    # Delete the shorter ones
    for extra in new_files[1:]:
        try:
            extra.unlink()
        except Exception:
            pass
    return longest


def _project_selector(key_prefix: str) -> str:
    """
    Render a project name input/selector. Returns the chosen project name.
    Existing projects can be picked from a dropdown, or a new name typed.
    """
    from app.project_manager import list_song_projects

    existing = list_song_projects()
    names = [p["name"] for p in existing]

    col_mode, col_input = st.columns([1, 2])
    with col_mode:
        if names:
            use_new = st.checkbox("새 프로젝트", value=False, key=f"{key_prefix}_newproj")
        else:
            use_new = True
            st.caption("첫 프로젝트")

    with col_input:
        if use_new or not names:
            project = st.text_input(
                "프로젝트 이름",
                placeholder="예: 서울 시티팝 Vol.1",
                key=f"{key_prefix}_proj_new",
                label_visibility="collapsed",
            )
        else:
            project = st.selectbox(
                "프로젝트",
                names,
                key=f"{key_prefix}_proj_sel",
                label_visibility="collapsed",
            )
    return project.strip() if project else ""


def _run_generation(params: dict, project: str = ""):
    """
    Run song generation via SunoCliProvider.
    Songs download into the project's folder (or a default folder).
    """
    from providers.suno.suno_cli_provider import SunoCliProvider
    from app.project_manager import song_project_download_dir

    provider = SunoCliProvider()
    title = params["title"]

    # Download into the project folder so songs group together
    proj = project or "기본"
    dl_dir = song_project_download_dir(proj, title)

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

    # Snapshot existing mp3s so we can identify the NEW ones afterward
    before_mp3s = _snapshot_mp3s(dl_dir)

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
            "(CAPTCHA 자동 10회 재시도, Chrome 창에서 해결 대기, 최대 10분)"
        )

        task_id = provider.create_song(
            title=params["title"],
            style=params["style"],
            lyrics=params["lyrics"],
            options=options,
        )

        elapsed = int(time.time() - start_time)

        # Keep only the LONGEST of the newly-generated clips (Suno makes 2)
        kept = _keep_longest_new_mp3(dl_dir, before_mp3s)
        if not kept and getattr(provider, "_last_download_dir", None):
            actual_dir = Path(provider._last_download_dir)
            if str(actual_dir) != str(dl_dir):
                kept = _keep_longest_new_mp3(actual_dir, before_mp3s)
                if kept:
                    dl_dir = actual_dir
        mp3s = [kept] if kept else []

        if mp3s:
            dur = _mp3_duration(kept)
            status_container.success(f"✅ 생성 완료! 더 긴 1곡 선택 ({int(dur)}초, {elapsed}초 소요)")
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
                "project": proj,
            }
            songs.append(song)
            _save_generated_song(song)
            # Record in the project manifest so songs group by project
            try:
                from app.project_manager import add_song_to_project
                add_song_to_project(proj, song)
            except Exception:
                pass

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
                "🧩 CAPTCHA 로딩 실패 (자동 10회 재시도했으나 실패)\n\n"
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
        ["⚡ Quick Single", "🤖 Auto Batch", "💿 프로젝트 관리", "📂 Manual Import"],
        horizontal=True,
        key="song_lab_mode",
        label_visibility="collapsed",
    )

    st.divider()

    if "Manual Import" in mode:
        _render_manual_import()
    elif "Auto Batch" in mode:
        _render_auto_batch()
    elif "프로젝트 관리" in mode:
        _render_project_album()
    else:
        _render_quick_single()


def _generate_plan_only(concept: str, ai_provider_name: str, language: str = "korean") -> dict:
    """
    AI writes ONE song's title/style/lyrics (no Suno generation yet).
    Returns a draft dict for the plan preview.
    """
    from providers.ai.base import get_ai_provider, _lyrics_char_count

    draft = {"status": "drafted", "title": "", "style": "", "lyrics": "", "error": ""}
    try:
        ai = get_ai_provider(ai_provider_name)
        pkg = ai.generate_song_package(concept, language=language)
        draft["title"] = pkg.title
        draft["style"] = pkg.style
        draft["lyrics"] = pkg.lyrics
        draft["lyric_chars"] = _lyrics_char_count(pkg.lyrics)
    except Exception as e:
        draft["status"] = "draft_failed"
        draft["error"] = f"AI 생성 실패: {e}"
    return draft


def _generate_one_from_draft(draft: dict, base_params: dict, project: str = "기본") -> dict:
    """
    Generate ONE song in Suno from an already-prepared draft (title/style/lyrics).
    Downloads into the project folder. Re-authenticates internally.
    """
    from providers.suno.suno_cli_provider import SunoCliProvider
    from app.ui.composer_panel import DEFAULT_EXCLUDE
    from app.project_manager import song_project_download_dir

    result = dict(draft)
    title = draft.get("title", "제목 없음")
    style = draft.get("style", "")
    lyrics = draft.get("lyrics", "")

    exclude_list = [s.strip() for s in DEFAULT_EXCLUDE.split(",") if s.strip()]

    try:
        provider = SunoCliProvider()
        dl_dir = song_project_download_dir(project, title)

        options = {
            "exclude_styles": exclude_list,
            "model": base_params.get("model", "v5.5"),
            "vocal_gender": base_params.get("vocal_gender", "Female"),
            "instrumental": base_params.get("instrumental", False),
            "weirdness": base_params.get("weirdness", 35),
            "style_influence": base_params.get("style_influence", 70),
            "download_dir": str(dl_dir),
        }

        before_mp3s = _snapshot_mp3s(dl_dir)
        task_id = provider.create_song(title, style, lyrics, options)

        # Keep only the longest of the 2 generated clips
        kept = _keep_longest_new_mp3(dl_dir, before_mp3s)
        if not kept and getattr(provider, "_last_download_dir", None):
            actual = Path(provider._last_download_dir)
            if str(actual) != str(dl_dir):
                kept = _keep_longest_new_mp3(actual, before_mp3s)
                if kept:
                    dl_dir = actual
        mp3s = [kept] if kept else []

        if mp3s:
            result["status"] = "generated"
            result["file_count"] = len(mp3s)
            from app.project_manager import add_song_to_project
            for i, mp3 in enumerate(mp3s):
                cid = ["A", "B", "C", "D"][i] if i < 4 else str(i)
                song = {
                    "title": title, "candidate_id": cid, "status": "completed",
                    "provider": "suno_cli", "model": options["model"],
                    "duration": None, "file_type": "mp3", "file_path": str(mp3),
                    "distribution_eligible": False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "style": style, "project": project,
                }
                _save_generated_song(song)
                try:
                    add_song_to_project(project, song)
                except Exception:
                    pass
        else:
            result["status"] = "no_files"
            result["error"] = f"생성됐지만 파일 못 찾음 (task: {task_id})"
    except Exception as e:
        err_status = getattr(e, "status", "failed")
        result["status"] = "failed"
        result["error"] = f"[{err_status}] {e}"

    return result


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
        from app.project_manager import song_project_download_dir
        provider = SunoCliProvider()
        dl_dir = song_project_download_dir(base_params.get("project", "기본"), pkg.title)

        options = dict(params)
        options["download_dir"] = str(dl_dir)
        options.pop("title", None)
        options.pop("lyrics", None)
        options.pop("style", None)

        before_mp3s = _snapshot_mp3s(dl_dir)
        task_id = provider.create_song(pkg.title, pkg.style, pkg.lyrics, options)

        kept = _keep_longest_new_mp3(dl_dir, before_mp3s)
        if not kept and getattr(provider, "_last_download_dir", None):
            actual = Path(provider._last_download_dir)
            if str(actual) != str(dl_dir):
                kept = _keep_longest_new_mp3(actual, before_mp3s)
                if kept:
                    dl_dir = actual
        mp3s = [kept] if kept else []

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
    """Auto Batch — 2-step: generate plan (preview title/style/lyrics) → generate songs."""
    from providers.ai.base import get_available_ai_providers

    st.markdown("<h2 style='margin-bottom:0.5rem'>🤖 Auto Batch 생성</h2>", unsafe_allow_html=True)
    st.caption("① AI가 N곡의 제목/스타일/가사를 먼저 만듭니다 → ② 확인/편집 후 Suno로 순차 생성")

    # Project selector — all songs in this batch go to one project folder
    st.markdown("<div style='font-size:0.8rem;color:#9aa5b8;margin-bottom:4px'>📁 프로젝트 (이 배치의 곡들이 모일 폴더)</div>", unsafe_allow_html=True)
    project = _project_selector("auto")
    st.divider()

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

    # Language selector
    from providers.ai.languages import language_choices, get_language
    lang_opts = language_choices()
    col_lang, col_langnote = st.columns([1, 3])
    with col_lang:
        lang_idx = st.selectbox(
            "언어", range(len(lang_opts)),
            format_func=lambda i: lang_opts[i][1],
            key="auto_language_idx",
        )
    auto_language = lang_opts[lang_idx][0]
    with col_langnote:
        _lg = get_language(auto_language)
        st.markdown(
            f"<div style='font-size:0.78rem;color:#7a8aa0;padding-top:30px'>"
            f"🌏 가사: {_lg['lyric_language']} · 도시 감성: {_lg['city']}</div>",
            unsafe_allow_html=True,
        )

    with st.expander("⚙️ 공통 설정 (모델 / 보컬)", expanded=False):
        col_m, col_v = st.columns(2)
        with col_m:
            model = st.selectbox("모델", ["v5.5", "v5", "v4.5", "v4", "v3.5"], index=0, key="auto_model")
        with col_v:
            vocal = st.selectbox("보컬", ["Female", "Male", "Instrumental"], index=0, key="auto_vocal")

    if count >= 10:
        st.warning(f"⚠️ {count}곡은 시간이 오래 걸립니다 (곡당 1~3분, CAPTCHA 대기 포함).")

    cookie = os.getenv("SUNO_COOKIE", "").strip()
    ai_ok = bool(available) and bool(concept.strip())

    base_params = {"model": model, "vocal_gender": vocal, "instrumental": vocal == "Instrumental"}

    # ── Step 1: Generate Plan ────────────────────────────────────────────
    col_plan, col_clear = st.columns([3, 1])
    with col_plan:
        if st.button(f"📝 {count}곡 계획 생성 (제목/스타일/가사)", disabled=not ai_ok,
                     use_container_width=True, key="auto_plan_btn"):
            ai_provider_name = available[prov_idx]["name"]
            plan = []
            prog = st.progress(0.0)
            stat = st.empty()
            for n in range(int(count)):
                stat.info(f"📝 {n+1}/{count}곡 작곡 중... (AI가 제목/스타일/가사 생성)")
                draft = _generate_plan_only(concept.strip(), ai_provider_name, language=auto_language)
                plan.append(draft)
                prog.progress((n + 1) / count)
            st.session_state["auto_plan_data"] = plan
            stat.success(f"✅ {count}곡 계획 완료 — 아래에서 확인/편집하세요")
            st.rerun()
    with col_clear:
        if st.session_state.get("auto_plan_data") and st.button("🗑️ 계획 삭제", use_container_width=True, key="auto_plan_clear"):
            st.session_state.pop("auto_plan_data", None)
            st.rerun()

    # ── Step 2: Show Plan (editable) + Generate ──────────────────────────
    plan = st.session_state.get("auto_plan_data", [])
    if plan:
        st.divider()
        st.markdown(f"<h3>📋 생성 계획 ({len(plan)}곡)</h3>", unsafe_allow_html=True)
        st.caption("각 곡을 펼쳐서 제목/스타일/가사를 확인하고 직접 수정할 수 있습니다.")

        for i, draft in enumerate(plan):
            title = draft.get("title", "제목 없음")
            chars = draft.get("lyric_chars", 0)
            status_icon = {"drafted": "📝", "generated": "✅", "failed": "❌",
                            "no_files": "⚠️", "draft_failed": "❌"}.get(draft.get("status"), "•")
            with st.expander(f"{status_icon} {i+1}. {title}  ·  가사 {chars}자", expanded=False):
                if draft.get("error"):
                    st.error(draft["error"])
                # Editable fields
                draft["title"] = st.text_input("제목", value=draft.get("title", ""), key=f"plan_title_{i}")
                draft["style"] = st.text_area("스타일", value=draft.get("style", ""), height=80, key=f"plan_style_{i}")
                draft["lyrics"] = st.text_area("가사", value=draft.get("lyrics", ""), height=200, key=f"plan_lyrics_{i}")
                # Recompute char count
                from providers.ai.base import _lyrics_char_count
                lc = _lyrics_char_count(draft["lyrics"])
                est = int(lc / 118 * 60) + 15
                st.caption(f"가사 {lc}자 · 예상 ~{est//60}:{est%60:02d}")

        st.session_state["auto_plan_data"] = plan  # save edits

        st.divider()
        if not cookie:
            st.error("❌ SUNO_COOKIE 미설정 — 사이드바에서 쿠키를 연결하세요.")
        else:
            if st.button(f"🚀 {len(plan)}곡 Suno 생성 시작", type="primary",
                         use_container_width=True, key="auto_generate"):
                prog = st.progress(0.0)
                stat = st.empty()
                results_box = st.container()
                ok = 0
                for n, draft in enumerate(plan):
                    stat.info(f"🎵 {n+1}/{len(plan)}곡 생성 중: {draft.get('title','?')} "
                              f"(인증 → Suno 생성, CAPTCHA 자동 재시도)")
                    res = _generate_one_from_draft(draft, base_params, project=project or "기본")
                    plan[n] = res
                    if res["status"] == "generated":
                        ok += 1
                    prog.progress((n + 1) / len(plan))
                    with results_box:
                        icon = {"generated": "✅", "failed": "❌", "no_files": "⚠️"}.get(res["status"], "•")
                        st.write(f"{icon} **{n+1}. {res.get('title','?')}** — {res['status']}"
                                 + (f" · {res['error']}" if res.get("error") else ""))
                st.session_state["auto_plan_data"] = plan
                stat.success(f"✅ 완료: {ok}/{len(plan)}곡 생성 성공")

    st.divider()
    if project:
        st.markdown(f"<h3>🎵 '{project}' 곡</h3>", unsafe_allow_html=True)
        from app.project_manager import get_song_project_songs
        render_song_list(get_song_project_songs(project))
    else:
        st.markdown("<h3>🎵 생성된 곡</h3>", unsafe_allow_html=True)
        render_song_list(_load_generated_songs())


def _render_quick_single():
    """Quick Single mode — generate 1 song into a project folder."""

    # Project selector at the top
    st.markdown("<div style='font-size:0.8rem;color:#9aa5b8;margin-bottom:4px'>📁 프로젝트 (곡이 저장될 폴더)</div>", unsafe_allow_html=True)
    project = _project_selector("qs")
    if not project:
        st.caption("💡 프로젝트 이름을 입력하면 그 폴더에 곡이 모입니다 (유튜브 업로드 시 편리)")
    st.divider()

    col_composer, col_results = st.columns([1, 1], gap="large")

    with col_composer:
        st.markdown("<h2 style='margin-bottom:0.5rem'>🎵 Song Composer</h2>", unsafe_allow_html=True)
        params = render_composer_panel()

        if params:
            if not project:
                st.warning("⚠️ 먼저 프로젝트 이름을 입력하세요 (위쪽).")
            else:
                _run_generation(params, project=project)
                st.rerun()

    with col_results:
        # Show songs from the selected project
        if project:
            st.markdown(f"<h2 style='margin-bottom:0.5rem'>📋 '{project}' 곡</h2>", unsafe_allow_html=True)
            from app.project_manager import get_song_project_songs
            songs = get_song_project_songs(project)
        else:
            st.markdown("<h2 style='margin-bottom:0.5rem'>📋 생성 결과</h2>", unsafe_allow_html=True)
            songs = _load_generated_songs()
        render_song_list(songs)


def _render_project_album():
    """Project browser — view all projects and their songs, grouped by folder."""
    from app.project_manager import (
        list_song_projects, get_song_project_songs, delete_song_project,
        song_project_dir,
    )

    st.markdown("<h2 style='margin-bottom:0.3rem'>💿 프로젝트 관리</h2>", unsafe_allow_html=True)
    st.caption("프로젝트별로 곡이 폴더에 모여 있습니다. 유튜브 업로드/배포 시 프로젝트 단위로 관리하세요.")

    projects = list_song_projects()
    if not projects:
        st.info("아직 프로젝트가 없습니다. Quick Single 또는 Auto Batch에서 프로젝트 이름을 입력해 곡을 생성하세요.")
        return

    # Project summary cards
    st.markdown(f"**총 {len(projects)}개 프로젝트**")
    for proj in projects:
        name = proj["name"]
        count = proj["song_count"]
        with st.expander(f"📁 {name}  ·  {count}곡", expanded=False):
            pdir = song_project_dir(name)
            st.caption(f"폴더: `{pdir}`")

            col_open, col_del = st.columns([3, 1])
            with col_open:
                st.markdown(f"<div style='font-size:0.8rem;color:#7a8aa0'>songs/ 폴더에 {count}곡 저장됨</div>", unsafe_allow_html=True)
            with col_del:
                if st.button("🗑️ 삭제", key=f"delproj_{proj['slug']}", use_container_width=True):
                    if delete_song_project(name):
                        st.success(f"'{name}' 삭제됨")
                        st.rerun()

            songs = get_song_project_songs(name)
            if songs:
                render_song_list(songs)
            else:
                st.caption("이 프로젝트에 곡이 없습니다.")


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
