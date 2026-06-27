"""
Seoul Records Production OS — Tab 1: Song Generation
"""
import time
from pathlib import Path
from datetime import datetime, timezone

import streamlit as st
from app.models import TrackPrompt
from app.state_machine import TrackStatus, ProjectStatus
from app.project_manager import save_manifest, log_action
from app.config import SUNO_MODELS, AUTO_MODE_INTERVAL_SECONDS, AUTO_MODE_TEST_INTERVAL_SECONDS
from agents.producer_agent import generate_song_prompt
from workflows.generate_album import run_song_generation, update_song_list_csv


def _get_folder() -> Path:
    return Path(st.session_state.current_output_folder)


def _get_manifest():
    return st.session_state.current_project


def _save(manifest):
    st.session_state.current_project = manifest
    save_manifest(manifest, _get_folder())


# ─── Song List Table ─────────────────────────────────────────────────────────

def render_song_list_table():
    manifest = _get_manifest()
    st.markdown("#### 📋 Song List")

    if not manifest.tracks:
        st.info("No tracks yet.")
        return

    rows = []
    for t in manifest.tracks:
        dur = f"{t.duration_seconds:.0f}s" if t.duration_seconds else "—"
        wav = "✅" if t.is_wav else "—"
        warns = f"⚠️ {', '.join(t.qc_warnings[:2])}" if t.qc_warnings else "✅"
        rows.append({
            "#": t.track_number,
            "Title": t.prompt.title or "(no title)",
            "Style": (t.prompt.style or "")[:40],
            "Duration": dur,
            "Status": t.status,
            "WAV": wav,
            "QC": warns,
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)


# ─── Manual Mode: Single Track Editor ────────────────────────────────────────

def render_manual_track_editor(track_index: int):
    manifest = _get_manifest()
    output_folder = _get_folder()
    track = manifest.tracks[track_index]
    p = track.prompt

    st.markdown(f"##### Track {track.track_number}: {p.title or '(untitled)'}")
    st.caption(f"Status: **{track.status}**")

    # Prompt generation
    col_gen, col_lock = st.columns([3, 1])
    with col_gen:
        if st.button("🎲 Generate Prompt", key=f"gen_prompt_{track_index}"):
            with st.spinner("Generating…"):
                result = generate_song_prompt(
                    track_number=track.track_number,
                    theme=manifest.theme,
                    language_pack=manifest.language_pack,
                    locked_title=p.title_locked,
                    locked_style=p.style_locked,
                    locked_lyrics=p.lyrics_locked,
                    existing_title=p.title,
                    existing_style=p.style,
                    existing_lyrics=p.lyrics,
                )
                if not p.title_locked:
                    p.title = result["title"]
                if not p.style_locked:
                    p.style = result["style"]
                if not p.lyrics_locked:
                    p.lyrics = result["lyrics"]
                p.exclude_styles = result["exclude_styles"]
                track.update_status(TrackStatus.PROMPT_READY)
                _save(manifest)
                st.rerun()

    st.divider()

    # Title row
    c1, c2, c3 = st.columns([4, 1, 1])
    with c1:
        new_title = st.text_input("Title", value=p.title, key=f"title_{track_index}",
                                   disabled=p.title_locked)
        if new_title != p.title and not p.title_locked:
            p.title = new_title
    with c2:
        if st.button("🔄", key=f"regen_title_{track_index}", help="Regenerate title"):
            r = generate_song_prompt(track.track_number, manifest.theme,
                                      manifest.language_pack, locked_title=False,
                                      locked_style=True, locked_lyrics=True,
                                      existing_style=p.style, existing_lyrics=p.lyrics)
            p.title = r["title"]
            _save(manifest)
            st.rerun()
    with c3:
        locked = st.checkbox("🔒", value=p.title_locked, key=f"lock_title_{track_index}",
                              help="Lock title")
        p.title_locked = locked

    # Style row
    c1, c2, c3 = st.columns([4, 1, 1])
    with c1:
        new_style = st.text_input("Style", value=p.style, key=f"style_{track_index}",
                                   disabled=p.style_locked)
        if new_style != p.style and not p.style_locked:
            p.style = new_style
    with c2:
        if st.button("🔄", key=f"regen_style_{track_index}", help="Regenerate style"):
            r = generate_song_prompt(track.track_number, manifest.theme,
                                      manifest.language_pack, locked_title=True,
                                      locked_style=False, locked_lyrics=True,
                                      existing_title=p.title, existing_lyrics=p.lyrics)
            p.style = r["style"]
            _save(manifest)
            st.rerun()
    with c3:
        locked = st.checkbox("🔒", value=p.style_locked, key=f"lock_style_{track_index}",
                              help="Lock style")
        p.style_locked = locked

    # Exclude styles
    # exclude_styles is list[str] — display as comma-separated string
    excl_display = ", ".join(p.exclude_styles) if p.exclude_styles else ""
    new_excl_str = st.text_input("Exclude Styles", value=excl_display,
                                  key=f"excl_{track_index}",
                                  help="Comma-separated. Stored as list in manifest.")
    new_excl_list = [s.strip() for s in new_excl_str.split(",") if s.strip()]
    if new_excl_list != p.exclude_styles:
        p.exclude_styles = new_excl_list

    # Lyrics
    c1, c2, c3 = st.columns([4, 1, 1])
    with c1:
        st.markdown("**Lyrics**")
    with c2:
        if st.button("🔄", key=f"regen_lyrics_{track_index}", help="Regenerate lyrics"):
            r = generate_song_prompt(track.track_number, manifest.theme,
                                      manifest.language_pack, locked_title=True,
                                      locked_style=True, locked_lyrics=False,
                                      existing_title=p.title, existing_style=p.style)
            p.lyrics = r["lyrics"]
            _save(manifest)
            st.rerun()
    with c3:
        locked = st.checkbox("🔒", value=p.lyrics_locked, key=f"lock_lyrics_{track_index}",
                              help="Lock lyrics")
        p.lyrics_locked = locked

    new_lyrics = st.text_area("Lyrics Content", value=p.lyrics, height=200,
                               key=f"lyrics_{track_index}", disabled=p.lyrics_locked,
                               label_visibility="collapsed")
    if new_lyrics != p.lyrics and not p.lyrics_locked:
        p.lyrics = new_lyrics

    # Controls row
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        p.vocal_gender = st.selectbox("Vocal Gender", ["Female", "Male", "Auto"],
                                       index=["Female", "Male", "Auto"].index(p.vocal_gender),
                                       key=f"vocal_{track_index}")
    with col_b:
        p.model = st.selectbox("Model", SUNO_MODELS,
                                index=SUNO_MODELS.index(p.model) if p.model in SUNO_MODELS else 0,
                                key=f"model_{track_index}")
    with col_c:
        p.instrumental = st.toggle("Instrumental", value=p.instrumental, key=f"inst_{track_index}")

    p.weirdness = st.slider("Weirdness", 0, 100, p.weirdness, key=f"weird_{track_index}")
    p.style_influence = st.slider("Style Influence", 0, 100, p.style_influence, key=f"influence_{track_index}")

    optional_vid = st.text_input("Persona / Voice ID (optional)",
                                  value=p.persona_voice_id or "",
                                  key=f"persona_{track_index}")
    p.persona_voice_id = optional_vid or None

    _save(manifest)
    st.divider()

    # Actions
    col_confirm, col_send = st.columns(2)
    with col_confirm:
        if st.button("✅ Confirm Prompt", key=f"confirm_{track_index}", use_container_width=True):
            track.update_status(TrackStatus.CONFIRMED)
            _save(manifest)
            st.success("Prompt confirmed.")

    with col_send:
        ready = track.status in (TrackStatus.CONFIRMED, TrackStatus.PROMPT_READY)
        if st.button("🚀 Send to Suno", key=f"send_{track_index}",
                     type="primary", use_container_width=True, disabled=not ready):
            with st.spinner(f"Generating Track {track.track_number}…"):
                updated_track = run_song_generation(manifest, output_folder, track)
                manifest.tracks[track_index] = updated_track
                update_song_list_csv(manifest, output_folder)
                if all(t.status in (TrackStatus.SAVED, TrackStatus.APPROVED)
                       for t in manifest.tracks):
                    manifest.update_status(ProjectStatus.SONG_GENERATION_COMPLETED)
                _save(manifest)
            st.success(f"Track {track.track_number} complete! Selected: candidate_{updated_track.selected_candidate_id}")
            if updated_track.qc_warnings:
                st.warning(f"QC warnings: {', '.join(updated_track.qc_warnings)}")
            st.rerun()

    # Candidate override — Fix 6: use track_folder_path, not folder scan
    if track.candidates and len(track.candidates) >= 2:
        st.markdown("**Candidate Override**")
        options = [f"Candidate {c.candidate_id} ({c.duration_seconds:.0f}s)" for c in track.candidates]
        selected_idx = next(
            (i for i, c in enumerate(track.candidates) if c.candidate_id == track.selected_candidate_id),
            0
        )
        choice = st.radio("Select candidate", options, index=selected_idx,
                           horizontal=True, key=f"cand_override_{track_index}")
        chosen_id = choice.split(" ")[1]
        if chosen_id != track.selected_candidate_id:
            import shutil
            track.selected_candidate_id = chosen_id
            # Use the exact track folder — never scan all song folders
            if track.track_folder_path and Path(track.track_folder_path).exists():
                tf = Path(track.track_folder_path)
            else:
                # Derive from track_number + title as fallback
                from app.project_manager import _slugify
                safe = _slugify(track.prompt.title) or f"track-{track.track_number:02d}"
                tf = output_folder / "01_suno_song_generation" / "songs" / f"{track.track_number:02d}_{safe}"
            src = tf / "candidates" / f"candidate_{chosen_id}.wav"
            dst = tf / "selected" / "suno_master.wav"
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                track.selected_wav_path = str(dst)
                cand_meta = next((c for c in track.candidates if c.candidate_id == chosen_id), None)
                if cand_meta:
                    track.duration_seconds = cand_meta.duration_seconds
                _save(manifest)
                st.success(f"Switched to Candidate {chosen_id}")
                st.rerun()
            else:
                st.error(f"Candidate WAV not found: {src}")

    # ── Fix 7: Manual WAV Import UI ──────────────────────────────────────────
    st.divider()
    with st.expander("📂 Manual WAV Import", expanded=False):
        st.caption("Upload WAV files directly (bypasses Suno). Good for manual production.")

        import_mode = st.radio(
            "Import mode",
            ["Upload selected WAV directly", "Upload Candidate A + B"],
            horizontal=True,
            key=f"import_mode_{track_index}",
        )

        if import_mode == "Upload selected WAV directly":
            uploaded = st.file_uploader(
                "Upload WAV", type=["wav"],
                key=f"manual_wav_{track_index}",
            )
            if uploaded and st.button("💾 Import WAV", key=f"import_btn_{track_index}"):
                from providers.suno.manual_import import ManualImportProvider
                from app.project_manager import create_track_folder, _slugify

                songs_root = output_folder / "01_suno_song_generation"
                tf = create_track_folder(
                    songs_root, track.track_number,
                    track.prompt.title or f"track-{track.track_number:02d}",
                )
                track.track_folder_path = str(tf)
                dest = tf / "selected" / "suno_master.wav"
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(uploaded.read())

                provider = ManualImportProvider()
                # Re-read for validation
                info = provider.import_wav(dest, dest)
                track.selected_wav_path = str(dest)
                track.is_wav = info["is_wav"]
                track.duration_seconds = info.get("duration_seconds")
                track.distribution_eligible = info["is_wav"]
                track.update_status(TrackStatus.SAVED)
                _save(manifest)
                st.success(
                    f"✅ WAV imported: {info.get('duration_seconds', '?'):.0f}s"
                    if info.get("duration_seconds")
                    else "✅ WAV imported (duration unknown)"
                )
                st.rerun()

        else:  # Upload Candidate A + B
            col_a, col_b = st.columns(2)
            with col_a:
                up_a = st.file_uploader("Candidate A (WAV)", type=["wav"],
                                         key=f"cand_a_{track_index}")
            with col_b:
                up_b = st.file_uploader("Candidate B (WAV)", type=["wav"],
                                         key=f"cand_b_{track_index}")

            if (up_a or up_b) and st.button("💾 Import Candidates", key=f"import_cands_{track_index}"):
                from providers.suno.manual_import import ManualImportProvider
                from providers.suno.mock_suno import _read_wav_duration
                from app.project_manager import create_track_folder
                from app.models import CandidateMetadata
                from agents.qc_agent import select_best_candidate

                songs_root = output_folder / "01_suno_song_generation"
                tf = create_track_folder(
                    songs_root, track.track_number,
                    track.prompt.title or f"track-{track.track_number:02d}",
                )
                track.track_folder_path = str(tf)
                cands_dir = tf / "candidates"
                cands_dir.mkdir(exist_ok=True)
                cand_infos = []

                for label, uploaded_file, cid in [("A", up_a, "A"), ("B", up_b, "B")]:
                    if uploaded_file:
                        dest = cands_dir / f"candidate_{cid}.wav"
                        dest.write_bytes(uploaded_file.read())
                        dur = _read_wav_duration(dest)
                        cand_infos.append({
                            "candidate_id": cid,
                            "file_path": str(dest),
                            "duration_seconds": dur or 0,
                            "is_wav": True,
                        })
                        track.candidates.append(CandidateMetadata(
                            candidate_id=cid,
                            task_id="manual",
                            file_path=str(dest),
                            duration_seconds=dur,
                            is_wav=True,
                            provider="manual_import",
                        ))

                if cand_infos:
                    result = select_best_candidate(cand_infos)
                    track.selected_candidate_id = result.candidate_id
                    if result.save_wav:
                        import shutil
                        src = cands_dir / f"candidate_{result.candidate_id}.wav"
                        dst = tf / "selected" / "suno_master.wav"
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dst)
                        track.selected_wav_path = str(dst)
                        track.is_wav = True
                        best_info = next((c for c in cand_infos if c["candidate_id"] == result.candidate_id), {})
                        track.duration_seconds = best_info.get("duration_seconds")
                        track.distribution_eligible = True
                        track.update_status(TrackStatus.SAVED)
                    else:
                        track.update_status(TrackStatus.REGENERATION_REQUIRED)
                    track.qc_warnings.extend(result.qc_warnings)
                    _save(manifest)
                    st.success(f"Candidates imported. Selected: {result.candidate_id}")
                    st.rerun()


# ─── Auto Mode ───────────────────────────────────────────────────────────────

def render_auto_mode():
    manifest = _get_manifest()
    output_folder = _get_folder()

    st.markdown("#### ⚙️ Auto Mode")
    st.info(
        "Auto Mode generates all tracks sequentially with a 5-minute interval between Suno requests. "
        "Use Test Mode (10s interval) for development."
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        test_mode = st.checkbox("⚡ Test Mode (10s interval)", value=True)
    with col2:
        interval = AUTO_MODE_TEST_INTERVAL_SECONDS if test_mode else AUTO_MODE_INTERVAL_SECONDS
        st.metric("Interval", f"{interval}s")
    with col3:
        pending = [t for t in manifest.tracks
                   if t.status not in (TrackStatus.SAVED, TrackStatus.APPROVED, TrackStatus.FAILED)]
        st.metric("Remaining", f"{len(pending)} tracks")

    # Auto-generate remaining tracks
    if st.button("▶️ Start Auto Mode", type="primary", use_container_width=True):
        pending_tracks = [t for t in manifest.tracks
                          if t.status not in (TrackStatus.SAVED, TrackStatus.APPROVED, TrackStatus.FAILED)]

        if not pending_tracks:
            st.success("All tracks already complete!")
            return

        manifest.auto_mode_active = True
        manifest.update_status(ProjectStatus.SONG_GENERATION_IN_PROGRESS)
        _save(manifest)

        progress_bar = st.progress(0.0)
        status_text = st.empty()
        completed_in_run = 0

        for i, track in enumerate(pending_tracks):
            # Check interval
            if manifest.auto_mode_last_job_time and i > 0:
                last = datetime.fromisoformat(manifest.auto_mode_last_job_time)
                elapsed = (datetime.now(timezone.utc) - last).total_seconds()
                wait = interval - elapsed
                if wait > 0:
                    status_text.info(f"⏱ Waiting {wait:.0f}s before next track…")
                    time.sleep(wait)

            status_text.info(f"🎵 Generating Track {track.track_number}: {track.prompt.title or '(generating…)'}…")

            # Generate prompt if needed
            if not track.prompt.title:
                result = generate_song_prompt(
                    track_number=track.track_number,
                    theme=manifest.theme,
                    language_pack=manifest.language_pack,
                )
                track.prompt.title = result["title"]
                track.prompt.style = result["style"]
                track.prompt.lyrics = result["lyrics"]
                track.prompt.exclude_styles = result["exclude_styles"]
                track.prompt.vocal_gender = "Female"

            # Track index in manifest
            tidx = next(j for j, t in enumerate(manifest.tracks) if t.track_id == track.track_id)
            updated_track = run_song_generation(manifest, output_folder, manifest.tracks[tidx])
            manifest.tracks[tidx] = updated_track
            manifest.auto_mode_last_job_time = datetime.now(timezone.utc).isoformat()
            update_song_list_csv(manifest, output_folder)
            _save(manifest)

            completed_in_run += 1
            progress_bar.progress(completed_in_run / len(pending_tracks))

        # Check if all done
        if all(t.status in (TrackStatus.SAVED, TrackStatus.APPROVED, TrackStatus.FAILED)
               for t in manifest.tracks):
            manifest.update_status(ProjectStatus.SONG_GENERATION_COMPLETED)

        manifest.auto_mode_active = False
        _save(manifest)
        status_text.success(f"✅ Auto Mode complete — {completed_in_run} tracks generated.")
        st.rerun()


# ─── Main Tab Render ─────────────────────────────────────────────────────────

def render_tab_song_generation():
    manifest = _get_manifest()
    st.markdown("## 🎵 Song Generation")
    st.caption("Seoul Records City Pop · Generate and manage your tracks")

    col_stat, col_wav = st.columns(2)
    with col_stat:
        completed = sum(1 for t in manifest.tracks if t.status in ("saved", "approved"))
        st.metric("Tracks Complete", f"{completed} / {manifest.track_count}")
    with col_wav:
        wav_ready = sum(1 for t in manifest.tracks if t.is_wav)
        st.metric("WAV Ready", wav_ready)

    render_song_list_table()
    st.divider()

    if manifest.production_mode == "Auto":
        render_auto_mode()
    else:
        # Manual mode: track selector
        if not manifest.tracks:
            st.warning("No tracks in this project.")
            return

        track_options = [
            f"Track {t.track_number}: {t.prompt.title or '(untitled)'} [{t.status}]"
            for t in manifest.tracks
        ]
        selected_label = st.selectbox("Select Track to Edit", track_options)
        selected_idx = track_options.index(selected_label)
        st.divider()
        render_manual_track_editor(selected_idx)

    st.divider()
    # Log viewer
    with st.expander("📋 Generation Log (last 20 entries)", expanded=False):
        log_path = _get_folder() / "project_log.jsonl"
        if log_path.exists():
            lines = log_path.read_text(encoding="utf-8").strip().split("\n")
            for line in reversed(lines[-20:]):
                try:
                    import json
                    entry = json.loads(line)
                    st.caption(f"`{entry.get('timestamp', '')[:19]}` [{entry.get('level')}] **{entry.get('action')}** — {entry.get('step')}")
                except Exception:
                    st.caption(line)
        else:
            st.caption("No log entries yet.")
