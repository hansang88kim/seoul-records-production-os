# UnitedMasters Distribution Package (v0.9.0)

This guide explains the UnitedMasters tab, which builds a **manual-upload
distribution package** from your finished playlist. It deliberately does NOT
auto-upload — UnitedMasters has no confirmed public upload API, so v0.9.0
focuses on producing a clean, verified submission package you upload yourself.

## What the UnitedMasters tab does

1. Reads the **Video Renderer `playlist_plan.json`** to get the exact track
   order used in your YouTube longform video (the source of truth).
2. Uses the **`streaming_cover_1x1`** image from Thumbnail Studio as the cover.
3. Builds a package folder with metadata, a tracklist (CSV + JSON), the cover,
   MP3 reference audio, and (if provided) WAV/FLAC distribution masters.
4. Generates a manual upload checklist and instructions.

## Why MP3 is "source / draft audio" only

The app's default audio output is **MP3**, which is perfect as the YouTube
rendering source. But music distributors typically require a lossless
**WAV or FLAC** master. So:

- MP3 files are included as **source audio** in `audio_mp3_reference/`.
- A package that has only MP3 is a **draft** — it is shown as **MP3-only
  Warning**, and `distribution_ready` is **false**.
- The app never converts MP3 to WAV and calls it a master, and it never creates
  a fake WAV. That would produce a low-quality file masquerading as a master.

## Why a WAV/FLAC master may be required

Lossless masters preserve full audio quality for streaming services. When you
have real WAV/FLAC masters:

- Attach them in the track table (by path), or place a WAV/FLAC next to the MP3
  with the same name.
- Each track with a valid master flips to **Distribution Ready**.
- When **every** track has a valid master, the package becomes
  `distribution_ready = true`.

## How to export the manual upload package

1. Select the latest Video Renderer playlist and a `streaming_cover_1x1`.
2. Fill in the release metadata (artist, title, genre, label, copyright, date).
3. Click **UnitedMasters 패키지 생성**.
4. Click **수동 업로드 패키지 ZIP** to get `manual_upload_package.zip`.

## How to upload to UnitedMasters manually

1. Click **UnitedMasters 열기** and log in (the app never stores your password).
2. Create a new release.
3. Enter the metadata from `release_metadata.json`.
4. Upload the cover from `cover/`.
5. Upload the masters from `audio_distribution_master/` in order `01, 02, 03`.
   - If that folder is empty, prepare WAV/FLAC masters first — MP3 is not a
     distribution master.
6. Verify titles and order, add credits, choose a release date.
7. Review rights/copyright and submit.

The exact steps are also written to
`metadata/unitedmasters_manual_upload_checklist.md`.

## Keeping order synced with the YouTube playlist

The track order comes directly from `playlist_plan.json`. The tab shows whether
the package order matches the playlist, and a **Sync order from Video Renderer**
action rebuilds it from the plan if needed. Repeated tracks in the longform
video are collapsed to unique tracks (01, 02, 03 ...).

## Attaching WAV/FLAC later

You can build a draft package now (MP3-only) and attach masters later:

- Re-open the tab, enter the WAV/FLAC paths in the track table, apply, and
  re-create the package. Tracks become Distribution Ready as masters are added.

## Policy: no CAPTCHA bypass, no credential storage

- The app never bypasses login or CAPTCHA.
- It never stores your UnitedMasters password or browser cookies.
- It never scrapes private account data without your action.
- Any future "assisted upload" (v0.9.1) keeps you in control: you log in
  manually in your own browser; the app may only help fill metadata or select
  local files, never automate authentication.

## Package layout

```
outputs/unitedmasters_package/<package_id>/
├── package_manifest.json
├── release_metadata.json
├── tracklist.csv
├── tracklist.json
├── cover/
│   ├── streaming_cover_1x1.png
│   └── cover_upload_ready.png
├── audio_mp3_reference/
│   ├── 01_track_title.mp3
│   └── 02_track_title.mp3
├── audio_distribution_master/        (WAV/FLAC only if provided)
│   ├── 01_track_title.wav
│   └── 02_track_title.wav
└── metadata/
    ├── release_notes.txt
    ├── credits.csv
    ├── rights_checklist.md
    ├── upload_instructions.md
    └── unitedmasters_manual_upload_checklist.md
```
