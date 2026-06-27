"""
Seoul Records Production OS — Tab 5: Music Distribution
"""
from pathlib import Path
import streamlit as st
from app.project_manager import save_manifest, log_action
from agents.qc_agent import qc_distribution
from workflows.export_distribution_package import export_distribution_package


def _get_folder() -> Path:
    return Path(st.session_state.current_output_folder)


def _get_manifest():
    return st.session_state.current_project


def _save(manifest):
    st.session_state.current_project = manifest
    save_manifest(manifest, _get_folder())


def render_tab_distribution():
    manifest = _get_manifest()
    output_folder = _get_folder()
    st.markdown("## 📦 Music Distribution")
    st.caption("UnitedMasters · WAV masters · Rights statements · Distribution package")

    approved = manifest.approved_tracks()
    wav_tracks = [t for t in approved if t.is_wav]
    mp3_only = [t for t in approved if not t.is_wav and t.selected_wav_path]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("WAV Masters", len(wav_tracks))
    with col2:
        st.metric("MP3-Only (blocked)", len(mp3_only), delta=None,
                   help="MP3 tracks cannot be distributed. WAV required.")
    with col3:
        cover_path = output_folder / "02_thumbnail_cover" / "final" / "dsp_cover_3000x3000.png"
        st.metric("Cover Art", "✅" if cover_path.exists() else "❌")

    # Distribution rules reminder
    with st.expander("📋 Distribution Rules", expanded=False):
        st.markdown("""
**WAV-First Policy:**
- ✅ WAV 16-bit 44.1kHz stereo required
- ❌ MP3 files not eligible for distribution
- ❌ MP3-to-WAV conversion not allowed as distribution master
- ❌ YouTube draft MP3 preview not eligible

**Cover Art:**
- 3000×3000 JPEG or PNG
- No text, no URL, no QR codes
- No social handles, no brand logos
- No third-party stock imagery
        """)

    if mp3_only:
        st.error(
            f"❌ {len(mp3_only)} track(s) have MP3 only. "
            "Distribution package is partially blocked. "
            "Manual import of WAV required for these tracks."
        )

    if not wav_tracks:
        st.warning("⚠️ No WAV masters available. Complete Song Generation first.")
        return

    if manifest.distribution.blocked_reason:
        st.error(f"🚫 {manifest.distribution.blocked_reason}")

    st.divider()

    # QC check
    warnings = qc_distribution(manifest.distribution, approved)
    if warnings:
        with st.expander(f"⚠️ QC Warnings ({len(warnings)})", expanded=True):
            for w in warnings:
                st.warning(f"• {w}")

    # Export
    if st.button("📦 Export Distribution Package", type="primary", use_container_width=True):
        with st.spinner("Building UnitedMasters package…"):
            zip_path, pkg_warnings = export_distribution_package(manifest, output_folder)
            _save(manifest)

        if zip_path:
            st.success(f"✅ Package ready: `{zip_path.name}`")
            with open(zip_path, "rb") as f:
                st.download_button(
                    label="⬇️ Download Distribution ZIP",
                    data=f,
                    file_name=zip_path.name,
                    mime="application/zip",
                    use_container_width=True,
                )
        else:
            st.error("❌ Package export blocked. Check WAV masters.")

        if pkg_warnings:
            for w in pkg_warnings:
                st.warning(f"⚠️ {w}")

    st.divider()

    # Contents preview
    dist_root = output_folder / "05_music_distribution" / "unitedmasters"
    if dist_root.exists():
        with st.expander("📁 Package Contents", expanded=True):
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Audio Masters**")
                audio_dir = dist_root / "audio"
                if audio_dir.exists():
                    for f in sorted(audio_dir.iterdir()):
                        if f.is_file():
                            size_kb = f.stat().st_size // 1024
                            st.caption(f"🎵 `{f.name}` ({size_kb:,} KB)")
                else:
                    st.caption("No audio files yet.")
            with col_b:
                st.markdown("**Rights Statements**")
                rights_dir = dist_root / "rights"
                if rights_dir.exists():
                    for f in sorted(rights_dir.iterdir()):
                        if f.is_file():
                            st.caption(f"📄 `{f.name}`")
                else:
                    st.caption("No rights files yet.")

            st.markdown("**Metadata**")
            meta_dir = dist_root / "metadata"
            if meta_dir.exists():
                for f in sorted(meta_dir.iterdir()):
                    if f.is_file():
                        st.caption(f"📊 `{f.name}`")

    # Checklist
    with st.expander("✅ Upload Checklist", expanded=False):
        checklist_path = dist_root / "metadata" / "upload_checklist.md" if dist_root.exists() else None
        if checklist_path and checklist_path.exists():
            st.markdown(checklist_path.read_text(encoding="utf-8"))
        else:
            st.caption("Export package first to see checklist.")

    # Playwright note
    st.divider()
    st.info("🤖 **v0.6 Roadmap:** UnitedMasters web-assisted upload with Playwright — stops before final Submit.")
