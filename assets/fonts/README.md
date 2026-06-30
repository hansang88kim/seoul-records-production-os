# Bundled fonts

These are used by the Thumbnail Studio premium renderer so titles look identical
on every OS (no dependency on system fonts).

| File | Family | Use | License |
|------|--------|-----|---------|
| Montserrat-Bold/SemiBold/Medium.ttf | Montserrat | Latin titles (YouTube music-channel look) | SIL Open Font License 1.1 |
| Pretendard-Bold/Medium.otf | Pretendard | Korean titles (Hangul fallback) | SIL Open Font License 1.1 |

- Montserrat © The Montserrat Project Authors — https://github.com/JulietaUla/Montserrat
- Pretendard © Kil Hyung-jin — https://github.com/orioncactus/pretendard

Both are licensed under the SIL OFL 1.1, which permits bundling and redistribution
with this project. The renderer picks Pretendard automatically when a title
contains Hangul, otherwise Montserrat.
