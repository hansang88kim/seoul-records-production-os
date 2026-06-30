# Bundled fonts

Used by the Thumbnail Studio premium renderer so titles look identical on every
OS (no dependency on system fonts).

| File | Family / Weight | Use | License |
|------|-----------------|-----|---------|
| Montserrat-Black.ttf | Montserrat 900 | Main title (country/city) | SIL OFL 1.1 |
| Montserrat-Bold.ttf | Montserrat 700 | Eyebrow + Latin sub-line (Vietnamese/Indonesian/Malay/Filipino) | SIL OFL 1.1 |
| Montserrat-SemiBold.ttf | Montserrat 600 | Secondary text | SIL OFL 1.1 |
| Montserrat-Medium.ttf | Montserrat 500 | Bottom line | SIL OFL 1.1 |
| NotoSansKR.ttf | Noto Sans KR (var) | CJK sub-line (Korean/Japanese/Chinese — 밤의 음악 / 夜の音楽 / 夜的音乐) | SIL OFL 1.1 |
| NotoSansThai.ttf | Noto Sans Thai (var) | Thai sub-line (ดนตรียามค่ำคืน) | SIL OFL 1.1 |
| NotoSansDevanagari.ttf | Noto Sans Devanagari (var) | Hindi sub-line (रात का संगीत) | SIL OFL 1.1 |

- Montserrat © The Montserrat Project Authors — https://github.com/JulietaUla/Montserrat
- Noto Sans KR / Thai / Devanagari © Google — https://fonts.google.com/noto

All SIL Open Font License 1.1 (bundling + redistribution permitted).

The renderer's local sub-line picks a font by script (CJK→KR, Thai→Thai,
Devanagari→Devanagari, otherwise Latin→Montserrat). Thai/Devanagari are loaded
with the RAQM layout engine and drawn as a whole string so combining marks and
conjuncts shape correctly.
