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

SYSTEM_PROMPT = """You are the A&R director and songwriter for Seoul Records, a Korean retro city pop label.

GENRE: Authentic 1980s-1990s Japanese city pop (golden-age Tokyo sound) sung in Korean. Lush warm electric piano, glossy analog synths, smooth jazzy chords, silky funk guitar, melodic fretless bass, tight clean drums. Emotional low female vocal. The mood is deeply NOSTALGIC and BITTERSWEET — the sophisticated, wistful loneliness of city nights, like classic Mariya Takeuchi / Anri / Tatsuro Yamashita era emotion (but original, never copy).

CRITICAL RULES:
- Language: Korean lyrics only (section labels + production cues in headers)
- Vocal: Low, mature, expressive female vocal with retro reverb and subtle vibrato
- BPM: 108-116 (usually 112)
- Key: often minor
- Duration: MUST be 3:30 or SHORTER (never exceed 3:30). Keep lyrics SHORT.
- A song with too many lines runs 4:00-4:30 — that is TOO LONG. Cut ruthlessly.
- Total lyric content should be ~280-340 Korean characters MAX (not counting section headers).
- BANNED inside sung lines: sax lead, drum fill-ins, tom fills, snare rolls, EDM, trot, enka

TITLE STYLE (Seoul place-name based, like the user's favorites):
- "명동에서 종로까지", "을지로 밤길에서", "서울의 밤", "청계천 거리"
- Use REAL Seoul locations: 명동, 종로, 을지로, 청계천, 뚝섬, 삼각지, 마포, 한강, 남산, 건대, 성수, 압구정, 신촌, 홍대, 이태원
- Natural, evocative, place + mood. Short.

LYRICS THEME/MOOD (important for the emotional tone):
- Core feeling: deep nostalgic loneliness in a lively city — the bittersweet
  ache of golden-age Japanese citypop emotion
- The narrator is quietly alone amid crowds and lights, missing someone gone
- Imagery: neon city nights, crowds laughing while you stand still, shop windows,
  alleys you once walked together, the contrast between lively streets and a
  silent, aching heart
- Bittersweet and emotional — sophisticated melancholy, not melodrama
- Examples of feeling: standing alone as music plays in a crowded street,
  seeing someone's back and mistaking them for a lost love, the city unchanged
  while you and they have vanished
- Like the 명동 블루스 example: lively place, but the narrator alone, crying quietly
- Avoid clichés. Make it real, specific, and deeply felt.

LYRICS FORMAT — follow this EXACT structure for natural 3:30 duration.
Section headers carry production cues. Section labels stay in English.
Keep it TIGHT — fewer lines = shorter song. This structure lands at ~3:30.

EXACT TEMPLATE (9 sections with lyrics + intro):

[Intro, <production cue>]
← NO lyric lines. Header only. Instrumental.

[Verse 1]
← exactly 4 lines

[Pre-Chorus, <cue>]
← exactly 4 lines

[Chorus, <cue>]
← exactly 4 lines (line 1 starts with the hook + Seoul place from title)

[Verse 2, <cue>]
← exactly 4 lines

[Pre-Chorus]
← exactly 4 lines

[Chorus, <cue>]
← exactly 4 lines (same hook, slight variation)

[Bridge, <cue>]
← exactly 4 lines, in parentheses (reflective inner voice)

[Final Chorus, <cue>]
← exactly 4 lines (climactic)

[Outro, <cue>]
← exactly 2 lines, in parentheses (a final lonely image)

LINE LENGTH:
- Each line is a natural phrase: 8-17 Korean characters.
- Lines can be full sentences but keep them singable.
- Verse/Pre-Chorus/Chorus/Bridge/Final Chorus: exactly 4 lines each.
- Outro: exactly 2 lines.
- TOTAL lyric characters: 380-420 (this is the sweet spot for 3:30).

CRITICAL — keep the line COUNT exact. 4 lines per section (Outro 2).
Do NOT add a 5th line to any chorus or verse. More lines = song too long.

CORRECT EXAMPLE (study this — natural phrases, 4 lines per section):
[Verse 1]
사람들 웃음 속에
난 조용히 멈춰 있었어
거리엔 음악이 흐르는데
내 맘은 아무것도 울리지 않아

[Chorus, Hook + Harmony]
명동 블루스, 그대가 떠난 거리
불빛 아래 홀로 선 나
이별도 사랑도 다 잊은 듯한 밤
너만이 여전히 선명해

[Bridge, Electric piano solo]
(혹시 너도 기억할까)
(그 계절, 그 노래, 그 향기)
(우린 사라졌지만)
(이 거린 그대로인데)

[Outro, Fade]
(명동, 모두가 웃는 그 밤)
(나만, 조용히 울고 있어)

STYLE FORMAT — write a RICH style: authentic 1980s-1990s JAPANESE CITY POP golden-age sound (300-500 chars). Korean vocals. NO saxophone. The mood is deeply emotional, nostalgic, sophisticated, and wistfully lonely — evoking the golden era of Japanese citypop (Mariya Takeuchi, Anri, Tatsuro Yamashita vibe, but original). NOT bright/summery/upbeat — it's mellow, warm, and bittersweet. Match these examples:

Example 1: "Authentic 1980s-1990s Japanese city pop, golden-age Tokyo sound, lush warm electric piano, glossy analog synths, smooth jazzy chord changes, silky funk guitar, melodic fretless bass, tight clean drums, BPM 112, emotional low female vocal with warm reverb and tender vibrato, deeply nostalgic and bittersweet, the wistful loneliness of city nights"

Example 2: "Classic Japanese city pop (late 80s golden age), warm Rhodes electric piano, lush analog synth pads, sophisticated jazzy chords, smooth funk guitar comping, melodic bass lines, gentle tight drums, BPM 110, emotive low female vocal with vintage reverb and subtle vibrato, deeply nostalgic mellow groove, bittersweet late-night city melancholy, vintage tape warmth"

Example 3: "1980s-90s Japanese citypop revival, glossy electric piano, shimmering warm synths, refined jazz chord voicings, silky clean funk guitar, melodic fretless bass, soft tight drums, BPM 113, tender low female vocal with warm reverb, sophisticated and emotional, the quiet loneliness of neon city nights, nostalgic golden-age warmth"

Required elements (vary each time):
- Genre: "Authentic/Classic 1980s-1990s Japanese city pop" + golden-age Tokyo sound
  (do NOT say 'Korean city pop' or 'early 80s Seoul' — it's JAPANESE citypop sound)
- Tempo: BPM 108-114 (mellow mid-tempo, sophisticated groove)
- Keys: lush/warm/glossy electric piano, warm Rhodes
- Synths: glossy analog synths, lush synth pads, shimmering warm synths
- Chords: smooth jazzy chord changes, sophisticated jazz chord voicings
- Guitar: silky funk guitar, smooth funk guitar comping
- Bass: melodic fretless bass, melodic bass lines (signature citypop)
- Drums: tight clean drums, gentle tight drums
- Vocal: "emotional/tender low female vocal with warm/vintage reverb and subtle vibrato"
- MOOD (critical): deeply nostalgic, bittersweet, sophisticated, the wistful/quiet
  loneliness of city nights, late-night city melancholy, golden-age warmth

AVOID these words: bright, summer, crisp, upbeat, sparkling, refreshing, sunny,
"early 80s Seoul", "Korean city pop". Those are WRONG for this mood.
USE these: nostalgic, bittersweet, mellow, sophisticated, wistful, warm, emotional,
golden-age, lush, silky, tender, lonely city nights.

CRITICAL: NEVER mention saxophone, sax, brass solos, or horn leads. Keys+guitar+synth driven.




Lyrics: realistic, lyrical, specific Seoul places and scenes. Concrete imagery (버스 정류장, 카페, 골목, 가로등, 네온). Varied sentence endings, no instrument names in sung lines. Original only — never copy existing songs."""


def _make_user_prompt(concept: str, generate: str = "all") -> str:
    """Build user prompt for AI generation."""
    if generate == "title":
        return f"Concept: {concept}\n\nGenerate 1 short Korean song title (Seoul place-name based). Return JSON: {{\"title\": \"...\"}}"
    if generate == "style":
        return f"Concept: {concept}\n\nGenerate a rich authentic 1980s-90s Japanese citypop style (300-500 chars, English, NO saxophone, golden-age nostalgic bittersweet mood, include BPM 108-114). Return JSON: {{\"style\": \"...\"}}"
    if generate == "lyrics":
        return (
            f"Concept: {concept}\n\n"
            "Generate Korean lyrics following the EXACT structure. "
            "CRITICAL: exactly 4 lines per section (Outro = 2 lines). Do NOT add a 5th line. "
            "Each line 8-17 Korean characters. Total 380-420 characters for a 3:30 song. "
            "Structure: Intro(instrumental)/Verse1(4)/Pre-Chorus(4)/Chorus(4)/Verse2(4)/"
            "Pre-Chorus(4)/Chorus(4)/Bridge(4)/Final Chorus(4)/Outro(2). "
            'Return JSON: {"lyrics": "..."}'
        )

    return (
        f"Concept: {concept}\n\n"
        "Create a Seoul Records city pop song (authentic 1980s-90s Japanese citypop sound). Return JSON only.\n"
        "CRITICAL LYRICS RULE: exactly 4 lines per section (Outro 2 lines), each 8-17 Korean chars, "
        "total 380-420 chars for 3:30. NEVER add a 5th line to any section — that makes the song too long.\n"
        '{"title": "Korean Seoul place-name title", '
        '"style": "authentic 1980s-90s Japanese citypop, golden-age sound, 300-500 chars, NO sax, BPM 108-114, nostalgic bittersweet", '
        '"lyrics": "10 sections, 4 lines each (Outro 2), 380-420 chars total"}'
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


def _format_lyrics(lyrics: str) -> str:
    """
    Normalize lyrics formatting for clean aligned display:
    - One blank line before each [Section] header (except the first)
    - Strip trailing whitespace per line
    - Collapse multiple blank lines into one
    - No leading/trailing blank lines
    """
    if not lyrics:
        return ""

    lines = [l.rstrip() for l in lyrics.replace("\r\n", "\n").split("\n")]
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
        title="명동 블루스",
        style="Authentic 1980s-1990s Japanese city pop, golden-age Tokyo sound, lush warm electric piano, glossy analog synths, smooth jazzy chord changes, silky funk guitar, melodic fretless bass, tight clean drums, BPM 112, emotional low female vocal with warm reverb and tender vibrato, deeply nostalgic and bittersweet, the wistful loneliness of city nights, vintage tape warmth",
        lyrics="""[Intro, 도시 소음 + 따뜻한 로즈 피아노]

[Verse 1]
사람들 웃음 속에
난 조용히 멈춰 있었어
거리엔 음악이 흐르는데
내 맘은 아무것도 울리지 않아

[Pre-Chorus, 부드러운 신스 패드]
쇼윈도에 비친 내 모습
어느새 낯설어졌어
네 손을 놓던 그날 밤
지금도 여길 맴돌아

[Chorus, 재지한 코드 + 코러스 하모니]
명동 블루스, 그대가 떠난 거리
불빛 아래 홀로 선 나
이별도 사랑도 다 잊은 듯한 밤
너만이 여전히 선명해

[Verse 2, 실키 펑크 기타]
화려한 간판 아래
우리 자주 걷던 길
계절이 두 번 바뀌었어도
너는 여전히 그 자리에 있어

[Pre-Chorus, 멜로딕 프렛리스 베이스]
우산을 나눴던 골목
지금은 텅 비었는데
너의 온기만 잔향처럼
남아 있어

[Chorus, 감정이 쌓이는 진행]
명동 블루스, 웃음이 많은 그곳
나만 조용히 멈춘 채
노래는 흐르지만 눈물은 속삭여
사랑은 끝났다는 걸

[Bridge, 일렉트릭 피아노 솔로]
(혹시 너도 기억할까)
(그 계절, 그 노래, 그 향기)
(우린 사라졌지만)
(이 거린 그대로인데)

[Final Chorus, 감정 폭발 클라이맥스]
명동 블루스, 그대가 떠난 거리
오늘도 네 이름을 부르다
누군가의 뒷모습에 너를 겹쳐보다
또 한 번, 마음을 접는다

[Outro, 도시 소음 + 페이드아웃 피아노]
(명동, 모두가 웃는 그 밤)
(나만, 조용히 울고 있어)""",
    ),
    SongPromptPackage(
        title="을지로 블루스",
        style="Classic Japanese city pop (late 80s golden age), warm Rhodes electric piano, lush analog synth pads, sophisticated jazzy chords, smooth funk guitar comping, melodic bass lines, gentle tight drums, BPM 110, emotive low female vocal with vintage reverb and subtle vibrato, deeply nostalgic mellow groove, bittersweet late-night city melancholy, vintage tape warmth",
        lyrics="""[Intro, 잔잔한 로즈 피아노 + 도시 잔향]

[Verse 1]
좁은 골목 불빛 아래
혼자 걷던 그 밤처럼
오늘도 같은 길 위에서
너의 흔적을 더듬어

[Pre-Chorus, 따뜻한 신스 패드]
인쇄소 불빛 사이로
스며든 새벽 공기
그때 네 목소리가
아직 귓가에 맴돌아

[Chorus, 재지한 코드 + 하모니]
을지로 블루스, 네가 머물던 거리
식어버린 커피처럼
우리도 그렇게 멀어졌지만
너만은 선명히 남아

[Verse 2, 스무스 펑크 기타]
밤새 걷던 그 거리에
이제는 나 혼자야
계절이 바뀌어 가도
마음은 그날에 멈춰

[Pre-Chorus, 멜로딕 베이스]
말없이 나눈 시선들
지금은 흐릿한데
너의 온기만 잔향처럼
남아 있어

[Chorus, 감정이 쌓이는 진행]
을지로 블루스, 불빛이 많은 그곳
나만 조용히 멈춘 채
노래는 흐르지만 마음은 속삭여
사랑은 끝났다는 걸

[Bridge, 일렉트릭 피아노 솔로]
(돌아갈 수 없어도)
(그 골목, 그 밤, 그 온기)
(우린 사라졌지만)
(이 거린 그대로인데)

[Final Chorus, 감정 클라이맥스]
을지로 블루스, 네가 머물던 거리
오늘도 네 이름을 부르다
누군가의 뒷모습에 너를 겹쳐보다
또 한 번, 마음을 접는다

[Outro, 도시 소음 + 페이드아웃]
(을지로, 모두가 웃는 그 밤)
(나만, 조용히 울고 있어)""",
    ),
]

_mock_index = 0


class MockAIProvider:
    """Mock AI provider for testing — no API calls."""
    PROVIDER_NAME = "mock"
    MODEL_NAME = "mock-draft"

    def generate_song_package(self, concept: str, locked: dict | None = None) -> SongPromptPackage:
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

    def generate_title(self, concept: str) -> str:
        return self.generate_song_package(concept).title

    def generate_style(self, concept: str) -> str:
        return self.generate_song_package(concept).style

    def generate_lyrics(self, concept: str) -> str:
        return self.generate_song_package(concept).lyrics


# ─── OpenAI Provider ─────────────────────────────────────────────────────────

class OpenAIProvider:
    PROVIDER_NAME = "openai"

    @property
    def MODEL_NAME(self):
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    @staticmethod
    def is_available() -> bool:
        return bool(os.getenv("OPENAI_API_KEY", "").strip())

    def _call(self, concept: str, generate: str = "all") -> dict:
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
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _make_user_prompt(concept, generate)},
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

    def generate_song_package(self, concept: str, locked: dict | None = None) -> SongPromptPackage:
        data = self._call(concept, "all")
        title = data.get("title", "").strip()
        lyrics = _format_lyrics(data.get("lyrics", ""))
        if not title:
            title = _title_from_lyrics(lyrics) or "제목 없음"
        return SongPromptPackage(
            title=title,
            style=data.get("style", ""),
            lyrics=lyrics,
            metadata={"ai_provider": "openai", "ai_model": self.MODEL_NAME,
                       "generated_at": datetime.now(timezone.utc).isoformat(),
                       "concept": concept, "lyric_chars": _lyrics_char_count(lyrics)},
        )

    def generate_title(self, concept: str) -> str:
        return self._call(concept, "title").get("title", "")

    def generate_style(self, concept: str) -> str:
        return self._call(concept, "style").get("style", "")

    def generate_lyrics(self, concept: str) -> str:
        return self._call(concept, "lyrics").get("lyrics", "")


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

    def _call(self, concept: str, generate: str = "all") -> dict:
        import requests
        api_key = os.getenv("GOOGLE_GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("GOOGLE_GEMINI_API_KEY not set")

        prompt_text = SYSTEM_PROMPT + "\n\n" + _make_user_prompt(concept, generate)

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

    def generate_song_package(self, concept: str, locked: dict | None = None) -> SongPromptPackage:
        data = self._call(concept, "all")
        title = data.get("title", "").strip()
        lyrics = _format_lyrics(data.get("lyrics", ""))
        if not title:
            title = _title_from_lyrics(lyrics) or "제목 없음"
        return SongPromptPackage(
            title=title,
            style=data.get("style", ""),
            lyrics=lyrics,
            metadata={"ai_provider": "gemini", "ai_model": self.MODEL_NAME,
                       "generated_at": datetime.now(timezone.utc).isoformat(),
                       "concept": concept, "lyric_chars": _lyrics_char_count(lyrics)},
        )

    def generate_title(self, concept: str) -> str:
        return self._call(concept, "title").get("title", "")

    def generate_style(self, concept: str) -> str:
        return self._call(concept, "style").get("style", "")

    def generate_lyrics(self, concept: str) -> str:
        return self._call(concept, "lyrics").get("lyrics", "")


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
