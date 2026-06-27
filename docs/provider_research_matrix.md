# Seoul Records Production OS — Provider Research Matrix (v0.3)

Last updated: 2026-06-27

## Background

Suno does not offer an official public API (as of mid-2026). Every "Suno API" in the developer ecosystem is reverse-engineered and unofficial. Seoul Records Production OS uses a provider abstraction layer to isolate integration risk — if a wrapper breaks or is discontinued, only the provider file changes, not the core app.

---

## Provider Comparison Table

| Criterion | gcui-art/suno-api | paperfoot/suno-cli | PlaywrightSunoWebProvider | ManualImportProvider | ThirdPartySunoProvider |
|---|---|---|---|---|---|
| **repo/url** | github.com/gcui-art/suno-api | github.com/paperfoot/suno-cli | Built-in (playwright_suno_web.py) | Built-in (manual_import.py) | Built-in (third_party_suno.py) |
| **language/runtime** | TypeScript / Node.js | Rust (single binary) | Python / Playwright | Python (stdlib) | Python / requests |
| **local server possible** | ✅ npm run dev / Docker | ✅ CLI binary, no server needed | ✅ Local browser | ✅ No server needed | ❌ Cloud API only |
| **uses official user credits** | ✅ SUNO_COOKIE | ✅ Auto-auth from browser cookie | ✅ User's browser session | N/A (manual upload) | ❌ Third-party pool |
| **custom mode** | ✅ /api/custom_generate | ✅ suno generate (full flags) | ✅ (v0.4 target) | N/A | ✅ |
| **title/style/lyrics** | ✅ / ✅ / ✅ | ✅ / ✅ / ✅ | ✅ / ✅ / ✅ (skeleton) | N/A | ✅ / ✅ / ✅ |
| **exclude styles** | ✅ negative_tags | ✅ --exclude flag | ❌ (skeleton) | N/A | ✅ |
| **vocal gender** | ⚠️ Via style tags | ✅ --vocal-gender flag | ⚠️ Via style tags | N/A | ✅ Direct param |
| **weirdness** | ❌ | ✅ --weirdness 0-100 | ❌ | N/A | ✅ 0.00–1.00 |
| **style influence** | ❌ | ✅ --style-influence 0-100 | ❌ | N/A | ✅ 0.00–1.00 |
| **instrumental** | ✅ make_instrumental | ✅ --instrumental | ✅ (skeleton) | N/A | ✅ |
| **model selector** | ✅ model param | ✅ --model (v4, v4.5, v5, v5.5) | ❌ (skeleton) | N/A | ✅ |
| **persona** | ❌ | ✅ --persona-id | ❌ | N/A | ✅ personaId |
| **polling** | ✅ /api/get | ✅ suno status (built-in wait) | ❌ (skeleton) | N/A | ✅ |
| **two candidates** | ✅ Returns 2 clips | ✅ Returns 2 clips | ✅ (target) | ✅ A/B upload | ✅ |
| **WAV download** | ⚠️ wav_url intermittent | ✅ suno download (MP3 w/ embedded lyrics, WAV via Suno Pro) | ✅ (target) | ✅ User provides | ✅ (paid) |
| **MP3 fallback** | ✅ audio_url (CDN) | ✅ Default download format | ✅ (target) | ✅ User provides | ✅ |
| **auth method** | SUNO_COOKIE env var | Auto-extract from browser | Browser session | None | X-API-Key (paid) |
| **CAPTCHA/2FA handling** | ❌ Requires 2Captcha (paid) | ✅ No bypass; stops if needed | ✅ Stops, user_action_required | N/A | ✅ Server-side |
| **license** | LGPL-3.0 | MIT | Internal | Internal | Proprietary |
| **maintenance status** | Active (2026) | Active (2026, v5.5 support) | Internal skeleton | Stable | Active (commercial) |
| **risk** | HIGH (CAPTCHA bypass req'd) | MEDIUM (Rust binary dep) | LOW (skeleton only) | NONE (manual) | HIGH (paid, non-user credits) |
| **recommendation** | ✅ HTTP adapter (no Playwright/2Captcha) | ✅ Strong v0.4 candidate | ⚠️ v0.4 target | ✅ Production default | ❌ Not default |

---

## Integration Architecture

```
Seoul Records Production OS
│
├── ManualImportProvider       ← Production-safe default (v0.1+)
│   └── User downloads WAV from suno.com → uploads via UI
│
├── LocalUnofficialSunoProvider ← First experimental provider (v0.3)
│   └── HTTP adapter → gcui-art/suno-api (localhost:3000)
│   └── SUNO_COOKIE → user's own credits
│   └── Fallback: ManualImportProvider
│
├── PlaywrightSunoWebProvider  ← WAV fallback / UI automation (v0.4 target)
│   └── Browser automation for WAV download
│   └── CAPTCHA → stop, user_action_required
│   └── Fallback: ManualImportProvider
│
├── ThirdPartySunoProvider     ← Disabled by default
│   └── sunoapi.org or similar paid APIs
│   └── Requires ALLOW_THIRD_PARTY_SUNO=true
│   └── Uses third-party account pool, NOT user credits
│
└── MockSunoProvider           ← Testing only
    └── Generates local sine-wave WAV files
```

---

## Conclusions & Policy

### Default provider is ManualImportProvider
The safest, most reliable workflow is manual: user downloads WAV from suno.com, imports via the Song Generation tab. This works regardless of API changes, CAPTCHA, or session expiry.

### First experimental provider is LocalUnofficialSunoProvider
Uses gcui-art/suno-api as a local HTTP server with the user's own SUNO_COOKIE. Supports custom mode (title, lyrics, tags, negative_tags, model, instrumental). Limitations: no direct vocal_gender/weirdness/style_influence params — these are either injected into style tags or stored as `not_applied`.

### paperfoot/suno-cli is the strongest v0.4 candidate
A Rust CLI binary with full v5.5 feature coverage including vocal_gender, weirdness, style_influence, persona, exclude, model selection, and auto-auth from browser cookies. No CAPTCHA bypass. Runs as a local binary — could be invoked via subprocess from Python. Integration approach: subprocess adapter wrapping `suno generate --json`.

### PlaywrightSunoWebProvider is a WAV fallback
When API wrappers cannot provide WAV downloads, Playwright can automate the Suno web UI to download WAV directly. Strict safety: stops immediately on CAPTCHA/2FA detection, never bypasses human verification.

### ThirdPartySunoProvider is disabled by default
Paid services like sunoapi.org use their own account pools, not the user's credits. They charge per generation. Not suitable as default for Seoul Records' independent production model.

### Security policy
- CAPTCHA/2FA bypass is **strictly prohibited**
- Credentials (cookies, tokens, API keys) are **never logged or committed to GitHub**
- `safe_error()` in ProviderError automatically redacts credential-like fields
- `.env`, `cookies/`, `tokens/`, `*.cookie`, `*.token` are in `.gitignore`
- SUNO_COOKIE is loaded from environment variable only, never hardcoded
