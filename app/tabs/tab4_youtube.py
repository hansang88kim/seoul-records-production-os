"""
Seoul Records Production OS — Tab 4: YouTube Upload
"""
from pathlib import Path
import streamlit as st
from app.project_manager import save_manifest, log_action
from workflows.export_youtube_package import export_youtube_package, generate_youtube_metadata


def _get_folder() -> Path:
    return Path(st.session_state.current_output_folder)


def _get_manifest():
    return st.session_state.current_project


def _save(manifest):
    st.session_state.current_project = manifest
    save_manifest(manifest, _get_folder())


def render_tab_youtube():
    manifest = _get_manifest()
    output_folder = _get_folder()
    st.markdown("## ▶️ YouTube Upload")
    st.caption("Generate upload package · Private by default · Manual publish")

    approved = manifest.approved_tracks()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Tracks Ready", len(approved))
    with col2:
        video_path = output_folder / "03_longform_video" / "output" / "final_video.mp4"
        st.metric("Video", "✅" if video_path.exists() else "⏳")
    with col3:
        thumb_path = output_folder / "02_thumbnail_cover" / "final" / "youtube_thumbnail_16x9.png"
        st.metric("Thumbnail", "✅" if thumb_path.exists() else "⏳")

    if not approved:
        st.warning("⚠️ No completed tracks. Finish Song Generation first.")
        return

    st.divider()

    # Preview metadata
    with st.expander("👁 Preview YouTube Metadata", expanded=True):
        preview = generate_youtube_metadata(manifest, output_folder)
        st.text_input("Title", value=preview["title"], disabled=True)
        st.text_area("Description", value=preview["description"], height=300, disabled=True)
        st.text_input("Tags", value=", ".join(preview["tags"][:10]), disabled=True)
        st.text_input("Hashtags", value=" ".join(preview["hashtags"]), disabled=True)

    st.divider()
    st.warning("🔒 Auto upload will always upload as **Private**. Public release is manual.")

    col_export, col_upload = st.columns(2)

    with col_export:
        if st.button("📦 Export Upload Package", type="primary", use_container_width=True):
            with st.spinner("Exporting YouTube package…"):
                zip_path = export_youtube_package(manifest, output_folder)
                _save(manifest)
            st.success(f"✅ Package exported: `{zip_path.name}`")
            with open(zip_path, "rb") as f:
                st.download_button(
                    label="⬇️ Download ZIP",
                    data=f,
                    file_name=zip_path.name,
                    mime="application/zip",
                    use_container_width=True,
                )

    with col_upload:
        st.button(
            "▶️ Upload to YouTube (Private)",
            use_container_width=True,
            disabled=True,
            help="YouTube API upload coming in v0.5",
        )
        st.caption("Coming in v0.5 — YouTube Data API integration")

    # File listing
    st.divider()
    yt_root = output_folder / "04_youtube_upload"
    if yt_root.exists():
        with st.expander("📁 Package Contents", expanded=False):
            meta_dir = yt_root / "metadata"
            for file in sorted(meta_dir.rglob("*")):
                if file.is_file():
                    st.caption(f"📄 `{file.relative_to(output_folder)}`")
