# Bundled fonts

Used by the Thumbnail Studio premium renderer so titles look identical on every
OS (no dependency on system fonts).

| File | Family / Weight | Use | License |
|------|-----------------|-----|---------|
| Montserrat-Black.ttf | Montserrat 900 | Main playlist title (strong, bold) | SIL OFL 1.1 |
| Montserrat-Bold.ttf | Montserrat 700 | Eyebrow / brand label | SIL OFL 1.1 |
| Montserrat-SemiBold.ttf | Montserrat 600 | Secondary text | SIL OFL 1.1 |
| Montserrat-Medium.ttf | Montserrat 500 | Subtitle | SIL OFL 1.1 |
| NotoSansKR.ttf | Noto Sans KR (variable, wght 100–900) | Hanja/Hangul sub-line under the title (TOKYO / 東京 style) | SIL OFL 1.1 |

- Montserrat © The Montserrat Project Authors — https://github.com/JulietaUla/Montserrat
- Noto Sans KR © Google — https://fonts.google.com/noto/specimen/Noto+Sans+KR
  (covers Hangul + the common Hanja/Kanji used in titles; the renderer sets the
  weight axis to ~700 for a bold sub-line)

All SIL Open Font License 1.1, which permits bundling and redistribution.

Main titles are English (Montserrat). The optional CJK sub-line under the title
is rendered with Noto Sans KR; if it is unavailable the renderer falls back to an
OS CJK font (Malgun Gothic on Windows, Noto CJK on Linux).
