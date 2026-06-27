"""
Seoul Records Production OS — Tab 3: Longform Video
"""
from pathlib import Path
import streamlit as st
from app.project_manager import save_manifest, log_action
from workflows.render_video import export_video_package, _ffmpeg_available, _format_timestamp


def _get_folder() -> Path:
    return Path(st.session_state.current_output_folder)


def _get_manifest():
    return st.session_state.current_project


def _save(manifest):
    st.session_state.current_project = manifest
    save_manifest(manifest, _get_folder())


def render_tab_video():
    manifest = _get_manifest()
    output_folder = _get_folder()
    st.markdown("## 🎬 Longform Video")
    st.caption("FFmpeg-based video rendering · timestamps · YouTube chapters")

    # Status checks
    wav_tracks = [t for t in manifest.tracks if t.is_wav and t.selected_wav_path]
    thumb_path = output_folder / "02_thumbnail_cover" / "final" / "youtube_thumbnail_16x9.png"

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("WAV Tracks Ready", len(wav_tracks))
    with col2:
        st.metric("FFmpeg", "✅ Available" if _ffmpeg_available() else "❌ Not Found")
    with col3:
        total_dur = sum((t.duration_seconds or 210.0) for t in wav_tracks)
        st.metric("Est. Duration", _format_timestamp(total_dur) if wav_tracks else "—")

    if not wav_tracks:
        st.warning("⚠️ No WAV tracks ready. Complete Song Generation first.")
        return

    # Output type note
    if manifest.output_type == "1 Hour Playlist Mode":
        st.info("📌 Mode: 1 Hour Playlist — targeting ~15-16 tracks, ~60 minutes")
    elif manifest.output_type == "Full Album Mix Mode":
        st.info("📌 Mode: Full Album Mix — targeting ~20 tracks, ~70-80 minutes")

    if not _ffmpeg_available():
        st.warning("⚠️ FFmpeg not found. Will export command files for manual rendering.")

    st.divider()

    # Generate package
    if st.button("🎬 Generate Video Package", type="primary", use_container_width=True):
        with st.spinner("Building video package…"):
            result = export_video_package(manifest, output_folder)
            _save(manifest)

        st.success("✅ Video package generated!")

        if result.get("rendered"):
            st.balloons()
            st.success(f"🎉 Video rendered: `{result['output_video']}`")
        else:
            st.info("FFmpeg command exported. Run manually or install FFmpeg to auto-render.")

        st.rerun()

    # Show current state
    video = manifest.video
    if video.timestamps_generated:
        st.divider()
        timestamps_path = output_folder / "03_longform_video" / "timestamps" / "timestamps.txt"
        chapters_path = output_folder / "03_longform_video" / "timestamps" / "youtube_chapters.txt"
        ffmpeg_cmd_path = output_folder / "03_longform_video" / "render_scripts" / "ffmpeg_render_command.txt"

        col_a, col_b = st.columns(2)
        with col_a:
            if timestamps_path.exists():
                with st.expander("⏱ Timestamps", expanded=True):
                    st.code(timestamps_path.read_text(encoding="utf-8"))
            if chapters_path.exists():
                with st.expander("📋 YouTube Chapters", expanded=False):
                    st.code(chapters_path.read_text(encoding="utf-8"))

        with col_b:
            if ffmpeg_cmd_path.exists():
                with st.expander("🖥 FFmpeg Command", expanded=True):
                    st.code(ffmpeg_cmd_path.read_text(encoding="utf-8"), language="bash")
                    st.caption("Copy and run in your terminal to render the video.")

        # Metrics
        st.divider()
        col_x, col_y = st.columns(2)
        with col_x:
            st.metric("Total Duration", _format_timestamp(video.total_duration_seconds or 0))
        with col_y:
            st.metric("Render Status", "✅ Rendered" if video.status == "rendered" else "⏳ Command Ready")

        if video.final_video_path and Path(video.final_video_path).exists():
            st.success(f"📹 Video: `{video.final_video_path}`")
        else:
            st.info(f"📁 Render script: `{video.render_command_path}`")

    st.divider()
    with st.expander("📦 Manual Export Assets", expanded=False):
        st.markdown("""
**For CapCut / Manual Editing:**
1. Find selected WAV files in `01_suno_song_generation/songs/*/selected/suno_master.wav`
2. Import background image from `02_thumbnail_cover/final/`
3. Use timestamps from `03_longform_video/timestamps/timestamps.txt`
4. Follow FFmpeg command as reference for timing
        """)
        audio_list_path = output_folder / "03_longform_video" / "input" / "selected_audio_list.txt"
        if audio_list_path.exists():
            st.code(audio_list_path.read_text(encoding="utf-8"))
