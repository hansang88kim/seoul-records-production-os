# Seoul Records Production OS

**AI Music Label Production Harness — v0.1.3**

> Creative direction: controlled by ChatGPT and the user.
> Engineering: this repository.
> Creative prompt generation is placeholder in v0.1.3 and will later be controlled by ChatGPT.

---

## What This Is

Seoul Records Production OS is a local MVP application for creating AI-generated city pop album projects. It provides a full 5-tab production pipeline from song generation through music distribution, with mock providers for v0.1.x and a clear upgrade path to real integrations.

**v0.1.3 is still mock/local only — no real Suno, Canva, YouTube, or UnitedMasters APIs yet.**

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

| Tab | Purpose | v0.1.3 Status |
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
| v0.1.3 | Clean package, fast tests, manual WAV import, safe candidate override | ✅ Current |
| v0.2 | Real FFmpeg rendering, ffprobe audio QC | Planned |
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
