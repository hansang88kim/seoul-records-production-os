# Seoul Records Production OS

**AI Music Label Production Harness — v1.0.0-alpha.13**

> Creative direction: controlled by ChatGPT and the user.
> Engineering: this repository.
> Creative prompt generation is placeholder and will later be controlled by ChatGPT.

---


## Running the app

**Python / Streamlit backend (current stable, legacy/admin fallback):**
```
pip install -r requirements.txt
streamlit run app/main.py
```

**Next.js Frontend (v1.0.0-alpha.1 — modern dark Studio Console):**
```
cd frontend
npm install
npm run dev        # http://localhost:3000
npm run build
npm run typecheck
npm run lint
```

The Next.js console runs **in parallel** with Streamlit. It shares the same
`outputs/` folder and Python services via a sanitized snapshot bridge
(`api/snapshot.py`) that never returns tokens/cookies/keys. v1.0.0-alpha.1 is the
frontend **shell + read-only dashboard + route structure + mock/API-ready UI**
stage; Streamlit remains the legacy/admin fallback. Set `NEXT_PUBLIC_API_BASE`
to point the console at a live backend.


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

**v1.0.0-alpha.13: Country-Based Title Block (12 languages) — The thumbnail title block is now a fixed, auto-filled 4-line layout: SEOUL RECORDS (eyebrow) → main title (country/city, e.g. TOKYO, biggest) → local-language "night music" line (夜の音楽 / 밤의 음악 / ดนตรียามค่ำคืน / रात का संगीत …) → CityPop Playlist (bottom). All three text lines auto-fill from the selected country via a new TITLE_DEFAULTS map (get_title_defaults) and stay editable in the Brand Thumbnail + Exports tabs. The local line is rendered with a script-aware font (CJK→Noto Sans KR, Thai→Noto Sans Thai, Devanagari→Noto Sans Devanagari, otherwise Latin→Montserrat); Thai/Devanagari use the RAQM layout engine and whole-string drawing so marks/conjuncts shape correctly. Bundled Noto Sans Thai + Devanagari. Tests +4; 671 passing, clean under -X warn_default_encoding.**

**v1.0.0-alpha.12: TOKYO-Style Hanja/Hangul Sub-line — Adds the reference-channel "TOKYO / 東京" look: an optional CJK sub-line (cjk_subtext) sits just under the bold English title, a little smaller, in the same color. Free text — type 시티팝 / 音楽 / 夜 etc. Rendered with a bundled Noto Sans KR (weight-set, covers Hangul + common Hanja/Kanji). The title block is now laid out as an auto-spaced vertical stack (eyebrow → divider → title → CJK line → subtitle) so nothing overlaps at any size. Wired through the branded thumbnail and all exports, with a 한자/한글 서브텍스트 field in the Brand Thumbnail and Exports tabs. Tests +3; 667 passing, clean under -X warn_default_encoding.**

**v1.0.0-alpha.11: Title Color Picker + Size Control + Bigger Default — render_premium_thumbnail gains title_color (hex) and title_scale (multiplier), threaded through the branded thumbnail and all exports (YouTube thumbnail, 1:1 streaming cover, export-all). The Brand Thumbnail and Exports tabs now show a 제목 색상 color picker (default white) and a 제목 크기 slider (0.8–1.6). Base title size bumped (~18% larger) and the default scale is 1.10, so titles are bigger out of the box. Tests +3; 664 passing, clean under -X warn_default_encoding.**

**v1.0.0-alpha.10: Bold English Title — Title font is now Montserrat Black (900) for a strong, punchy look, and the default playlist title is "CityPop Playlist" (no "Vol.1"; still freely editable). Titles are English-only: the Pretendard Korean face is removed; any incidental Hangul (e.g. the optional 구독/좋아요 stickers) falls back to an OS CJK font. Tests updated; 661 passing, clean under -X warn_default_encoding.**

**v1.0.0-alpha.9: Thumbnail Typography & Polish — Refines the premium thumbnail look. Title font is now bundled Montserrat (the clean geometric sans most YouTube music channels use), with Pretendard auto-selected for Korean titles — both bundled under assets/fonts/ so rendering is identical on every OS (no reliance on system fonts). The title outline/glow is removed in favour of a single soft drop shadow (no border). The gap between the title and subtitle is widened for a more editorial layout, and the vignette/darken is softened so backgrounds read more naturally. Generation prompts re-tuned toward a tasteful, understated, muted-cinematic palette (less garish neon). Sticker labels (구독/좋아요) are now Hangul-aware. Tests +1; 661 passing, clean under -X warn_default_encoding.**

**v1.0.0-alpha.8: Premium Minimal Thumbnails + Count Input + Higher Quality — A visual overhaul of the thumbnail/deliverable rendering toward a 10만+ music-channel look. New shared `render_premium_thumbnail`: a cinematic, vignetted background with a clean CENTER-aligned title block (letter-spaced eyebrow + thin divider + title + subtitle), no clutter, output at full HD (1920x1080; 3000x3000 for the 1:1 cover). The branded thumbnail AND all three deliverables (YouTube thumbnail, video background, streaming cover) now share it, so they are consistent and the cover no longer crops the title. CTA stickers (equalizer / 구독 / 좋아요) are now OFF by default and optional. The Prompt Lab "Volume 번호" field is replaced by a "생성 개수" count (type 5 -> 5 images); the 1/5/10 radio is removed. Generation prompts strengthened with cinematic / 35mm film / shallow DoF / volumetric lighting / HDR / 4K / detail boosters for higher-quality Gemini output. Cross-platform CJK fonts throughout so Korean titles render. Tests +8; 660 passing, clean under -X warn_default_encoding.**

**v1.0.0-alpha.7: Auto-Composite YouTube Thumbnails (Stickers) — The branding step now produces a FINISHED YouTube thumbnail locally with PIL — no Canva subscription or template needed. On top of the title/subtitle/brand layout it auto-draws YouTube stickers: a citypop-tinted equalizer/visualizer, a red 구독 (subscribe) pill with a play triangle, and an outlined ♥ 좋아요 (like) pill — each toggleable in Brand Thumbnail, plus a center-title layout option. Fonts are now cross-platform and CJK-capable (Windows 맑은 고딕 / Linux Noto Sans CJK / macOS), so Korean titles and sticker text render correctly instead of falling back to a tiny box-glyph default (this also fixes the small/garbled title text seen earlier). The mock placeholder image generator uses the same CJK fonts. The old "Mock Canva" mode is renamed "🎬 자동 합성 (앱 내 렌더링)". Tests +7 (render, Korean text, sticker flags, layouts, helper drawing); 652 passing, clean under -X warn_default_encoding.**

**v1.0.0-alpha.6: Real Image Generation — Sidebar Key + No-Install REST — Fixes two blockers for real thumbnail generation. (1) The image provider now reads the SAME key the app's sidebar stores (`GOOGLE_GEMINI_API_KEY`), so the Gemini key entered in the left panel is picked up automatically — previously it only checked `GEMINI_API_KEY` and ignored the sidebar key. (2) A new `requests`-only REST backend (`GeminiRestImageProvider`, mirroring the app's existing Gemini REST calls) is now the default, so real generation works with just an API key — no `pip install google-genai` needed. The SDK backend is still available via `SEOUL_IMAGE_BACKEND=sdk` (required for Imagen). Readiness now depends on the key alone; the toggle activates as soon as a key is present. Keys are redacted from all error messages. Tests +3 (16 total in this suite, 645 overall); no real network calls in tests. NOTE: if you still hit the `create_session() project_folder` TypeError, you are running stale files from a OneDrive ZIP copy — run from a clean `git clone`, where pulled files stay consistent.**

**v1.0.0-alpha.5: Thumbnail Studio — Inline Image Preview — Prompt Lab now renders the generated thumbnails inline (a grid right under the generate button) instead of only listing prompt text, so "generate → see images" happens on one screen without switching to the Candidate Gallery tab. Failed generations surface their error inline, and mock outputs show a hint on how to enable real Gemini generation. Pure UI; backend + tests unchanged (642 passing).**

**v1.0.0-alpha.4: Thumbnail Studio — Project Linking + Real Image Generation — Thumbnail Studio can now bind to a Song Lab project, so generated images save into that project's `thumbnails/` folder, kept separate from audio in `songs/` (same project directory, separate subfolders). Prompt Lab's batch (1/5/10) no longer just emits prompt text — it renders ACTUAL images through a provider abstraction: a zero-cost PIL mock by default, or the OFFICIAL Google Gemini API ("Nano Banana" = gemini-2.5-flash-image; Imagen 4 also supported) when "use real images" is enabled and `google-genai` + a `GEMINI_API_KEY` are present (Google Flow has no official developer API; we use the same underlying image model via the official Gemini API — API-key auth only, no browser automation, no CAPTCHA solving, key never logged). Country/theme/volume drive the prompts. Generated images flow straight into the existing Candidate Gallery → select → Brand Thumbnail (Canva) pipeline. New modules `services/thumbnail/image_provider.py` + `image_gen_deps.py`; `session_store` gains project binding + `generate_images`. 13 new mock-only tests (no network). `pip install google-genai` (or the `imagegen` extra) enables the real path.**

**v1.0.0-alpha.3: Korean Windows (cp949) Hardening + Deterministic Job Ordering — every file read/write/open and every text-mode subprocess capture now pins `encoding="utf-8"` (subprocess also `errors="replace"`), so the app and the full test suite run cleanly on Korean Windows, where the locale default is cp949 (previously Korean paths, em-dashes, and UTF-8 JSON tripped UnicodeDecodeError). `list_jobs` now orders newest-first by the microsecond `created_at` timestamp (with `job_id` tiebreaker) instead of filesystem mtime, which on NTFS could tie within one coarse tick and flip the order. Proven clean under `python -X warn_default_encoding -W error::EncodingWarning` across all 629 tests; production file I/O has zero locale-default calls. No behavior change beyond encoding/ordering.**

**v1.0.0-alpha.1: Frontend Modernization — a parallel, modern dark-theme Studio Console under frontend/, built with Next.js 15 (App Router, React 19), TypeScript (strict, @/* alias), Tailwind CSS v4, and shadcn/ui components. Hybrid strategy (Option C): the existing Streamlit app is untouched and remains the legacy/admin fallback; the Next.js console shares the same outputs/ folder and Python services via a sanitized, framework-free snapshot bridge (api/snapshot.py) that never returns tokens/cookies/keys. Routes: Dashboard + Song Lab / Thumbnail Studio / Video Renderer / YouTube Package / Production QA / UnitedMasters / Remote Control / Settings, with a responsive sidebar+topbar shell, design tokens (cyan/magenta/amber accents), and read-only status pages wired to a mock-first typed API. No backend regressions.**

**v0.9.2: Telegram Runtime Dependency Fix — declares python-telegram-bot>=21.0 in requirements.txt and pyproject.toml (plus a `remote` optional extra) so the real Telegram long-poll bot works after `pip install -r requirements.txt`. A runtime dependency check (is_telegram_package_installed / check_telegram_dependency) surfaces install status in the Production QA remote-control panel, and run_polling degrades clearly with an install hint when the package is missing — the supervisor and all other features keep working. Tokens/chat_ids remain hidden from UI and logs.**

**v0.9.1: Remote Control Plane + Supervisor Watchdog — a separate supervisor process watches the Streamlit frontend (HTTP health check on 127.0.0.1:8501), restarts it when down with a per-hour restart-loop guard, summarizes active jobs, and writes supervisor_status.json. A Telegram control bot (disabled unless TELEGRAM_BOT_TOKEN + TELEGRAM_ALLOWED_CHAT_IDS are set) accepts a fixed allowlist of management commands only (/status, /app, /restart_app, /jobs, /render, /youtube, /qa, /tail, /help) — there is NO shell/exec command, only whitelisted chat_ids may issue commands, and every response is redacted so no token/cookie/secret is ever exposed. Restart matches the app/main.py command line carefully and never kills the render/upload workers. Windows Task Scheduler scripts register the supervisor at logon. Read-only remote-control status panel added to Production QA. Tailscale is used for frontend access via a guide (not required).**

**v0.9.0: UnitedMasters Distribution Package Studio — a new UnitedMasters tab builds a manual-upload distribution package from the Video Renderer playlist order + streaming_cover_1x1. MP3 is included as source/draft audio (distribution_ready=false); WAV/FLAC masters (attached by path or found beside the MP3) flip tracks to Distribution Ready. No fake WAV is ever created, source MP3s are never deleted, and there is no credential storage or CAPTCHA bypass — manual upload workflow only. Produces tracklist CSV/JSON, release_metadata.json, cover (+ upload-ready), MP3 references, distribution masters when provided, and a manual upload checklist. Production QA now includes UnitedMasters readiness (MP3-only does not count as distribution-ready).**

**v0.8.4: Pilot Production QA Mode — a new Production QA tab scans the global outputs/ folder and shows an end-to-end readiness dashboard for one YouTube CityPop playlist: grouped checklists (songs / thumbnails / Canva overlays / video render / YouTube package / upload), per-group + overall readiness scores, asset warnings (optional vs blocker), a single next-recommended-action, a pilot render-sequence guide, and an exportable report (production_status.json / production_checklist.md / missing_assets.md / next_steps.md) that never contains secrets. Read-only — no changes to existing tabs.**

**v0.8.3: YouTube Real API Dependency Fix — declares the Google libraries (google-api-python-client, google-auth, google-auth-oauthlib, google-auth-httplib2) in requirements.txt and pyproject.toml, and adds a runtime dependency check so the real-upload path degrades clearly instead of silently failing: a structured check_youtube_api_dependencies() report drives the UI (Ready/Missing + "pip install -r requirements.txt"), the real-API toggle and OAuth button are disabled when libraries are missing, and the upload worker performs its own dependency guard so a real upload fails gracefully (sanitized, no secrets) instead of crashing. Mock upload, Manual Package Only default, and private-by-default are all unchanged.**

**v0.8.2: YouTube Private Upload — upload final_video.mp4 to YouTube as PRIVATE (default) via OAuth 2.0, in a background worker so the UI never blocks, then set the custom thumbnail. Manual package flow is unchanged. Tokens/client secrets/Authorization headers are redacted everywhere via a central redaction utility; token.json stays local and is excluded from exports and git. Thumbnail failure → partial_success (video stays private) with thumbnail-only retry. Tests use a mock client; no real API calls. Public upload is not implemented.**

**v0.8.1: Home Navigation UX — Video Renderer and YouTube Package are now reachable from the home screen (no open project required); both scan the global outputs/ folder, so MP3s, thumbnails, final_video.mp4, and chapters can be selected without opening a project. Tab exposure only — no changes to music generation, Thumbnail Studio, Video Renderer, or YouTube Package logic.**

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

| Tab | Purpose | v1.0.0-alpha.1 Status |
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
