"""
Seoul Records Production OS — Tab 2: Thumbnail & Cover
"""
import json
from pathlib import Path
from datetime import datetime, timezone

import streamlit as st
from app.project_manager import save_manifest, log_action
from app.state_machine import ProjectStatus
from providers.image.mock_image import generate_mock_thumbnail_16x9, generate_mock_cover_1x1


def _get_folder() -> Path:
    return Path(st.session_state.current_output_folder)


def _get_manifest():
    return st.session_state.current_project


def _save(manifest):
    st.session_state.current_project = manifest
    save_manifest(manifest, _get_folder())


def render_tab_thumbnail():
    manifest = _get_manifest()
    output_folder = _get_folder()
    st.markdown("## 🖼 Thumbnail & Cover")
    st.caption("YouTube 16:9 thumbnail · DSP 1:1 cover art")

    thumb_root = output_folder / "02_thumbnail_cover"
    final_dir = thumb_root / "final"
    source_dir = thumb_root / "source_images"
    flow_dir = thumb_root / "flow_prompts"

    for d in [final_dir, source_dir, flow_dir]:
        d.mkdir(parents=True, exist_ok=True)

    thumb_16x9 = final_dir / "youtube_thumbnail_16x9.png"
    cover_1x1 = final_dir / "dsp_cover_3000x3000.png"

    col_thumb, col_cover = st.columns(2)

    # ── YouTube Thumbnail 16:9 ────────────────────────────────────────────────
    with col_thumb:
        st.markdown("#### YouTube Thumbnail (16:9)")
        if thumb_16x9.exists():
            st.image(str(thumb_16x9), use_container_width=True)
            st.success("✅ 1280×720 placeholder ready")
        else:
            st.info("No thumbnail generated yet.")

        if manifest.production_mode == "Auto" or st.button("🎨 Generate Mock Thumbnail", key="gen_thumb"):
            with st.spinner("Generating thumbnail…"):
                generate_mock_thumbnail_16x9(thumb_16x9, manifest.project_name, manifest.theme)
                manifest.visual.youtube_thumbnail_path = str(thumb_16x9)
                manifest.visual.youtube_thumbnail_16x9 = True
                manifest.visual.updated_at = datetime.now(timezone.utc).isoformat()
                _save(manifest)
            st.success("Thumbnail generated!")
            st.rerun()

    # ── DSP Cover 1:1 ─────────────────────────────────────────────────────────
    with col_cover:
        st.markdown("#### DSP Cover Art (1:1 · 3000×3000)")
        if cover_1x1.exists():
            st.image(str(cover_1x1), use_container_width=True)
            st.success("✅ 3000×3000 placeholder ready")
        else:
            st.info("No cover generated yet.")

        if manifest.production_mode == "Auto" or st.button("🎨 Generate Mock Cover", key="gen_cover"):
            with st.spinner("Generating cover…"):
                generate_mock_cover_1x1(cover_1x1, manifest.project_name, manifest.theme)
                manifest.visual.dsp_cover_path = str(cover_1x1)
                manifest.visual.dsp_cover_1x1 = True
                manifest.visual.updated_at = datetime.now(timezone.utc).isoformat()
                _save(manifest)
            st.success("Cover generated!")
            st.rerun()

    st.divider()

    # ── Manual Upload Override ────────────────────────────────────────────────
    st.markdown("#### 📤 Manual Upload Override")
    col_up1, col_up2 = st.columns(2)

    with col_up1:
        up_thumb = st.file_uploader("Upload YouTube Thumbnail (PNG/JPG)", type=["png", "jpg", "jpeg"],
                                     key="upload_thumb")
        if up_thumb:
            thumb_16x9.write_bytes(up_thumb.read())
            manifest.visual.youtube_thumbnail_path = str(thumb_16x9)
            manifest.visual.youtube_thumbnail_16x9 = True
            _save(manifest)
            st.success("Thumbnail uploaded.")
            st.rerun()

    with col_up2:
        up_cover = st.file_uploader("Upload DSP Cover (PNG/JPG 3000×3000)", type=["png", "jpg", "jpeg"],
                                     key="upload_cover")
        if up_cover:
            cover_1x1.write_bytes(up_cover.read())
            manifest.visual.dsp_cover_path = str(cover_1x1)
            manifest.visual.dsp_cover_1x1 = True
            _save(manifest)
            st.success("Cover uploaded.")
            st.rerun()

    st.divider()

    # ── Flow / Nano Banana Prompts ─────────────────────────────────────────────
    with st.expander("🔮 Visual Director Prompts (for Flow / Nano Banana)", expanded=False):
        thumb_prompt = (
            f"City pop album art, Tokyo-Seoul aesthetic, "
            f"night city rooftop, neon reflections on wet street, "
            f"1990s Japanese urban mood, no text, no logo, no watermarks, "
            f"16:9 landscape, cinematic, {manifest.theme or 'late night drive'}"
        )
        cover_prompt = (
            f"City pop album cover, elegant square format, "
            f"sophisticated urban woman at night, neon cityscape, "
            f"1990s Japanese-inspired, moody color palette, "
            f"no text, no logo, no watermark, 1:1 square"
        )
        (flow_dir / "youtube_thumbnail_prompt.txt").write_text(thumb_prompt, encoding="utf-8")
        (flow_dir / "dsp_cover_prompt.txt").write_text(cover_prompt, encoding="utf-8")
        st.text_area("Thumbnail Prompt (16:9)", value=thumb_prompt, height=100, disabled=True)
        st.text_area("Cover Prompt (1:1)", value=cover_prompt, height=100, disabled=True)
        st.caption("Prompts saved to 02_thumbnail_cover/flow_prompts/")

    # ── Canva guide ───────────────────────────────────────────────────────────
    with st.expander("🖼 Canva Text Overlay Guide", expanded=False):
        st.markdown("""
**YouTube Thumbnail Rules:**
- Add title text in large, high-contrast font
- Seoul Records watermark bottom-left (small)
- CTR-focused: bold, readable at small size

**DSP Cover Rules:**
- NO text overlays
- NO URLs, QR codes, social handles
- NO brand logos or third-party imagery
- Clean, metadata-safe artwork only
        """)

    # Mark step complete
    if manifest.visual.youtube_thumbnail_16x9 and manifest.visual.dsp_cover_1x1:
        manifest.visual.status = "completed"
        if manifest.status in (ProjectStatus.SONG_GENERATION_COMPLETED, ProjectStatus.THUMBNAIL_READY):
            manifest.update_status(ProjectStatus.THUMBNAIL_COMPLETED)
        _save(manifest)
        log_action(output_folder, "thumbnail", "step_completed",
                   {}, project_id=manifest.project_id)
        st.success("✅ Both assets ready — step complete.")
