# YouTube Private Upload (v0.8.2)

This guide explains how to upload a finished `final_video.mp4` to YouTube as a
**private** video directly from Seoul Records Production OS, then set the custom
thumbnail. Uploads are **always private by default** — nothing is ever published
publicly automatically.

## Overview

The YouTube Package tab can now:

1. Build a manual upload package (titles, description, tags, chapters, thumbnail) — unchanged from v0.8.0.
2. Authenticate with your Google account via OAuth 2.0.
3. Upload the video **private** in a background job (the UI never blocks).
4. Set the custom thumbnail after the video ID is returned.
5. Save `upload_result.json` with the video ID and YouTube URL.

You review the result in YouTube Studio and publish manually if and when you choose.


## YouTube API dependency installation

Real uploads require these Google libraries (already declared in
`requirements.txt` and `pyproject.toml`):

- `google-api-python-client`
- `google-auth`
- `google-auth-oauthlib`
- `google-auth-httplib2`

Install them:

```
pip install -r requirements.txt
```

Verify the install:

```
python -c "import googleapiclient; import google_auth_oauthlib; print('ok')"
```

If the YouTube Package tab shows **YouTube API dependencies: Missing**, run the
install command above and reload the app. Until they are installed, the real-API
toggle and the OAuth button are disabled — but **mock upload and Manual Package
generation keep working**.

### Troubleshooting

- **`ModuleNotFoundError: googleapiclient`** — `google-api-python-client` is not
  installed. Run `pip install -r requirements.txt`.
- **`ModuleNotFoundError: google_auth_oauthlib`** — `google-auth-oauthlib` is not
  installed. Run `pip install google-auth-oauthlib google-auth`.
- **OAuth flow fails before the browser opens** — usually a missing
  `google-auth-oauthlib`, or a malformed `client_secret.json`. Re-download the
  OAuth client (Desktop app) and re-upload it.
- **Dependency status is "Missing" in the UI** — the Python environment running
  Streamlit does not have the libraries. Make sure you installed into the same
  virtualenv that runs `streamlit run app/main.py`.

## Step-by-step

### 1. Create a Google Cloud project
Go to the Google Cloud Console and create a new project (or reuse one).

### 2. Enable the YouTube Data API v3
In the project, enable **YouTube Data API v3** under APIs & Services.

### 3. Create an OAuth client
Under APIs & Services → Credentials, create an **OAuth client ID** of type
**Desktop app**. Configure the OAuth consent screen if prompted (External, add
yourself as a test user).

### 4. Download `client_secret.json`
Download the OAuth client credentials file. Keep it private — **never commit it**.

### 5. Upload `client_secret.json` in the app
In the YouTube Package tab, choose **API Private Upload**, then upload your
`client_secret.json` in the OAuth / 계정 section. It is stored locally under
`outputs/youtube_auth/` and never shown back on screen.

### 6. Authorize with Google
Click **YouTube 인증**. A browser window opens for Google sign-in and consent.
After approval, the token is stored locally (again, never displayed).

### 7. Review the checklist and upload
The **Upload Private to YouTube** button stays disabled until you check the
review box confirming you understand the video uploads **private** and that you
are responsible for rights/copyright. Then click upload.

### 8. Watch progress
The background worker uploads the video and reports progress (percent / status)
in the **업로드 진행 상황** panel. When done, the video ID and YouTube URL appear.

### 9. Thumbnail
After the video ID is returned, the app sets the `thumbnail_upload_ready` image
as the custom thumbnail. If the thumbnail step fails, the job is marked
**partial_success** (the video stays private and uploaded) and you can retry the
thumbnail only.

### 10. Review and publish in YouTube Studio
Open the video in YouTube Studio. Confirm everything, then publish manually if
you want it public. The app never makes a video public for you.

## Privacy & security notes

- **Uploads default to private.** Public publishing is not automated and is not implemented in v0.8.2.
- **Tokens are never shown or logged.** `access_token`, `refresh_token`, `client_secret`, and any `Authorization: Bearer` header are redacted everywhere (logs, manifests, UI).
- **`token.json` stays local.** It lives under `outputs/youtube_auth/` and is excluded from package exports and from git.
- **Do not share** your OAuth token files or `client_secret.json`.
- **Local files are never deleted** after upload — your MP4, thumbnail, and package files remain on disk.
- **Unverified API projects** may have uploads restricted to private until the project completes Google's verification. This is expected.

## Files written

Under `outputs/youtube_upload/jobs/<upload_job_id>/`:

- `upload_state.json` — live status (status, percent, video_id, url, ...)
- `upload_log.jsonl` — sanitized log lines (no secrets)
- `upload_progress.jsonl` — upload progress records
- `upload_payload_snapshot.json` — the request body (sanitized)
- `upload_result.json` — final result (video_id, url, privacy, thumbnail status)
- `request_sanitized.json` — sanitized request descriptor

Under `outputs/youtube_auth/` (local only, never exported):

- `client_secret.json`
- `token.json`
- `oauth_status.json` — status only (no secrets)
