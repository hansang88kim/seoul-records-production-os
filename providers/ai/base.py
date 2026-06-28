"""
providers/ai/base.py — AI Songwriter Provider System
Mock / OpenAI / Gemini providers for generating title, style, lyrics.
"""
from __future__ import annotations

import json
import os
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Song Prompt Package ─────────────────────────────────────────────────────

@dataclass
class SongPromptPackage:
    title: str = ""
    style: str = ""
    lyrics: str = ""
    exclude_styles: str = ""
    language_pack: str = "ko_kr_seoul"
    model: str = "v5.5"
    vocal_gender: str = "Female"
    weirdness: int = 35
    style_influence: int = 70
    variation: str = "normal"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


# ─── System Prompt ───────────────────────────────────────────────────────────

from providers.ai.languages import get_language, DEFAULT_LANGUAGE


# Language-independent STYLE guidance (the musical sound never changes).
_STYLE_GUIDANCE = """STYLE FORMAT — write a RICH style: authentic 1980s-1990s JAPANESE CITY POP golden-age sound (300-500 chars). NO saxophone. The mood is deeply emotional, nostalgic, sophisticated, and wistfully lonely — evoking the golden era of Japanese citypop (Mariya Takeuchi, Anri, Tatsuro Yamashita vibe, but original). NOT bright/summery/upbeat — it's mellow, warm, and bittersweet. The musical style is ALWAYS Japanese city pop regardless of the lyric language. Match these examples:

Example 1: "Authentic 1980s-1990s Japanese city pop, golden-age Tokyo sound, lush warm electric piano, glossy analog synths, smooth jazzy chord changes, silky funk guitar, melodic fretless bass, tight clean drums, BPM 112, emotional low female vocal with warm reverb and tender vibrato, deeply nostalgic and bittersweet, the wistful loneliness of city nights"

Example 2: "Classic Japanese city pop (late 80s golden age), warm Rhodes electric piano, lush analog synth pads, sophisticated jazzy chords, smooth funk guitar comping, melodic bass lines, gentle tight drums, BPM 110, emotive low female vocal with vintage reverb and subtle vibrato, deeply nostalgic mellow groove, bittersweet late-night city melancholy, vintage tape warmth"

Example 3: "1980s-90s Japanese citypop revival, glossy electric piano, shimmering warm synths, refined jazz chord voicings, silky clean funk guitar, melodic fretless bass, soft tight drums, BPM 113, tender low female vocal with warm reverb, sophisticated and emotional, the quiet loneliness of neon city nights, nostalgic golden-age warmth"

Required elements (vary each time):
- Genre: "Authentic/Classic 1980s-1990s Japanese city pop" + golden-age Tokyo sound
- Tempo: BPM 108-114 (mellow mid-tempo, sophisticated groove)
- Keys: lush/warm/glossy electric piano, warm Rhodes
- Synths: glossy analog synths, lush synth pads, shimmering warm synths
- Chords: smooth jazzy chord changes, sophisticated jazz chord voicings
- Guitar: silky funk guitar, smooth funk guitar comping
- Bass: melodic fretless bass, melodic bass lines (signature citypop)
- Drums: tight clean drums, gentle tight drums
- Vocal: "emotional/tender low female vocal with warm/vintage reverb and subtle vibrato"
- MOOD (critical): deeply nostalgic, bittersweet, sophisticated, the wistful/quiet loneliness of city nights, late-night city melancholy, golden-age warmth

AVOID these words: bright, summer, crisp, upbeat, sparkling, refreshing, sunny, calm, dreamy, laid-back. Always say "Japanese city pop". Those are WRONG for this mood.
USE these: nostalgic, bittersweet, mellow, sophisticated, wistful, warm, emotional, golden-age, lush, silky, tender, lonely city nights.

CRITICAL: NEVER mention saxophone, sax, brass solos, or horn leads. Keys+guitar+synth driven."""


def build_system_prompt(lang_key: str = DEFAULT_LANGUAGE) -> str:
    """
    Build the A&R/songwriter system prompt for a given lyric language.
    The musical STYLE is always Japanese city pop; only the LYRIC LANGUAGE
    and the CITY/LOCALE emotion change per language.
    """
    lang = get_language(lang_key)
    lyric_lang = lang["lyric_language"]
    city = lang["city"]
    city_native = lang["city_native"]
    locations = ", ".join(lang["locations"])
    title_examples = ", ".join(f'"{t}"' for t in lang["title_examples"])
    char_target = lang["char_target"]
    line_chars = lang["line_chars"]
    vibe = lang["vibe"]

    return f"""You are the A&R director and songwriter for Seoul Records, a city pop label that produces authentic 1980s-90s Japanese-city-pop-style music in MANY languages.

GENRE: Authentic 1980s-1990s Japanese city pop (golden-age Tokyo sound), sung in {lyric_lang}. Lush warm electric piano, glossy analog synths, smooth jazzy chords, silky funk guitar, melodic fretless bass, tight clean drums. Emotional low female vocal. The mood is deeply NOSTALGIC and BITTERSWEET — the sophisticated, wistful loneliness of city nights, like classic Mariya Takeuchi / Anri / Tatsuro Yamashita era emotion (but original, never copy).

THIS SONG'S LANGUAGE & CITY:
- Write ALL lyrics in {lyric_lang}. This is essential.
- The lyrics evoke the night-time emotion of {city} ({city_native}).
- City vibe to capture: {vibe}
- Use REAL {city} place names where natural: {locations}
- The musical style is STILL Japanese city pop — only the lyric language and the city's emotional scenery change. Do NOT change the genre to local/traditional music. No local folk instruments, no trot/enka/luk-thung/dangdut. It is sophisticated Japanese-style city pop with {lyric_lang} lyrics about {city}.

CRITICAL RULES:
- Language: {lyric_lang} lyrics only (section labels + production cues in headers stay in English)
- Vocal: Low, mature, expressive female vocal with retro reverb and subtle vibrato
- BPM: 108-116 (usually 112)
- Key: often minor
- Duration: MUST be 3:30 or SHORTER. Keep lyrics SHORT.
- Too many lines runs 4:00-4:30 — TOO LONG. Cut ruthlessly.
- Total lyric content: {char_target} (not counting section headers).
- BANNED inside sung lines: sax lead, drum fill-ins, tom fills, snare rolls, EDM, trot, enka

TITLE STYLE (natural song titles in {lyric_lang}):
- Write titles like a REAL singer-songwriter, NOT a geographic catalog.
- Short (2-6 words), natural, evocative.
- NO commas in titles.
- NO "location + 밤/거리/블루스/기억/추억" formula.
- In a 5-song batch, use a city place name in AT MOST 1 title.
- The other 4 titles should be mood-based, not location-based.

GOOD title examples (natural, like real songs):
"밤이 지나면", "늦은 대답", "비가 그친 뒤", "오늘은 여기까지",
"아무 일 없던 밤", "조금 늦은 마음", "멀어진 계절", "다시 걷는 밤",
"창가의 불빛", "별일 아닌 척", "여름이 가도", "돌아보지 마",
"마지막 인사처럼", "천천히 사라져", "말하지 못한 채"

BAD title examples (formulaic, auto-generated feel):
"서울의 밤거리", "청계천 거리", "명동의 밤", "을지로 블루스",
"한강의 기억", "남산의 추억", "서울의 그리움", "청계천 거리에서"

Batch diversity: if generating multiple songs, NEVER repeat similar titles.
Each title must feel like it could be from a different album.

LYRICS THEME/MOOD:
- Core feeling: deep nostalgic loneliness in a lively city — the bittersweet ache of golden-age city pop
- The narrator is quietly alone amid crowds and lights in {city}, missing someone gone
- Imagery: neon city nights, crowds laughing while you stand still, shop windows, alleys you once walked together, the contrast between lively streets and a silent, aching heart — all set in {city}
- Bittersweet and emotional — sophisticated melancholy, not melodrama
- Avoid clichés. Make it real, specific to {city}, and deeply felt.

LYRICS FORMAT — follow this EXACT structure for natural 3:30 duration.
Lyrics must be 360-420 characters (sung text only, excluding section headers). Target duration: 3:30-3:50.
If over 420 chars, CUT words until under 420. If under 360 chars, ADD lines.
If under 360 chars, ADD natural phrases to reach 360.

STRUCTURE (10 sections — this length produces ~3:30-3:50):

[Intro]
(4마디 음원 (instrumental only))

[Verse 1]
← exactly 4 lines

[Pre-Chorus]
← exactly 4 lines

[Chorus]
← exactly 4 lines

[Verse 2]
← exactly 4 lines

[Pre-Chorus]
← exactly 4 lines

[Chorus]
← exactly 4 lines (same hook, slight word variation)

[Bridge]
← exactly 4 lines, in parentheses (reflective inner voice)

[Final Chorus]
← exactly 4 lines (climactic, strongest emotional moment)

[Outro]
← exactly 2 lines

SECTION HEADERS MUST BE CLEAN — NO production cues, NO arrangement notes:
CORRECT: [Intro], [Verse 1], [Pre-Chorus], [Chorus], [Verse 2], [Bridge], [Outro]
WRONG: [Bridge, 일렉트릭 피아노 솔로], [Chorus, Hook guitar riff + Harmony]
WRONG: [Outro, 도시 소음 + 페이드아웃 피아노]
WRONG: [Verse 2, 실키 펑크 기타]
Just write the section name. Nothing else inside the brackets.

LINE LENGTH:
- Each line is a natural, singable phrase: {line_chars}.
- Verse/Pre-Chorus/Chorus/Bridge/Final Chorus: exactly 4 lines each.
- Outro: exactly 2 lines.

CRITICAL — keep the line COUNT exact. 4 lines per section (Outro 2).
Do NOT add a 5th line to any chorus or verse. More lines = song too long.

{_STYLE_GUIDANCE}

LYRICS WRITING RULES (professional lyricist quality):
- Write in {lyric_lang} as a native speaker would
- Natural, poetic, emotionally specific — like a professional songwriter
- NO translation-like or explanatory language
- NO instrument names inside sung lyrics (drums, guitar, piano, beat — BANNED)
- NO excessive "~다" endings (vary: ~어, ~지, ~걸, ~는데, ~인데, ~잖아, ~일까)
- NO "~야" addressing inanimate objects (don't say "비야", "바람아")
- NO clichés or forced poetry — make it feel REAL and conversational
- Sentence endings should be varied and natural
- Chorus hook should be memorable but not overused
- Bridge should offer emotional contrast or inner reflection
- Original only — never copy existing songs"""



def _style_variation_prompt(current_style: str) -> str:
    """
    Build a prompt that asks the AI to make a SUBTLE variation of the current style.
    Only BPM, key, and vocal tone should change slightly. The core genre,
    instruments, and mood MUST stay the same.
    """
    return f"""You are given an existing music style description. Create a SUBTLE VARIATION of it.

RULES — READ CAREFULLY:
1. Keep the EXACT SAME genre, instruments, and mood. Do NOT change the genre.
2. Change ONLY these three things (pick 1-3 to vary each time):
   a. BPM: shift by ±2-4 (e.g. 112 → 110, or 112 → 115). Keep it 108-116.
   b. Key: change to a different key (e.g. if no key stated, add one like "E minor" or "Ab major"; if already has a key, change it)
   c. Vocal tone: keep "low female vocal" but vary the descriptor slightly
      (e.g. "emotional" → "tender", "warm reverb" → "vintage plate reverb",
       "subtle vibrato" → "gentle vibrato", add "breathy" or "intimate")
3. You may also make TINY instrument texture changes (e.g. "lush warm electric piano" → "glossy Rhodes electric piano") but keep the same instruments.
4. The output must be the SAME LENGTH and SAME FORMAT as the input.
5. Do NOT add saxophone, brass, or any banned instruments.
6. Do NOT change the mood words (nostalgic, bittersweet, wistful etc.)
7. Return ONLY the new style text as a JSON: {{"style": "..."}}

CURRENT STYLE:
{current_style}

Generate the variation now. Return JSON only."""


def generate_style_variation(current_style: str, provider_name: str = "openai") -> str:
    """
    Generate a subtle variation of the given style using an AI provider.
    Returns the new style string, or the original on failure.
    """
    provider = get_ai_provider(provider_name)
    prompt = _style_variation_prompt(current_style)

    try:
        if hasattr(provider, '_call'):
            # Use the provider's internal _call but with a custom prompt
            import json as _json

            if provider.PROVIDER_NAME == "openai":
                import os, requests
                api_key = os.getenv("OPENAI_API_KEY", "")
                if not api_key:
                    return current_style
                resp = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": provider.MODEL_NAME,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 2000,
                        "response_format": {"type": "json_object"},
                    },
                    timeout=30,
                )
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                parsed = _json.loads(text)
                return _coerce_str(parsed.get("style", current_style)).strip() or current_style

            elif provider.PROVIDER_NAME == "gemini":
                import os, requests
                api_key = os.getenv("GOOGLE_GEMINI_API_KEY", "")
                if not api_key:
                    return current_style
                models = provider.list_models(api_key)
                model = models[0] if models else "gemini-2.5-flash"
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                resp = requests.post(url, json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": 2000},
                }, timeout=30)
                data = resp.json()
                text = ""
                for c_item in data.get("candidates", []):
                    for part in c_item.get("content", {}).get("parts", []):
                        text += part.get("text", "")
                text = text.replace("```json", "").replace("```", "").strip()
                # Find JSON
                import re
                m = re.search(r'\{[^}]+\}', text, re.DOTALL)
                if m:
                    parsed = _json.loads(m.group())
                    return _coerce_str(parsed.get("style", current_style)).strip() or current_style

        # Mock or fallback — just tweak BPM
        import re, random
        bpm_match = re.search(r'BPM\s*(\d+)', current_style)
        if bpm_match:
            old_bpm = int(bpm_match.group(1))
            new_bpm = old_bpm + random.choice([-3, -2, 2, 3])
            new_bpm = max(108, min(116, new_bpm))
            return current_style.replace(f"BPM {old_bpm}", f"BPM {new_bpm}")
        return current_style

    except Exception:
        return current_style



# ── Composer Variation Layer ─────────────────────────────────────────────────
# Each song in a batch should have slightly different BPM, Key, and vocal tone.

_BATCH_BPMS = [108, 110, 111, 112, 113, 114, 115, 116]
_BATCH_KEYS = [
    "A minor", "B minor", "C# minor", "D minor", "E minor",
    "F# minor", "G# minor", "Ab major", "Bb minor", "Eb minor",
]
_BATCH_VOCAL_TONES = [
    "emotional low female vocal with warm reverb and tender vibrato",
    "husky low female vocal with vintage plate reverb and gentle vibrato",
    "intimate mid-low female vocal with soft reverb and subtle warmth",
    "calm smoky female vocal with warm analog reverb",
    "breath-led low alto female vocal with vintage reverb and subtle vibrato",
    "tender low female vocal with glossy reverb and soft vibrato",
]
_BATCH_KEYBOARD_TEXTURES = [
    "lush warm electric piano", "glossy Rhodes electric piano",
    "vintage Wurlitzer", "warm DX7 electric piano", "smooth CP-70 piano",
    "FM bell-layered electric piano",
]
_BATCH_MOOD_SHADES = [
    "the wistful loneliness of city nights",
    "quiet taxi ride through empty streets",
    "apartment window glow at midnight",
    "last train mood, station lights fading",
    "after-rain city lights reflecting on wet asphalt",
    "weekend melancholy in an empty office",
]


def apply_batch_variation(base_style: str, track_no: int) -> str:
    """
    Apply deterministic variation to a base style for a specific track number.
    Changes BPM, key, vocal tone, keyboard texture, and mood shade
    while keeping the core genre and instruments.
    """
    import re

    style = base_style
    idx = track_no % len(_BATCH_BPMS)

    # Replace BPM
    bpm_new = _BATCH_BPMS[idx]
    style = re.sub(r'BPM \d+', f'BPM {bpm_new}', style)

    # Add/replace key
    key_new = _BATCH_KEYS[track_no % len(_BATCH_KEYS)]
    if re.search(r'[A-G][#b]? (?:major|minor)', style):
        style = re.sub(r'[A-G][#b]? (?:major|minor)', key_new, style)
    else:
        style = style.replace(f'BPM {bpm_new}', f'{key_new}, BPM {bpm_new}')

    # Replace vocal tone
    vocal_new = _BATCH_VOCAL_TONES[track_no % len(_BATCH_VOCAL_TONES)]
    for old_vocal in _BATCH_VOCAL_TONES + [
        "emotional low female vocal with warm reverb and subtle vibrato",
    ]:
        if old_vocal in style:
            style = style.replace(old_vocal, vocal_new)
            break

    # Replace keyboard texture (if present)
    kb_new = _BATCH_KEYBOARD_TEXTURES[track_no % len(_BATCH_KEYBOARD_TEXTURES)]
    for old_kb in _BATCH_KEYBOARD_TEXTURES:
        if old_kb in style:
            style = style.replace(old_kb, kb_new)
            break

    # Replace mood shade (if present)
    mood_new = _BATCH_MOOD_SHADES[track_no % len(_BATCH_MOOD_SHADES)]
    for old_mood in _BATCH_MOOD_SHADES:
        if old_mood in style:
            style = style.replace(old_mood, mood_new)
            break

    return style

# Backward-compatible default (Korean) — some code/tests reference SYSTEM_PROMPT.
SYSTEM_PROMPT = build_system_prompt(DEFAULT_LANGUAGE)


def _make_user_prompt(concept: str, generate: str = "all", lang_key: str = DEFAULT_LANGUAGE) -> str:
    """Build user prompt for AI generation, in the target lyric language."""
    lang = get_language(lang_key)
    L = lang["lyric_language"]
    city = lang["city"]

    if generate == "title":
        return (
            f"Concept: {concept}\n\n"
            f"Generate 1 short song title in {L}, based on a {city} place name + mood. "
            f'Return JSON: {{"title": "..."}}'
        )
    if generate == "style":
        return (
            f"Concept: {concept}\n\n"
            "Generate a rich authentic 1980s-90s Japanese citypop style (300-500 chars, English, "
            "NO saxophone, golden-age nostalgic bittersweet mood, include BPM 108-114). "
            "The musical style is Japanese city pop regardless of lyric language. "
            'Return JSON: {"style": "..."}'
        )
    if generate == "lyrics":
        return (
            f"Concept: {concept}\n\n"
            f"Generate lyrics in {L} about {city}, following the EXACT structure. "
            "CRITICAL: exactly 4 lines per section (Outro = 2 lines). Do NOT add a 5th line. "
            "Keep lines short and singable for a 3:30 song. "
            "Structure: Intro(instrumental)/Verse1(4)/Pre-Chorus(4)/Chorus(4)/Verse2(4)/"
            "Pre-Chorus(4)/Chorus(4)/Bridge(4)/Final Chorus(4)/Outro(2). "
            f'Write naturally in {L}. Return JSON: {{"lyrics": "..."}}'
        )

    return (
        f"Concept: {concept}\n\n"
        f"Create a Seoul Records city pop song. Lyrics in {L} about {city}; "
        "the musical style stays authentic 1980s-90s Japanese citypop. Return JSON only.\n"
        "CRITICAL LYRICS RULE: exactly 4 lines per section (Outro 2 lines), short singable lines, "
        "for a 3:30 song. NEVER add a 5th line to any section — that makes the song too long.\n"
        f'{{"title": "{L} title with a {city} place name", '
        '"style": "authentic 1980s-90s Japanese citypop, golden-age sound, 300-500 chars, NO sax, BPM 108-114, nostalgic bittersweet", '
        f'"lyrics": "10 sections (with Final Chorus), 4 lines each (Outro 2), all lyrics in {L}"}}'
    )


# ─── Mock Provider ───────────────────────────────────────────────────────────

def _lyrics_char_count(lyrics: str) -> int:
    """Count Korean lyric characters excluding section headers and blank lines."""
    if not lyrics:
        return 0
    total = 0
    for line in lyrics.split("\n"):
        line = line.strip()
        if line and not line.startswith("["):
            # Remove parentheses content markers but count the Korean
            cleaned = line.replace("(", "").replace(")", "")
            total += len(cleaned)
    return total


def _coerce_str(value) -> str:
    """
    Safely convert an AI response field to a string.
    AI sometimes returns a list (e.g. lyrics as ["line1", "line2"]) or None.
    - list/tuple → joined with newlines (lyrics) or spaces
    - None → ""
    - dict → its values joined
    - str → as-is
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        # Join list items (each coerced) with newlines — works for lyrics lines
        return "\n".join(_coerce_str(v) for v in value)
    if isinstance(value, dict):
        return "\n".join(_coerce_str(v) for v in value.values())
    return str(value)


def _format_lyrics(lyrics: str) -> str:
    """
    Normalize lyrics formatting for clean aligned display:
    - One blank line before each [Section] header (except the first)
    - Strip trailing whitespace per line
    - Collapse multiple blank lines into one
    - No leading/trailing blank lines
    """
    lyrics = _coerce_str(lyrics)
    if not lyrics:
        return ""

    import re as _re

    # If all sections are on one line, split before each [Section] header
    if lyrics.count("\n") < 5 and "[" in lyrics:
        lyrics = _re.sub(r'\s*\[', '\n[', lyrics).strip()
    # Split text that follows a section header on the same line
    # [Verse 1] 가사 텍스트 → [Verse 1]\n가사 텍스트
    lyrics = _re.sub(r'(\[[^\]]+\])\s+([^(\n])', r'\1\n\2', lyrics)

    # Strip production cues from section headers: [Chorus, Hook + Harmony] → [Chorus]
    def _clean_header(line: str) -> str:
        m = _re.match(r'^(\[\w[\w\s-]*?)\s*,.*\]$', line.strip())
        if m:
            return m.group(1).rstrip() + "]"
        return line

    lines = [_clean_header(l.rstrip()) for l in lyrics.replace("\r\n", "\n").split("\n")]
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            # Section header — ensure one blank line before it (unless first)
            if out and out[-1] != "":
                out.append("")
            out.append(stripped)
        else:
            out.append(stripped)

    # Collapse multiple consecutive blank lines into one
    cleaned = []
    prev_blank = False
    for line in out:
        if line == "":
            if not prev_blank:
                cleaned.append(line)
            prev_blank = True
        else:
            cleaned.append(line)
            prev_blank = False

    # Trim leading/trailing blanks
    while cleaned and cleaned[0] == "":
        cleaned.pop(0)
    while cleaned and cleaned[-1] == "":
        cleaned.pop()

    return "\n".join(cleaned)


def _title_from_lyrics(lyrics: str) -> str:
    """Extract a fallback title from the chorus hook if AI didn't provide one."""
    if not lyrics:
        return ""
    lines = [l.strip() for l in lyrics.split("\n") if l.strip()]
    # Find first [Chorus] section and use its first sung line
    in_chorus = False
    for line in lines:
        if line.startswith("[Chorus"):
            in_chorus = True
            continue
        if in_chorus and not line.startswith("["):
            # Use first chorus line, truncate to reasonable title length
            t = line.replace("(", "").replace(")", "").strip()
            return t[:20] if t else ""
    # Fallback: first non-section line
    for line in lines:
        if not line.startswith("[") and not line.startswith("("):
            return line[:20]
    return ""


MOCK_SONGS = [
    SongPromptPackage(
        title="밤이 지나면",
        style="Authentic 1980s-1990s Japanese city pop, golden-age Tokyo sound, lush warm electric piano, glossy analog synths, smooth jazzy chord changes, silky funk guitar, melodic fretless bass, tight clean drums, A minor, BPM 112, emotional low female vocal with warm reverb and tender vibrato, deeply nostalgic and bittersweet, sophisticated mellow groove, the wistful loneliness of city nights, vintage tape warmth",
        lyrics="""[Intro]
(4마디 음원 (instrumental only))

[Verse 1]
사람들 웃음 속에
난 조용히 멈춰 있었어
거리엔 음악이 흐르는데
내 맘은 아무것도 울리지 않아

[Pre-Chorus]
쇼윈도에 비친 내 모습
어느새 낯설어졌어
네 손을 놓던 그날 밤
지금도 여길 맴돌아

[Chorus]
그대가 떠난 거리
불빛 아래 홀로 선 나
이별도 사랑도 다 잊은 듯한 밤
너만이 여전히 선명해

[Verse 2]
화려한 간판 아래
우리 자주 걷던 길
계절이 두 번 바뀌었어도
너는 여전히 그 자리에 있어

[Pre-Chorus]
우산을 나눴던 골목
지금은 텅 비었는데
너의 온기만 잔향처럼
남아 있어

[Chorus]
웃음이 많은 그곳
나만 조용히 멈춘 채
노래는 흐르지만 눈물은 속삭여
사랑은 끝났다는 걸

[Bridge]
(혹시 너도 기억할까)
(그 계절, 그 노래, 그 향기)
(우린 사라졌지만)
(이 거린 그대로인데)

[Final Chorus]
그대가 떠난 거리
오늘도 네 이름을 부르다
누군가의 뒷모습에 너를 겹쳐보다
또 한 번 마음을 접는다

[Outro]
혼자 걸어가는 이 길
밤은 깊어만 가네""",
    ),
    SongPromptPackage(
        title="늦은 대답",
        style="Classic Japanese city pop (late 80s golden age), warm Rhodes electric piano, lush analog synth pads, sophisticated jazzy chords, smooth funk guitar comping, melodic bass lines, gentle tight drums, B minor, BPM 110, husky low female vocal with vintage plate reverb and gentle vibrato, deeply nostalgic mellow groove, bittersweet late-night city melancholy, vintage tape warmth",
        lyrics="""[Intro]
(4마디 음원 (instrumental only))

[Verse 1]
좁은 골목 불빛 아래
혼자 걷던 그 밤처럼
오늘도 같은 길 위에서
너의 흔적을 더듬어

[Pre-Chorus]
유리창에 비친 그림자
점점 흐릿해지는데
그때 네 목소리가
아직 귓가에 맴돌아

[Chorus]
네가 머물던 그 자리
식어버린 커피처럼
우리도 그렇게 멀어졌지만
너만은 선명히 남아

[Verse 2]
밤새 걷던 그 거리에
이제는 나 혼자야
계절이 바뀌어 가도
마음은 그날에 멈춰

[Pre-Chorus]
말없이 나눈 시선들
지금은 흐릿한데
너의 온기만 잔향처럼
남아 있어

[Chorus]
불빛이 많은 그곳
나만 조용히 멈춘 채
노래는 흐르지만 마음은 속삭여
사랑은 끝났다는 걸

[Bridge]
(돌아갈 수 없어도)
(그 골목, 그 밤, 그 온기)
(우린 사라졌지만)
(이 거린 그대로인데)

[Final Chorus]
네가 머물던 그 자리
오늘도 네 이름을 부르다
누군가의 뒷모습에 너를 겹쳐보다
또 한 번 마음을 접는다

[Outro]
혼자 걸어가는 이 길
밤은 깊어만 가네""",
    ),
]

_mock_index = 0


class MockAIProvider:
    """Mock AI provider for testing — no API calls."""
    PROVIDER_NAME = "mock"
    MODEL_NAME = "mock-draft"

    def generate_song_package(self, concept: str, locked: dict | None = None, language: str = DEFAULT_LANGUAGE) -> SongPromptPackage:
        global _mock_index
        pkg = MOCK_SONGS[_mock_index % len(MOCK_SONGS)]
        _mock_index += 1
        pkg.metadata = {
            "ai_provider": "mock",
            "ai_model": "mock-draft",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "concept": concept,
        }
        return pkg

    def generate_title(self, concept: str, language: str = DEFAULT_LANGUAGE) -> str:
        return self.generate_song_package(concept, language=language).title

    def generate_style(self, concept: str, language: str = DEFAULT_LANGUAGE) -> str:
        return self.generate_song_package(concept, language=language).style

    def generate_lyrics(self, concept: str, language: str = DEFAULT_LANGUAGE) -> str:
        return self.generate_song_package(concept, language=language).lyrics


# ─── OpenAI Provider ─────────────────────────────────────────────────────────

class OpenAIProvider:
    PROVIDER_NAME = "openai"

    @property
    def MODEL_NAME(self):
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    @staticmethod
    def is_available() -> bool:
        return bool(os.getenv("OPENAI_API_KEY", "").strip())

    def _call(self, concept: str, generate: str = "all", language: str = DEFAULT_LANGUAGE) -> dict:
        import requests
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")

        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": self.MODEL_NAME,
                "messages": [
                    {"role": "system", "content": build_system_prompt(language)},
                    {"role": "user", "content": _make_user_prompt(concept, generate, language)},
                ],
                "temperature": 0.9,
                "max_tokens": 4000,
                "response_format": {"type": "json_object"},
            },
            timeout=60,
        )
        if resp.status_code != 200:
            try:
                msg = resp.json().get("error", {}).get("message", "")[:150]
            except Exception:
                msg = f"HTTP {resp.status_code}"
            raise RuntimeError(f"ChatGPT 생성 실패 — {msg}")
        content = resp.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)

    def generate_song_package(self, concept: str, locked: dict | None = None, language: str = DEFAULT_LANGUAGE) -> SongPromptPackage:
        data = self._call(concept, "all", language)
        title = _coerce_str(data.get("title", "")).strip()
        lyrics = _format_lyrics(data.get("lyrics", ""))
        if not title:
            title = _title_from_lyrics(lyrics) or "제목 없음"
        return SongPromptPackage(
            title=title,
            style=_coerce_str(data.get("style", "")).strip(),
            lyrics=lyrics,
            metadata={"ai_provider": "openai", "ai_model": self.MODEL_NAME,
                       "generated_at": datetime.now(timezone.utc).isoformat(),
                       "concept": concept, "lyric_chars": _lyrics_char_count(lyrics)},
        )

    def generate_title(self, concept: str, language: str = DEFAULT_LANGUAGE) -> str:
        return _coerce_str(self._call(concept, "title", language).get("title", "")).strip()

    def generate_style(self, concept: str, language: str = DEFAULT_LANGUAGE) -> str:
        return _coerce_str(self._call(concept, "style", language).get("style", "")).strip()

    def generate_lyrics(self, concept: str, language: str = DEFAULT_LANGUAGE) -> str:
        return _format_lyrics(self._call(concept, "lyrics", language).get("lyrics", ""))


# ─── Gemini Provider ─────────────────────────────────────────────────────────

class GeminiProvider:
    PROVIDER_NAME = "gemini"

    @property
    def MODEL_NAME(self):
        return os.getenv("GEMINI_MODEL", "gemini-flash-latest")

    @staticmethod
    def is_available() -> bool:
        return bool(os.getenv("GOOGLE_GEMINI_API_KEY", "").strip())

    @staticmethod
    def list_models(api_key: str) -> list[str]:
        """Query which models support generateContent for this key."""
        import requests
        try:
            r = requests.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
                timeout=15,
            )
            if r.status_code != 200:
                return []
            models = r.json().get("models", [])
            usable = []
            for m in models:
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods:
                    # name format: "models/gemini-2.0-flash" → "gemini-2.0-flash"
                    name = m.get("name", "").replace("models/", "")
                    if name and "vision" not in name and "embedding" not in name:
                        usable.append(name)
            return usable
        except Exception:
            return []

    def _call(self, concept: str, generate: str = "all", language: str = DEFAULT_LANGUAGE) -> dict:
        import requests
        api_key = os.getenv("GOOGLE_GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("GOOGLE_GEMINI_API_KEY not set")

        prompt_text = build_system_prompt(language) + "\n\n" + _make_user_prompt(concept, generate, language)

        # Use ONLY models the key actually supports (from live query).
        # Hardcoded fallbacks often don't exist for a given key/version.
        available = self.list_models(api_key)
        if not available:
            raise RuntimeError(
                "[v2] Gemini 모델 목록 조회 실패 — API 키 또는 네트워크 확인"
            )
        logger.info("Gemini available models: %s", available)

        # Order preference: flash (fast) → pro → others. Skip lite for quality.
        def _rank(m):
            if "flash" in m and "lite" not in m:
                return 0
            if "pro" in m:
                return 1
            if "flash" in m:  # flash-lite
                return 2
            return 3
        models_to_try = sorted(available, key=_rank)

        seen = set()
        last_error = "생성 가능한 모델 없음"

        for model in models_to_try:
            if not model or model in seen:
                continue
            seen.add(model)

            try:
                resp = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{"parts": [{"text": prompt_text}]}],
                        "generationConfig": {
                            "temperature": 0.95,
                            # High limit — Gemini 3 spends tokens on thinking,
                            # so 4000 was too low (output got truncated).
                            "maxOutputTokens": 16000,
                        },
                    },
                    timeout=90,
                )

                if resp.status_code != 200:
                    try:
                        last_error = resp.json().get("error", {}).get("message", "")[:150]
                    except Exception:
                        last_error = f"HTTP {resp.status_code}"
                    logger.warning("Gemini %s: %s", model, last_error)
                    continue

                data = resp.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    last_error = "안전 필터 차단 (candidates 없음)"
                    continue

                cand = candidates[0]
                finish = cand.get("finishReason", "")
                parts = cand.get("content", {}).get("parts", [])

                if not parts:
                    if finish == "MAX_TOKENS":
                        last_error = "토큰 한도 초과 (thinking에 소모) — 재시도"
                    else:
                        last_error = f"빈 응답 (finishReason: {finish})"
                    continue

                # Concatenate all text parts (Gemini 3 may split)
                content = "".join(p.get("text", "") for p in parts).strip()
                if not content:
                    last_error = f"텍스트 없음 (finishReason: {finish})"
                    continue

                # Strip markdown code fences
                if "```" in content:
                    # Extract content between first ``` and last ```
                    import re
                    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL)
                    if m:
                        content = m.group(1)
                    else:
                        content = content.replace("```json", "").replace("```", "").strip()

                # Find the JSON object if there is surrounding text
                if not content.startswith("{"):
                    start_brace = content.find("{")
                    end_brace = content.rfind("}")
                    if start_brace >= 0 and end_brace > start_brace:
                        content = content[start_brace:end_brace + 1]

                result = json.loads(content)
                logger.info("Gemini success: model=%s", model)
                return result

            except requests.exceptions.RequestException as e:
                last_error = f"네트워크: {type(e).__name__}"
                continue
            except json.JSONDecodeError as e:
                last_error = f"JSON 파싱 실패: {str(e)[:60]} | 내용: {content[:80]}"
                logger.warning("Gemini JSON error: %s", last_error)
                continue

        raise RuntimeError(f"[v2] Gemini 실패 ({len(models_to_try)}개 모델 시도) — {last_error}")

    def generate_song_package(self, concept: str, locked: dict | None = None, language: str = DEFAULT_LANGUAGE) -> SongPromptPackage:
        data = self._call(concept, "all", language)
        title = _coerce_str(data.get("title", "")).strip()
        lyrics = _format_lyrics(data.get("lyrics", ""))
        if not title:
            title = _title_from_lyrics(lyrics) or "제목 없음"
        return SongPromptPackage(
            title=title,
            style=_coerce_str(data.get("style", "")).strip(),
            lyrics=lyrics,
            metadata={"ai_provider": "gemini", "ai_model": self.MODEL_NAME,
                       "generated_at": datetime.now(timezone.utc).isoformat(),
                       "concept": concept, "lyric_chars": _lyrics_char_count(lyrics)},
        )

    def generate_title(self, concept: str, language: str = DEFAULT_LANGUAGE) -> str:
        return _coerce_str(self._call(concept, "title", language).get("title", "")).strip()

    def generate_style(self, concept: str, language: str = DEFAULT_LANGUAGE) -> str:
        return _coerce_str(self._call(concept, "style", language).get("style", "")).strip()

    def generate_lyrics(self, concept: str, language: str = DEFAULT_LANGUAGE) -> str:
        return _format_lyrics(self._call(concept, "lyrics", language).get("lyrics", ""))


# ─── Provider Registry ──────────────────────────────────────────────────────

def get_ai_provider(name: str):
    if name == "openai":
        return OpenAIProvider()
    if name == "gemini":
        return GeminiProvider()
    return MockAIProvider()


def get_available_ai_providers() -> list[dict]:
    """Return list of providers with availability status."""
    return [
        {"name": "mock", "label": "Mock Draft", "available": True},
        {"name": "openai", "label": "ChatGPT", "available": OpenAIProvider.is_available()},
        {"name": "gemini", "label": "Gemini", "available": GeminiProvider.is_available()},
    ]
