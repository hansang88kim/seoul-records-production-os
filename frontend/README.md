# Seoul Records Studio OS — Frontend (v1.0.0-alpha)

A modern, dark-theme studio console for Seoul Records Production OS, built with
**Next.js 15 (App Router)**, **TypeScript (strict)**, **Tailwind CSS v4**, and
**shadcn/ui**-style components. It runs in parallel with the existing Streamlit
app (which remains the legacy/admin fallback) and shares the same `outputs/`
folder and Python services via a sanitized snapshot API.

## Stack

- Next.js 15+ (App Router, React 19)
- TypeScript strict mode, path alias `@/*`
- Tailwind CSS v4 (`@tailwindcss/postcss`)
- shadcn/ui components (`components/ui`)
- lucide-react icons
- Dark theme first (design tokens in `app/globals.css`)

## Develop

```
cd frontend
npm install
npm run dev        # http://localhost:3000
npm run lint
npm run typecheck
npm run build
```

## Backend boundary

`lib/api.ts` is **mock-first**: with no `NEXT_PUBLIC_API_BASE` set it serves the
typed mock snapshot in `lib/mock-data.ts`, so the UI is fully navigable without a
backend. Point it at the Python bridge to get live, sanitized data:

```
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8787 npm run dev
```

The Python side (`api/snapshot.py`) builds the same JSON shape from the existing
services (production scanner/checklist, supervisor) and **never returns
secrets** — tokens, cookies, keys, and client secrets are scrubbed via
`services/security/redaction.py`.

## Routes

`/` Dashboard · `/song-lab` · `/thumbnail-studio` · `/video-renderer` ·
`/youtube-package` · `/production-qa` · `/unitedmasters` · `/remote-control` ·
`/settings`

## Migration phases

- **v1.0.0-alpha (this):** shell, design system, routing, dashboard + read-only
  status pages, mock/snapshot API. Streamlit untouched.
- v1.0.0-beta: wire pages to backend, start jobs from the console.
- v1.0.0: Next.js becomes primary, Streamlit retained as admin fallback.
