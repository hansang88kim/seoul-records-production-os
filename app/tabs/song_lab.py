"""
app/tabs/song_lab.py — Song Lab Tab (v0.5)
Main song generation interface: Quick Single / Project Album / Manual Import
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from datetime import datetime, timezone

import streamlit as st
from app.ui.composer_panel import render_composer_panel, SUNO_MODELS, DEFAULT_SUNO_MODEL
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


def _save_plan_to_disk(project_name: str, plan: list[dict]):
    """Save a batch plan to the project folder so it survives refresh."""
    from app.project_manager import song_project_dir
    import json
    pdir = song_project_dir(project_name)
    path = pdir / "batch_plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_plan_from_disk(project_name: str) -> list[dict] | None:
    """Load a saved batch plan from the project folder."""
    from app.project_manager import song_project_dir
    import json
    pdir = song_project_dir(project_name)
    path = pdir / "batch_plan.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _project_selector(key_prefix: str) -> str:
    """
    Render a project name input/selector. Returns the chosen project name.
    Existing projects can be picked from a dropdown, or a new name typed.

    v1.0.0-alpha.92: the dropdown shows each project's song count, a summary
    line shows the total songs generated so far, and an existing project can be
    deleted right here (two-step confirm) — no need to hop to 프로젝트 관리.
    """
    from app.project_manager import list_song_projects, delete_song_project

    existing = list_song_projects()
    names = [p["name"] for p in existing]
    counts = {p["name"]: p.get("song_count", 0) for p in existing}
    total_songs = sum(counts.values())

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
                format_func=lambda n: f"{n}  ·  {counts.get(n, 0)}곡",
                key=f"{key_prefix}_proj_sel",
                label_visibility="collapsed",
            )

    if names:
        sel = (project or "").strip()
        st.caption(
            f"📊 총 **{len(names)}개 프로젝트** · 현재까지 생성 **{total_songs}곡**"
            + (f"  ·  '{sel}' {counts.get(sel, 0)}곡" if (sel and not use_new) else "")
        )
        # per-project delete (only when an EXISTING project is picked)
        if sel and not use_new:
            _ck = f"{key_prefix}_delproj_confirm"
            _dc1, _dc2 = st.columns([2, 1])
            with _dc2:
                if st.button("🗑️ 프로젝트 삭제", key=f"{key_prefix}_delproj",
                             use_container_width=True,
                             help=f"'{sel}' 폴더+곡 전체를 영구 삭제합니다."):
                    st.session_state[_ck] = sel
                    st.rerun()
            if st.session_state.get(_ck) == sel:
                st.warning(f"⚠️ **'{sel}'** 프로젝트를 폴더·곡 전체까지 **영구 삭제**합니다. 되돌릴 수 없어요.")
                _wc1, _wc2 = st.columns(2)
                with _wc1:
                    if st.button("✅ 삭제 확정", key=f"{key_prefix}_delproj_yes",
                                 type="primary", use_container_width=True):
                        ok = delete_song_project(sel)
                        st.session_state.pop(_ck, None)
                        st.session_state.pop(f"{key_prefix}_proj_sel", None)  # reset selection
                        st.success(f"'{sel}' 삭제됨" if ok else "삭제 실패")
                        st.rerun()
                with _wc2:
                    if st.button("취소", key=f"{key_prefix}_delproj_no",
                                 use_container_width=True):
                        st.session_state.pop(_ck, None)
                        st.rerun()

    return project.strip() if project else ""


def _start_quick_single_job(params: dict, project: str = "") -> str | None:
    """
    Launch Quick Single generation as a background worker job — the SAME
    architecture Auto Batch uses (workers/suno_generation_worker.py via
    subprocess.Popen + job_state.json polling, see
    services/generation_job_manager.start_generation_job).

    v1.0.0-alpha.65: this used to call provider.create_song() directly
    inside the Streamlit script run, blocking until Suno finished. Any tab
    switch / refresh / other interaction during that block killed the
    script mid-run, leaving the job stuck at "생성 진행 중" forever — even
    though the actual Suno generation (its own CREATE_NEW_PROCESS_GROUP
    subprocess) kept running independently and completed on Suno's side.
    The app just never found out (no PID was even recorded). Routing
    through the same background worker Auto Batch already uses fixes
    this: the worker survives Streamlit interruption, and the UI polls
    job_state.json for progress (see app/ui/live_console.py).

    Returns the job_id, or None if the job could not be started
    (e.g. missing SUNO_COOKIE) — caller should only st.rerun() on a job_id.
    """
    from services.generation_job_manager import start_generation_job

    cookie = os.getenv("SUNO_COOKIE", "").strip()
    if not cookie:
        st.error("❌ SUNO_COOKIE가 설정되지 않았습니다.")
        st.warning("사이드바 🔑 Suno에서 쿠키를 입력하고 연결하세요.")
        return None

    plan = [{
        "title": params["title"],
        "style": params["style"],
        "lyrics": params["lyrics"],
        "vocal_gender": params.get("vocal_gender", "Female"),
        "status": "drafted",
        "ai_provider": "",
    }]
    settings = {
        "model": params.get("model", "v5"),
        "vocal_gender": params.get("vocal_gender", "Female"),
        "instrumental": params.get("instrumental", False),
        "weirdness": params.get("weirdness", 35),
        "style_influence": params.get("style_influence", 70),
        # v1.0.0-alpha.65: worker falls back to DEFAULT_EXCLUDE when this
        # is empty (Auto Batch never sets it), so this only changes
        # behavior for Quick Single, preserving its per-song exclude edits.
        "exclude_styles": params.get("exclude_styles", []),
    }

    result = start_generation_job(
        project=project or "기본",
        plan=plan,
        settings=settings,
        mode="quick_single",
    )

    job_id = result.get("job_id", "?")
    st.session_state["active_job_id"] = job_id
    if result.get("queued"):
        st.info(f"📋 대기열에 추가됨! (Job: {job_id})")
        st.caption("현재 생성 중인 작업이 끝나면 자동으로 이어서 시작됩니다.")
    else:
        st.success(f"🚀 백그라운드 생성 시작! (Job: {job_id})")
        st.caption("탭을 전환하거나 새로고침해도 생성이 계속됩니다. 아래에서 진행 상황을 확인하세요.")
    return job_id


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


def _generate_plan_only(concept: str, ai_provider_name: str, language: str = "korean",
                       locked_style: str = "", track_no: int = 0,
                       existing_titles: list[str] | None = None,
                       total_tracks: int = 10, mood: str = "") -> dict:
    """
    AI writes ONE song's title/style/lyrics (no Suno generation yet).
    If locked_style is set, use it instead of AI-generated style.
    existing_titles: titles already generated in this batch (AI must avoid them).
    mood (v1.0.0-alpha.94): overall vibe key from providers.ai.base.SONG_MOODS —
    steers the AI style/lyrics AND is woven into the final (even locked) style.
    """
    from providers.ai.base import (get_ai_provider, _lyrics_char_count, _format_lyrics,
                                    mood_directive, apply_mood_to_style)

    draft = {"status": "drafted", "title": "", "style": "", "lyrics": "", "error": ""}
    try:
        ai = get_ai_provider(ai_provider_name)
        # Diversify: tell AI what titles to AVOID (already used in this batch)
        diversified_concept = concept
        _md = mood_directive(mood)
        if _md:
            diversified_concept = f"{_md}\n\n{diversified_concept}"
        if existing_titles:
            avoid_str = ", ".join(f'"{t}"' for t in existing_titles)
            diversified_concept = (
                f"{concept}\n\n"
                f"IMPORTANT — This is song {track_no + 1} in a batch. "
                f"The following titles are ALREADY USED: {avoid_str}. "
                f"You MUST create a COMPLETELY DIFFERENT title and lyrics. "
                f"Do NOT use the same location or similar phrasing. "
                f"Each song should feel like it's from a different album."
            )
        pkg = ai.generate_song_package(diversified_concept, language=language)
        # Ensure lyrics are properly formatted with line breaks
        pkg.lyrics = _format_lyrics(pkg.lyrics)
        if locked_style:
            pkg.style = locked_style  # override with the locked preset
        # Weave the chosen mood into the style (so even a locked preset shifts
        # its emotional color per the selected 무드).
        pkg.style = apply_mood_to_style(pkg.style, mood)
        # Apply composer variation so each batch song is slightly different
        from providers.ai.base import apply_batch_variation, get_batch_vocal
        draft["track_no"] = track_no
        pkg.style = apply_batch_variation(pkg.style, track_no, total_tracks)
        # Determine vocal gender for this track (40% male / 60% female)
        vocal_gender, _ = get_batch_vocal(track_no, total_tracks)
        draft["vocal_gender"] = vocal_gender
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
    Re-authenticates internally.

    v1.0.0-alpha.29: no local download. Returns the task_id so the user can
    find the song on suno.com and download it there directly.
    """
    from providers.suno.suno_cli_provider import SunoCliProvider
    from app.ui.composer_panel import DEFAULT_EXCLUDE

    result = dict(draft)
    title = draft.get("title", "제목 없음")
    style = draft.get("style", "")
    lyrics = draft.get("lyrics", "")

    exclude_list = [s.strip() for s in DEFAULT_EXCLUDE.split(",") if s.strip()]

    try:
        provider = SunoCliProvider()

        options = {
            "exclude_styles": exclude_list,
            "model": base_params.get("model", "v5"),
            "vocal_gender": base_params.get("vocal_gender", "Female"),
            "instrumental": base_params.get("instrumental", False),
            "weirdness": base_params.get("weirdness", 35),
            "style_influence": base_params.get("style_influence", 70),
        }

        task_id = provider.create_song(title, style, lyrics, options)

        result["status"] = "generated"
        result["task_id"] = task_id

        song = {
            "title": title, "status": "submitted",
            "provider": "suno_cli", "model": options["model"],
            "duration": None, "file_type": None, "file_path": "",
            "distribution_eligible": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "task_id": task_id,
            "style": style, "project": project,
        }
        _save_generated_song(song)
        try:
            from app.project_manager import add_song_to_project
            add_song_to_project(project, song)
        except Exception:
            pass

        # 자동 다운로드 훅은 제거됨 (v1.0.0-alpha.119) — 음원은 suno.com에서
        # 직접 받거나, 💿 프로젝트 관리의 ⬇️ 최종본 다운로드 버튼으로 받는다.
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
        "model": base_params.get("model", "v5"),
        "vocal_gender": base_params.get("vocal_gender", "Female"),
        "instrumental": base_params.get("instrumental", False),
        "weirdness": base_params.get("weirdness", 35),
        "style_influence": base_params.get("style_influence", 70),
    }

    # ── Step 3: Suno generates (re-auths internally) ─────────────────────
    # v1.0.0-alpha.29: no local download. Success = create_song() returning
    # a task_id without raising; the user downloads from suno.com directly.
    try:
        provider = SunoCliProvider()

        options = dict(params)
        options.pop("title", None)
        options.pop("lyrics", None)
        options.pop("style", None)

        task_id = provider.create_song(pkg.title, pkg.style, pkg.lyrics, options)

        result["status"] = "generated"
        result["task_id"] = task_id

        _save_generated_song({
            "title": pkg.title, "status": "submitted",
            "provider": "suno_cli", "model": params["model"],
            "duration": None, "file_type": None, "file_path": "",
            "distribution_eligible": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "task_id": task_id,
            "style": pkg.style,
        })

    except Exception as e:
        err_status = getattr(e, "status", "failed")
        result["status"] = "failed"
        result["error"] = f"[{err_status}] {e}"

    return result


def _render_auto_batch():
    """Auto Batch — 2-step: generate plan (preview title/style/lyrics) → generate songs."""
    from providers.ai.base import get_available_ai_providers

    # "🎲" writes to a _pending key instead of "auto_concept" directly,
    # because the auto_concept text_input widget below is instantiated
    # before the button — assigning to st.session_state["auto_concept"]
    # after that would raise StreamlitAPIException even though a
    # st.rerun() follows. Apply the pending value here, before the widget
    # is instantiated.
    if "_auto_concept_pending" in st.session_state:
        st.session_state["auto_concept"] = st.session_state.pop("_auto_concept_pending")

    st.markdown("<h2 style='margin-bottom:0.5rem'>🤖 Auto Batch 생성</h2>", unsafe_allow_html=True)
    st.caption("① AI가 N곡의 제목/스타일/가사를 먼저 만듭니다 → ② 확인/편집 후 Suno로 순차 생성")

    # Project selector — all songs in this batch go to one project folder
    st.markdown("<div style='font-size:0.8rem;color:var(--muted);margin-bottom:4px'>📁 프로젝트 (이 배치의 곡들이 모일 폴더)</div>", unsafe_allow_html=True)
    project = _project_selector("auto")

    # ── Style preset ─────────────────────────────────────────────────────
    from app.ui.composer_panel import CITYPOP_STYLE_PRESET

    if "auto_style" not in st.session_state:
        st.session_state["auto_style"] = CITYPOP_STYLE_PRESET
    if "auto_lock_style" not in st.session_state:
        st.session_state["auto_lock_style"] = True  # default ON

    col_slabel, col_spreset, col_sregen = st.columns([3, 1, 1])
    with col_slabel:
        st.markdown("<div style='font-size:0.85rem;color:var(--muted);padding-top:4px'>🎨 스타일 프리셋 (전 곡 공통)</div>", unsafe_allow_html=True)
    with col_spreset:
        if st.button("프리셋 적용", key="auto_apply_preset", use_container_width=True):
            st.session_state["auto_style"] = CITYPOP_STYLE_PRESET
            st.rerun()
    with col_sregen:
        if st.button("🔀 변주", key="auto_style_regen", use_container_width=True,
                     help="BPM/Key/보컬 톤만 살짝 변경 (장르 유지)"):
            current = st.session_state.get("auto_style", CITYPOP_STYLE_PRESET)
            if current.strip():
                with st.spinner("스타일 변주 중..."):
                    from providers.ai.base import generate_style_variation, get_available_ai_providers
                    avail = [p for p in get_available_ai_providers() if p["available"] and p["name"] != "mock"]
                    pname = avail[0]["name"] if avail else "mock"
                    st.session_state["auto_style"] = generate_style_variation(current, pname)
                    st.rerun()

    col_s, col_sl = st.columns([6, 1])
    with col_s:
        auto_style = st.text_area(
            "스타일", height=80, key="auto_style",
            label_visibility="collapsed",
        )
    with col_sl:
        st.checkbox("🔒", key="auto_lock_style", label_visibility="collapsed",
                    help="잠그면 AI 생성 시 스타일이 이 값으로 고정됩니다")

    is_locked = st.session_state.get("auto_lock_style", True)
    lock_note = "🔒 고정됨 (AI 생성 시 모든 곡에 이 스타일 적용)" if is_locked else "🔓 잠금 해제 (AI가 곡마다 다르게 생성)"
    st.caption(f"{len(auto_style)}/1000 · {lock_note}")

    # v1.0.0-alpha.94: overall MOOD category — keeps citypop (bright/nostalgic,
    # never enka/trot) but shifts the emotional color per selection.
    from providers.ai.base import SONG_MOODS, DEFAULT_SONG_MOOD
    _mkeys = list(SONG_MOODS.keys())
    auto_mood = st.selectbox(
        "🎭 전체 분위기 (무드)", _mkeys,
        index=_mkeys.index(DEFAULT_SONG_MOOD),
        format_func=lambda k: SONG_MOODS[k]["label"], key="auto_mood",
        help="곡 전체의 감정 색. 시티팝(밝고 청량하면서 nostalgic)은 유지하고 분위기만 바뀝니다 "
             "— 엔카/트로트가 아닌 세련된 시티팝. 스타일이 고정돼 있어도 무드 키워드가 반영됩니다.",
    )

    st.divider()

    providers = get_available_ai_providers()
    available = [p for p in providers if p["available"]]

    col_concept, col_provider, col_count = st.columns([3, 1, 1])
    with col_concept:
        cc1, cc2 = st.columns([5, 1])
        with cc1:
            concept = st.text_input(
                "컨셉 / 무드",
                placeholder="예: 서울 밤거리, 이별, 1990s 시티팝",
                key="auto_concept",
                label_visibility="collapsed",
            )
        with cc2:
            if st.button("🎲", key="auto_concept_variation",
                         help="누를 때마다 새로운 주제의 컨셉을 제안합니다 "
                              "(현대 서울 삶·20대 고민·연애·일상·향수 등).",
                         use_container_width=True):
                from services.concept_suggester import next_concept
                with st.spinner("새 컨셉 제안 중..."):
                    sug = next_concept(st.session_state,
                                       avoid=st.session_state.get("auto_concept", ""))
                st.session_state["_auto_concept_pending"] = sug
                st.rerun()
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
            f"<div style='font-size:0.78rem;color:var(--muted);padding-top:30px'>"
            f"🌏 가사: {_lg['lyric_language']} · 도시 감성: {_lg['city']}</div>",
            unsafe_allow_html=True,
        )

    with st.expander("⚙️ 공통 설정 (모델 / 보컬)", expanded=False):
        col_m, col_v = st.columns(2)
        with col_m:
            model = st.selectbox("모델", SUNO_MODELS, index=SUNO_MODELS.index(DEFAULT_SUNO_MODEL), key="auto_model")
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
                locked = auto_style.strip() if st.session_state.get("auto_lock_style") else ""
                # Collect already-generated titles for diversity
                existing_titles = [d.get("title", "") for d in plan if d.get("title")]
                draft = _generate_plan_only(concept.strip(), ai_provider_name,
                                            language=auto_language, locked_style=locked,
                                            track_no=n, existing_titles=existing_titles,
                                            total_tracks=count, mood=auto_mood)
                plan.append(draft)
                prog.progress((n + 1) / count)
            st.session_state["auto_plan_data"] = plan
            # Clear old widget keys so new plan values show correctly
            for k in list(st.session_state.keys()):
                if k.startswith("plan_title_") or k.startswith("plan_style_") or k.startswith("plan_lyrics_"):
                    del st.session_state[k]
            # Persist plan to disk (survives page refresh)
            if project:
                _save_plan_to_disk(project, plan)
            stat.success(f"✅ {count}곡 계획 완료 — 아래에서 확인/편집하세요")
            st.rerun()
    with col_clear:
        if st.session_state.get("auto_plan_data") and st.button("🗑️ 계획 삭제", use_container_width=True, key="auto_plan_clear"):
            st.session_state.pop("auto_plan_data", None)
            st.rerun()

    # ── Step 2: Show Plan (editable) + Generate ──────────────────────────
    plan = st.session_state.get("auto_plan_data", [])
    # Restore plan from disk if session lost (e.g. page refresh)
    if not plan and project:
        disk_plan = _load_plan_from_disk(project)
        if disk_plan:
            plan = disk_plan
            st.session_state["auto_plan_data"] = plan
    if plan:
        st.divider()
        st.markdown(f"<h3>📋 생성 계획 ({len(plan)}곡)</h3>", unsafe_allow_html=True)
        st.caption("각 곡을 펼쳐서 제목/스타일/가사를 확인하고 직접 수정할 수 있습니다.")

        # Summary stats
        total = len(plan)
        done = sum(1 for d in plan if d.get("status") == "generated")
        failed = sum(1 for d in plan if d.get("status") in ("failed", "no_files"))
        pending = total - done - failed
        st.caption(f"✅ {done}곡 완료 · ❌ {failed}곡 실패 · 📝 {pending}곡 대기" if (done or failed) else "")

        for i, draft in enumerate(plan):
            title = draft.get("title", "제목 없음")
            chars = draft.get("lyric_chars", 0)
            status = draft.get("status", "drafted")
            status_icon = {"drafted": "📝", "generated": "✅", "failed": "❌",
                            "no_files": "⚠️", "draft_failed": "❌"}.get(status, "•")
            # Extract BPM and Key from style for display
            import re as _re
            _bpm_m = _re.search(r'BPM (\d+)', draft.get("style", ""))
            _key_m = _re.search(r'([A-G][#b]? (?:major|minor))', draft.get("style", ""))
            _info = f"가사 {chars}자"
            if _bpm_m:
                _info += f" · BPM {_bpm_m.group(1)}"
            if _key_m:
                _info += f" · {_key_m.group(1)}"
            with st.expander(f"{status_icon} {i+1}. {title}  ·  {_info}", expanded=(status in ("failed", "draft_failed"))):
                if draft.get("error"):
                    st.error(draft["error"])
                # Per-song controls
                if status in ("failed", "no_files", "draft_failed") and cookie:
                    if st.button(f"🔄 {i+1}번 곡 Suno 재시도", key=f"retry_{i}", use_container_width=True):
                        with st.spinner(f"🎵 {title} 재생성 중..."):
                            res = _generate_one_from_draft(draft, base_params, project=project or "기본")
                            plan[i] = res
                            st.session_state["auto_plan_data"] = plan
                            st.rerun()

                # Per-track AI regenerate controls
                rg_cols = st.columns(4)
                with rg_cols[0]:
                    if st.button("🔄 전체", key=f"regen_all_{i}", help="제목+스타일+가사 재생성",
                                 use_container_width=True):
                        with st.spinner("재생성 중..."):
                            ai_name = available[prov_idx]["name"] if available else "mock"
                            new_draft = _generate_plan_only(
                                concept.strip(), ai_name,
                                language=auto_language, locked_style="", track_no=i,
                                mood=auto_mood)
                            plan[i].update({
                                "title": new_draft.get("title", ""),
                                "style": new_draft.get("style", ""),
                                "lyrics": new_draft.get("lyrics", ""),
                                "lyric_chars": new_draft.get("lyric_chars", 0),
                                "status": "drafted",
                            })
                            st.session_state["auto_plan_data"] = plan
                            # Clear widget keys so new values show
                            for _k in [f"plan_title_{i}", f"plan_style_{i}", f"plan_lyrics_{i}"]:
                                st.session_state.pop(_k, None)
                            st.rerun()
                with rg_cols[1]:
                    if st.button("📝 제목만", key=f"regen_title_{i}", help="제목만 재생성",
                                 use_container_width=True):
                        with st.spinner("제목 재생성..."):
                            from providers.ai.base import get_ai_provider
                            ai_name = available[prov_idx]["name"] if available else "mock"
                            ai = get_ai_provider(ai_name)
                            plan[i]["title"] = ai.generate_title(concept.strip(), language=auto_language)
                            plan[i]["status"] = "drafted"
                            st.session_state["auto_plan_data"] = plan
                            st.session_state.pop(f"plan_title_{i}", None)
                            st.rerun()
                with rg_cols[2]:
                    if st.button("🎨 스타일", key=f"regen_style_{i}", help="스타일 변주",
                                 use_container_width=True):
                        with st.spinner("스타일 변주..."):
                            from providers.ai.base import apply_batch_variation
                            from app.ui.composer_panel import CITYPOP_STYLE_PRESET
                            base = auto_style.strip() or CITYPOP_STYLE_PRESET
                            plan[i]["style"] = apply_batch_variation(base, i + hash(plan[i].get("title", "")) % 8)
                            st.session_state["auto_plan_data"] = plan
                            st.session_state.pop(f"plan_style_{i}", None)
                            st.rerun()
                with rg_cols[3]:
                    if st.button("✍️ 가사만", key=f"regen_lyrics_{i}", help="가사만 재생성",
                                 use_container_width=True):
                        with st.spinner("가사 재생성..."):
                            from providers.ai.base import get_ai_provider
                            ai_name = available[prov_idx]["name"] if available else "mock"
                            ai = get_ai_provider(ai_name)
                            plan[i]["lyrics"] = ai.generate_lyrics(concept.strip(), language=auto_language)
                            from providers.ai.base import _lyrics_char_count
                            plan[i]["lyric_chars"] = _lyrics_char_count(plan[i]["lyrics"])
                            plan[i]["status"] = "drafted"
                            st.session_state["auto_plan_data"] = plan
                            st.session_state.pop(f"plan_lyrics_{i}", None)
                            st.rerun()

                # Sync plan data → widget keys (so new values show after regeneration)
                if f"plan_title_{i}" not in st.session_state:
                    st.session_state[f"plan_title_{i}"] = draft.get("title", "")
                if f"plan_style_{i}" not in st.session_state:
                    st.session_state[f"plan_style_{i}"] = draft.get("style", "")
                if f"plan_lyrics_{i}" not in st.session_state:
                    st.session_state[f"plan_lyrics_{i}"] = draft.get("lyrics", "")

                # Editable fields
                draft["title"] = st.text_input("제목", key=f"plan_title_{i}")
                draft["style"] = st.text_area("스타일", height=80, key=f"plan_style_{i}")
                draft["lyrics"] = st.text_area("가사", height=200, key=f"plan_lyrics_{i}")
                # Recompute char count
                from providers.ai.base import _lyrics_char_count
                lc = _lyrics_char_count(draft["lyrics"])
                est = int(lc / 118 * 60) + 15
                if lc > 400:
                    st.warning(f"⚠️ 가사 본문 {lc}자 · 예상 ~{est//60}:{est%60:02d} (400자 이하로)")
                elif lc < 360:
                    st.caption(f"가사 본문 {lc}자 · 예상 ~{est//60}:{est%60:02d} (320자 이상 권장)")
                else:
                    st.caption(f"✅ 가사 본문 {lc}자 · 예상 ~{est//60}:{est%60:02d}")

        st.session_state["auto_plan_data"] = plan  # save edits
        if project:
            _save_plan_to_disk(project, plan)  # persist to disk

        st.divider()
        if not cookie:
            st.error("❌ SUNO_COOKIE 미설정 — 사이드바에서 쿠키를 연결하세요.")
        else:
            # Show "retry failed only" button if there are failures
            pending_songs = [d for d in plan if d.get("status") not in ("generated",)]
            if failed > 0 and done > 0:
                col_all, col_retry = st.columns([2, 1])
                with col_all:
                    do_all = st.button(f"🚀 {len(pending_songs)}곡 Suno 생성 시작", type="primary",
                                       use_container_width=True, key="auto_generate")
                with col_retry:
                    do_retry = st.button(f"🔄 실패 {failed}곡만 재시도", use_container_width=True, key="auto_retry_failed")
            else:
                do_all = st.button(f"🚀 {len(pending_songs)}곡 Suno 생성 시작", type="primary",
                                   use_container_width=True, key="auto_generate")
                do_retry = False

            if do_all or do_retry:
                from services.generation_job_manager import start_generation_job

                # Build plan for the worker (only pending tracks)
                if do_retry:
                    worker_plan = [dict(d) for d in plan if d.get("status") not in ("generated",)]
                else:
                    worker_plan = [dict(d) for d in plan if d.get("status") not in ("generated",)]

                settings = {
                    "model": model, "vocal_gender": vocal,
                    "instrumental": vocal == "Instrumental",
                    "weirdness": 35, "style_influence": 70,
                }

                result = start_generation_job(
                    project=project or "기본",
                    plan=worker_plan,
                    settings=settings,
                )

                job_id = result.get("job_id", "?")
                if result.get("queued"):
                    st.session_state["active_job_id"] = job_id
                    st.info(f"📋 대기열에 추가됨! (Job: {job_id})")
                    st.caption("현재 생성 중인 작업이 끝나면 자동으로 이어서 시작됩니다. "
                               "여러 곡을 미리 신청해두면 순서대로 처리됩니다.")
                    st.rerun()
                else:
                    st.session_state["active_job_id"] = job_id
                    st.success(f"🚀 백그라운드 생성 시작! (Job: {job_id})")
                    st.caption("탭을 전환하거나 새로고침해도 생성이 계속됩니다. 아래에서 진행 상황을 확인하세요.")
                    st.rerun()

    # ── Live Generation Console ──────────────────────────────────────────
    st.divider()
    from app.ui.live_console import render_active_job_console
    render_active_job_console()

    st.divider()
    if project:
        st.markdown(f"<h3>🎵 '{project}' 곡</h3>", unsafe_allow_html=True)
        from app.project_manager import get_song_project_songs
        render_song_list(get_song_project_songs(project),
                         project_name=project, key_ns="qs_proj")
    else:
        st.markdown("<h3>🎵 생성된 곡</h3>", unsafe_allow_html=True)
        render_song_list(_load_generated_songs(), key_ns="qs_session")


def _render_quick_single():
    """Quick Single mode — generate 1 song into a project folder (background worker)."""

    # Project selector at the top
    st.markdown("<div style='font-size:0.8rem;color:var(--muted);margin-bottom:4px'>📁 프로젝트 (곡이 저장될 폴더)</div>", unsafe_allow_html=True)
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
            elif _start_quick_single_job(params, project=project):
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
        render_song_list(songs, project_name=project or None, key_ns="batch")

    # ── Live Generation Console (백그라운드 — 탭 전환/새로고침해도 계속 진행) ──
    st.divider()
    from app.ui.live_console import render_active_job_console
    render_active_job_console()


def _render_project_album():
    """Project browser — view all projects and their songs, grouped by folder."""
    from app.project_manager import (
        list_song_projects, get_song_project_songs, delete_song_project,
        song_project_dir,
    )

    st.markdown("<h2 style='margin-bottom:0.3rem'>💿 프로젝트 관리</h2>", unsafe_allow_html=True)
    st.caption("프로젝트별로 곡이 폴더에 모여 있습니다. 유튜브 업로드/배포 시 프로젝트 단위로 관리하세요.")

    # Show job history
    from app.ui.live_console import render_job_history
    render_job_history()
    st.divider()

    projects = list_song_projects()
    if not projects:
        st.info("아직 프로젝트가 없습니다. Quick Single 또는 Auto Batch에서 프로젝트 이름을 입력해 곡을 생성하세요.")
        return

    # ── 📚 Song Library에서 곡 가져오기 (v1.0.0-alpha.43) ────────────────
    # 좌측 Library의 곡 라이브러리와 동일한 이름으로 곡을 골라, 선택한
    # 프로젝트로 복사합니다 (파일 + manifest).
    from services.library_labels import song_entry_label
    from app.project_manager import copy_song_to_project

    with st.expander("📚 Song Library에서 곡 가져오기", expanded=False):
        all_songs = []  # (label, source_project, song)
        for p in projects:
            for s in get_song_project_songs(p["name"]):
                all_songs.append((song_entry_label(p["name"], s), p["name"], s))

        if not all_songs:
            st.caption("라이브러리에 곡이 없습니다.")
        else:
            target = st.selectbox(
                "대상 프로젝트", [p["name"] for p in projects],
                key="lib_import_target",
                help="선택한 곡들이 이 프로젝트의 songs/ 폴더로 복사됩니다.",
            )
            picks = st.multiselect(
                "가져올 곡 (좌측 Library와 동일한 이름)",
                range(len(all_songs)),
                format_func=lambda i: all_songs[i][0],
                key="lib_import_songs",
            )
            if st.button("➕ 선택한 곡을 프로젝트로 복사", key="lib_import_go",
                         use_container_width=True, disabled=not picks):
                copied, skipped = 0, 0
                for i in picks:
                    _, src_proj, song = all_songs[i]
                    if src_proj == target:
                        skipped += 1
                        continue
                    if copy_song_to_project(target, song):
                        copied += 1
                    else:
                        skipped += 1
                if copied:
                    st.success(f"✅ {copied}곡을 '{target}' 프로젝트로 복사했습니다."
                               + (f" (중복/원본 {skipped}곡 건너뜀)" if skipped else ""))
                    st.rerun()
                else:
                    st.warning("복사된 곡이 없습니다 (이미 있거나 원본 프로젝트와 동일).")

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
                st.markdown(f"<div style='font-size:0.8rem;color:var(--muted)'>songs/ 폴더에 {count}곡 저장됨</div>", unsafe_allow_html=True)
            with col_del:
                # v1.0.0-alpha.91: two-step confirm — deleting a project removes
                # the whole folder + all songs permanently, so require a confirm.
                _ck = f"delproj_confirm_{proj['slug']}"
                if st.button("🗑️ 프로젝트 삭제", key=f"delproj_{proj['slug']}",
                             use_container_width=True):
                    st.session_state[_ck] = True
                    st.rerun()
            if st.session_state.get(_ck):
                st.warning(f"⚠️ **'{name}'** 프로젝트를 폴더·곡 전체까지 **영구 삭제**합니다. 되돌릴 수 없어요.")
                dc1, dc2 = st.columns(2)
                with dc1:
                    if st.button("✅ 삭제 확정", key=f"delproj_yes_{proj['slug']}",
                                 type="primary", use_container_width=True):
                        ok = delete_song_project(name)
                        st.session_state.pop(_ck, None)
                        if ok:
                            st.success(f"'{name}' 삭제됨")
                        else:
                            st.error("삭제 실패 — 폴더가 사용 중이거나 없습니다.")
                        st.rerun()
                with dc2:
                    if st.button("취소", key=f"delproj_no_{proj['slug']}",
                                 use_container_width=True):
                        st.session_state.pop(_ck, None)
                        st.rerun()

            songs = get_song_project_songs(name)
            if songs:
                render_song_list(songs, project_name=name,
                                 key_ns=f"proj_{proj['slug']}")

                # ── ⬇️ 최종본 자동 다운로드 (v1.0.0-alpha.52) ──────────
                # 180~240s 범위 우선순위 규칙(모듈 docstring 참고)으로
                # 최종본을 자동 선택해 프로젝트 폴더에 FLAT 저장하고(곡별
                # 폴더 없음), 나머지 버전은 Suno 휴지통으로 보낸다.
                from services.suno_cleanup import _task_clip_ids
                pending = [s for s in songs
                           if len(_task_clip_ids(s.get("task_id") or "")) >= 2
                           and not (s.get("file_path")
                                    and Path(s["file_path"]).exists())]
                dcol1, dcol2 = st.columns([3, 2])
                with dcol2:
                    del_other = st.toggle(
                        "나머지 버전 Suno에서 삭제", value=True,
                        key=f"autodl_del_{proj['slug']}",
                        help="180~240s 우선 → 둘 다 범위 안이면 긴 쪽 → 둘 다 범위 밖이면 "
                             "180~240s에 더 가까운 쪽을 최종본으로 다운로드하고, "
                             "나머지 버전을 Suno 휴지통으로 이동합니다 "
                             "(suno.com 휴지통에서 복원 가능).")
                with dcol1:
                    if st.button(f"⬇️ 최종본 자동 다운로드 (180~240s 우선)"
                                 + (" + 나머지 삭제" if del_other else ""),
                                 key=f"autodl_{proj['slug']}", type="primary",
                                 use_container_width=True):
                        from services.suno_auto_download import auto_download_final_version
                        with st.spinner("Suno에서 길이 비교 → 최종본 다운로드 중..."):
                            rep = auto_download_final_version(name,
                                                              delete_other=del_other)
                        if rep["downloaded"]:
                            st.success("✅ 다운로드: " + ", ".join(
                                f"{d['title']} ({d['duration']:.0f}s)"
                                for d in rep["downloaded"]))
                        if rep["deleted"]:
                            st.info(f"🗑 Suno에서 나머지 버전 {len(rep['deleted'])}개 삭제됨")
                        for sk in rep["skipped"]:
                            st.caption(f"⏭ {sk['title']} — {sk['reason']}")
                        for fl in rep["failed"]:
                            st.error(f"❌ {fl['title']} — {fl.get('reason','')}")
                        if rep["downloaded"]:
                            st.rerun()
                st.caption(f"자동 다운로드 대상: {len(pending)}곡 · 저장 위치: "
                           f"`song_projects/{proj['slug']}/songs/` (곡별 폴더 없음, MP3 파일만)")

                # ── 🧹 Suno 정리: 미선택 버전 삭제 (v1.0.0-alpha.49) ──
                # Suno는 곡당 2개 버전을 만듭니다. 다운로드한 버전은 파일명의
                # 클립 ID로 확정되므로, 나머지 버전만 안전하게 휴지통으로
                # 보냅니다 (드라이런 → 명시적 확인 → 실행 2단계).
                with st.expander("🧹 Suno 정리 — 다운로드하지 않은 나머지 버전 삭제"):
                    st.caption("Suno 워크스페이스에는 곡당 2개 버전이 남습니다. "
                               "로컬에 다운로드한 버전(파일명의 클립 ID로 식별)만 남기고 "
                               "나머지 버전을 Suno 휴지통으로 보냅니다. "
                               "식별이 불확실한 곡은 절대 삭제하지 않습니다.")
                    plan_key = f"suno_cleanup_plan_{proj['slug']}"
                    if st.button("🔍 정리 대상 확인 (드라이런)",
                                 key=f"cleanup_scan_{proj['slug']}",
                                 use_container_width=True):
                        from services.suno_cleanup import plan_suno_cleanup
                        # 길이 규칙 폴백용 provider (실패 시 오프라인 매칭만)
                        _prov = None
                        try:
                            from providers.suno.suno_cli_provider import SunoCliProvider
                            _prov = SunoCliProvider()
                        except Exception:
                            _prov = None
                        st.session_state[plan_key] = plan_suno_cleanup(name, provider=_prov)

                    plan = st.session_state.get(plan_key)
                    if plan is not None:
                        deletable = [e for e in plan if e["action"] == "delete"]
                        for e in plan:
                            if e["action"] == "delete":
                                st.markdown(
                                    f"🗑 **{e['title']}** — 유지: `{e['keep_id']}` · "
                                    f"삭제 예정: `{', '.join(e['delete_ids'])}`")
                            else:
                                st.caption(f"⏭ {e['title']} — {e['reason']}")
                        if not deletable:
                            st.info("삭제할 수 있는 미선택 버전이 없습니다.")
                        else:
                            st.warning(f"⚠️ Suno에서 {sum(len(e['delete_ids']) for e in deletable)}개 "
                                       f"버전이 휴지통으로 이동됩니다. 되돌리려면 suno.com 휴지통에서 복원하세요.")
                            confirm = st.checkbox(
                                "위 삭제 목록을 확인했습니다",
                                key=f"cleanup_confirm_{proj['slug']}")
                            if st.button("🗑 Suno에서 미선택 버전 삭제 실행",
                                         key=f"cleanup_go_{proj['slug']}",
                                         type="primary", use_container_width=True,
                                         disabled=not confirm):
                                from services.suno_cleanup import execute_suno_cleanup
                                with st.spinner("Suno에서 삭제 중..."):
                                    res = execute_suno_cleanup(deletable)
                                if res["deleted"]:
                                    st.success(f"✅ {len(res['deleted'])}개 버전 삭제됨: "
                                               + ", ".join(d['title'] for d in res['deleted']))
                                if res["failed"]:
                                    st.error(f"❌ {len(res['failed'])}개 실패 — "
                                             + "; ".join(f"{f['title']}({f['error']})"
                                                          for f in res['failed']))
                                st.session_state.pop(plan_key, None)
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
    render_song_list(songs, key_ns="manual")
