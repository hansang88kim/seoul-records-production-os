# Bundled fonts

Used by the Thumbnail Studio premium renderer so titles look identical on every
OS (no dependency on system fonts). Titles are English-only.

| File | Family / Weight | Use | License |
|------|-----------------|-----|---------|
| Montserrat-Black.ttf | Montserrat 900 | Main playlist title (strong, bold) | SIL OFL 1.1 |
| Montserrat-Bold.ttf | Montserrat 700 | Eyebrow / brand label | SIL OFL 1.1 |
| Montserrat-SemiBold.ttf | Montserrat 600 | Secondary text | SIL OFL 1.1 |
| Montserrat-Medium.ttf | Montserrat 500 | Subtitle | SIL OFL 1.1 |

Montserrat © The Montserrat Project Authors — https://github.com/JulietaUla/Montserrat
(SIL Open Font License 1.1, which permits bundling and redistribution).

Korean is not used in titles. If a string happens to contain Hangul (e.g. the
optional 구독/좋아요 sticker labels), the renderer falls back to an OS CJK font
(Malgun Gothic on Windows, Noto CJK on Linux).
