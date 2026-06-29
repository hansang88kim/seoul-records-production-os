# Seoul Records Production OS

**AI Music Label Production Harness — v0.8.0**

> Creative direction: controlled by ChatGPT and the user.
> Engineering: this repository.
> Creative prompt generation is placeholder and will later be controlled by ChatGPT.

---

## What's New in v0.2.0## What's New in v0.2.0

### Manual WAV Import Pipeline
- **Tab 1 — Song Generation**: Manual WAV Import section fully rebuilt
  - Upload Candidate A / B or Selected WAV directly
  - Files saved to the **correct track folder only** (no cross-track overwrite)
  - Instant Audio QC display (duration / sample rate / channels / codec / method)
  - `project_manifest.json` updated + `project_log.jsonl` appended on every import
  - Candidate A/B selection policy applied automatically → `suno_master.wav` created

### Audio QC (`workflows/audio_qc.py`)
- ffprobe → wave module → mutagen fallback chain
- **Fake WAV detection**: MP3 data inside `.wav` extension is caught via magic-byte check
- MP3 allowed for YouTube draft preview only; distribution blocked
- `AudioQCResult` dataclass with full metadata

### Distribution Master (`workflows/create_distribution_master.py`)
- Source must be confirmed PCM WAV — fake WAV, MP3, AAC all strictly blocked
- Source already at 44.1 kHz / 16-bit / stereo → simple copy
- Off-spec WAV → FFmpeg lossless conversion
- FFmpeg absent → `manual_required`, no crash

### FFmpeg Longform Rendering (enhanced)
- `final_audio_mix.wav` generated alongside `final_video.mp4`
- Better error capture (returncode + stderr in log)
- Graceful `manual_required` when FFmpeg is missing

### Project Library
- Landing page "Open Existing Project" panel rebuilt
- Shows 5-step status icons (Song Gen / Thumbnail / Video / YouTube / Distribution)
- Sort by Newest / Oldest / Name, Resume button
- **Not a 6th tab** — 5-tab production console preserved

### Distribution Warning Fix
- QC now runs **after** metadata, rights, cover, and audio are all generated
- Eliminates false `metadata_not_ready` / `rights_statements_missing` warnings

---

## What This Is

Seoul Records Production OS is a local MVP application for creating AI-generated city pop album projects. It provides a full 5-tab production pipeline from song generation through music distribution, with mock providers for v0.1.x and a clear upgrade path to real integrations.

**v0.8.0: YouTube Package Studio — a new top tab builds a complete YouTube upload package from final_video.mp4 + youtube_thumbnail_16x9 + chapters.txt. Generates title/description/tags/hashtags/pinned comment + a copy-ready chapters section (Korean preserved, no mojibake), validates the thumbnail (16:9, ≤2MB, compresses over-size into a separate upload-ready file without overwriting the original), writes a YouTube upload payload (privacyStatus private by default), an upload checklist, package_manifest.json, and an optional manual_upload_package.zip. Upload mode defaults to Manual Package Only; optional API upload is private-default and uses a mock client (no real API calls, OAuth tokens/Authorization headers always redacted). Music generation, Thumbnail Studio, and Video Renderer are untouched.**

**v0.7.5: Render Cancel Race Fix — a cancel requested immediately after Full Render is never lost. update_render_state refuses to overwrite a cancelling/cancelled status with running, and the worker checks for cancellation before flipping to running, before launching FFmpeg, and right after Popen — so a pre-start cancel marks the job cancelled without ever launching FFmpeg (files preserved).**

**v0.7.4: Render Cancel + Job History — Cancel Render button flips status to cancelling; the worker polls it, terminates FFmpeg, and marks the job cancelled (output/log/plan files are never deleted). render_state.json now tracks worker_pid and ffmpeg_pid separately, render_job_id carries a microsecond+uuid suffix (no same-second collisions), and a Render Job History panel lists running/completed/failed/cancelled jobs with Open Folder / View Log. Long renders run without a timeout and the progress panel recovers the active job from disk after any rerun.**

**v0.7.3: Video Render Worker + Visualizer Controls — full-length renders run in a detached background worker (Streamlit never blocks) with live FFmpeg progress (percent/time/speed/ETA via -progress pipe:1) persisted to outputs/video_renderer/jobs/. Visualizer y-position, height, width%, opacity, and glow are configurable and reflected in the real filter_complex; the Canva frame locks to the visualizer position. Previews still run inline.**

**v0.7.2: Overlay Composition — the Video Renderer now compiles overlay_plan into a real FFmpeg -filter_complex, so preview/full MP4s actually contain the audio-reactive visualizer (driven by the real audio input), Canva visualizer frame, per-track Now Playing cards (scheduled by chapter), and CTA stickers (every 5 min). Supports uploading Canva-exported PNGs (with mock fallback) and a Preview-CTA-Now option.**

**v0.7.1: MP3-first Video Renderer + Canva Asset Overlay — Video Renderer now works from MP3 alone (no WAV required, no fake WAV). Scans outputs/ for MP3s, builds 60/65/70-min playlists with repeat-until-target, prefers the clean video_playback_background, and composites Canva PNG overlays (Now Playing card, CTA sticker, visualizer frame) with an audio-reactive waveform. Includes 15s/30s/full preview renders.**

**v0.7.0: Output Asset Separation — Thumbnail Studio now exports 3 distinct deliverables: YouTube Thumbnail 16:9 (광고판), Video Playback Background 16:9 (무대, clean/no center title), and Streaming Cover 1:1 (앨범 자켓, derived from thumbnail). Includes a 1:1 crop tool and asset_manifest.json. Video Renderer prefers the clean playback background.**

**v0.6.0: Thumbnail Studio — Google Flow prompt batches, candidate gallery, and selected-image Canva branding for citypop YouTube thumbnails. Independent of music generation.**

**v0.5.0: Local WAV import pipeline — no real Suno, Canva, YouTube, or UnitedMasters APIs. Manual WAV import → FFmpeg render → Distribution package.**

**Core creative identity: Seoul Records City Pop Core**
- Japanese nostalgic city pop, sophisticated 1990s urban feeling
- Low, thick female vocal · Elegant night-city mood
- No sax lead · No drum fills · No EDM · No trot · No enka

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/seoul-records/seoul-records-production-os
cd seoul-records-production-os

# 2. Python environment (3.11+)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Edit .env — set COMPOSER_PROVIDER=mock for v0.1.x

# 5. Run
streamlit run app/main.py
```

---

## Project Structure

```
seoul-records-production-os/
├── app/
│   ├── main.py              # Streamlit entry point
│   ├── dashboard.py         # Tab router + sidebar
│   ├── config.py            # All configuration
│   ├── models.py            # Pydantic data models
│   ├── state_machine.py     # ProjectStatus + TrackStatus enums
│   ├── project_manager.py   # Create / resume / log / save
│   ├── orchestrator.py      # Full pipeline runner
│   └── tabs/
│       ├── project_screen.py       # New / Resume project
│       ├── tab1_song_generation.py # Song prompts, Suno, WAV import
│       ├── tab2_thumbnail.py       # 16:9 thumbnail, 1:1 cover
│       ├── tab3_video.py           # FFmpeg timestamps & render
│       ├── tab4_youtube.py         # YouTube metadata package
│       └── tab5_distribution.py    # UnitedMasters distribution
│
├── agents/
│   ├── producer_agent.py    # Prompt generation from presets
│   └── qc_agent.py         # QC checks + candidate selection
│
├── providers/
│   └── suno/
│       ├── __init__.py               # Central provider registry
│       ├── base.py                   # ComposerProvider ABC
│       ├── mock_suno.py              # MockSunoProvider (fast_mode)
│       ├── manual_import.py          # ManualImportProvider
│       ├── local_unofficial_suno.py  # Stub — v0.3
│       ├── playwright_suno_web.py    # Stub — v0.3
│       └── third_party_suno.py       # Stub — disabled by default
│   └── image/
│       └── mock_image.py    # Mock thumbnail/cover generator (Pillow)
│
├── presets/
│   ├── core/
│   │   └── seoul_records_citypop_core.json
│   ├── language_packs/
│   │   └── ko_kr_seoul.json
│   └── themes/
│       ├── late_night_drive.json
│       ├── rainy_city.json
│       ├── summer_farewell.json
│       └── soft_romance.json
│
├── workflows/
│   ├── generate_album.py
│   ├── render_video.py
│   ├── export_youtube_package.py
│   ├── export_distribution_package.py
│   └── validate_package_zip.py   # Zip cleanliness validator
│
├── scripts/
│   └── clean_package.sh          # Build + validate clean zip
│
├── tests/                        # pytest test suite (8 files)
└── outputs/                      # Generated projects (gitignored)
```

---

## Production Tabs

| Tab | Purpose | v0.8.0 Status |
|-----|---------|---------------|
| 🎵 Song Generation | Prompt generation, mock Suno, WAV import, candidate selection | ✅ Mock + Manual Import |
| 🖼 Thumbnail & Cover | 16:9 YouTube thumbnail + 1:1 DSP cover | ✅ Mock (Pillow) |
| 🎬 Longform Video | FFmpeg timestamps, chapters, render command | ✅ Command export |
| ▶️ YouTube Upload | Metadata, description, tags, package ZIP | ✅ Package export |
| 📦 Distribution | WAV masters, rights, cover, UnitedMasters ZIP | ✅ Package export |

---

## Composer Provider System

All providers implement `ComposerProvider` (defined in `providers/suno/base.py`).
The single registry lives in `providers/suno/__init__.py`.

```
COMPOSER_PROVIDER=mock              → MockSunoProvider (v0.1.x default, fast_mode)
COMPOSER_PROVIDER=manual_import     → ManualImportProvider (upload WAV directly)
COMPOSER_PROVIDER=local_unofficial  → LocalUnofficialSunoProvider (stub, v0.3)
COMPOSER_PROVIDER=playwright_web    → PlaywrightSunoWebProvider (stub, v0.3)
COMPOSER_PROVIDER=third_party       → ThirdPartySunoProvider (disabled by default)
```

**MockSunoProvider (v0.1.3):** fast_mode=True generates tiny (~500 KB) valid WAV files while simulating 3:30-4:00 metadata durations for candidate selection testing. Set fast_mode=False for full-length sine-wave audio.

**ManualImportProvider:** Upload WAV files via the Song Generation tab UI. Validates format, reads duration, and sets distribution eligibility.

**WAV-first policy:** Always prefer WAV. MP3 is preview-only. MP3 distribution is blocked by default.

---

## Candidate Selection Policy

Each Suno request returns 2 candidates. Selection rules (target: 3:30–4:00):

1. Both in range → select longer, save WAV
2. One in range → select that one
3. Both short → select longer, warn, save WAV
4. Both exceed 4:00 (strict_duration=True) → set REGENERATION_REQUIRED, do NOT save WAV
5. Mixed → select longer, warn, save WAV

---

## Running Tests

```bash
# Standard test run (recommended)
PYTHONDONTWRITEBYTECODE=1 pytest tests/ -v -p no:cacheprovider

# Or simply
pytest tests/ -v

# Validate a packaged zip
python workflows/validate_package_zip.py dist/seoul-records-production-os-v0.1.3.zip
```

Test files:
- `test_project_creation.py` — folder structure, manifest, tracks
- `test_manifest_schema.py` — Pydantic model serialization, exclude_styles list
- `test_song_generation_mock.py` — MockSunoProvider, WAV, full workflow
- `test_candidate_selection.py` — all selection policy cases
- `test_folder_structure.py` — all step subfolders
- `test_distribution_block_mp3.py` — MP3 block, cover art copy
- `test_youtube_package.py` — thumbnail, video_path.txt, chapters
- `test_package_cleanliness.py` — source code structural checks

---

## Building a Clean Package

```bash
bash scripts/clean_package.sh 0.1.2
# → dist/seoul-records-production-os-v0.1.3.zip
```

The script cleans caches, builds the zip, and runs `validate_package_zip.py` automatically. Exits non-zero if any validation fails.

---

## Language Pack Expansion

Add new markets by creating a JSON file in `presets/language_packs/`:

```json
{
  "pack_id": "ja_jp_tokyo",
  "language": "Japanese",
  "city": "Tokyo",
  "metadata": { "generate_original": true }
}
```

No backend code changes required. Planned packs:
`ja_jp_tokyo` · `vi_vn_saigon` · `th_th_bangkok` · `zh_tw_taipei` · `yue_hk_hongkong` · `zh_cn_mainland` · `id_id_jakarta` · `ms_my_kualalumpur` · `tl_ph_manila` · `hi_in_mumbai`

> HK must use Cantonese + Traditional Chinese. Do not write Mandarin for HK.
> Always generate original lyrics in the target language. Never translate from Korean.

---

## Roadmap

| Version | Focus | Status |
|---------|-------|--------|
| v0.1.3 | Clean package, fast tests, manual WAV import, safe candidate override | ✅ Released |
| v0.2.0 | Manual WAV import UI, Audio QC (ffprobe/wave), Distribution Master, FFmpeg render, Project Library | ✅ Released |
| v0.2.1 | FFmpeg audio concat absolute path fix, duration warning UI | ✅ Released |
| v0.3.0 | LocalUnofficialSunoProvider, provider capability system, Playwright skeleton | ✅ Released |
| v0.3.1 | Provider research matrix, pyproject.toml dependency fix | ✅ Released |
| v0.3.2 | Suno one-song dry-run, endpoint mapping, credential safety | ✅ Released |
| v0.3.3 | Windows test compatibility hotfix | ✅ Released |
| v0.3.4 | Real dry-run result, provider fallback hardening | ✅ Released |
| v0.4.0 | SunoCliProvider (paperfoot/suno-cli subprocess adapter) | ✅ Released |
| v0.4.1 | SunoCliProvider docs, dry-run suno_cli support | ✅ Released |
| v0.4.2 | SunoCliProvider fixes, real dry-run success | ✅ Released |
| v0.5.0 | Song Lab UX redesign, Quick Single mode, Korean UI | ✅ Current |
| v0.3 | LocalUnofficialSunoProvider (user's own Suno credits) | Planned |
| v0.4 | Flow / Nano Banana image, Canva MCP template design | Planned |
| v0.5 | YouTube private upload (YouTube Data API v3) | Planned |
| v0.6 | UnitedMasters web-assisted upload (Playwright, stops before Submit) | Planned |

---

## Security Notes

- Never commit `.env`, cookies, tokens, or Suno credentials
- `ThirdPartySunoProvider` is disabled by default (`ALLOW_THIRD_PARTY_SUNO=false`)
- Playwright mode must stop if human verification (CAPTCHA/2FA) appears
- Auto upload is always private — public release is always manual

---

## License

Seoul Records internal project. All rights reserved.
