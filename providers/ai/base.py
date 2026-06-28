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

GENRE: Bright summer Korean city pop with J-pop nostalgic energy (early 80s Seoul). Crisp upbeat groove, sparkling electric piano, shimmering synths, tight funk guitar, punchy bass. Expressive low female vocals. The mood is REFRESHING yet WISTFUL — summer brightness carrying a quiet loneliness, the feeling of being isolated in a fast-changing city.

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
- Core feeling: bright summer nostalgia mixed with urban loneliness
- The narrator feels left behind / isolated as the city and people change fast
- Imagery: summer city scenes, neon lights, crowds you feel alone in, memories
  of someone gone, the contrast between lively streets and inner emptiness
- Bittersweet — not pure sadness, not pure cheer. Refreshing surface, lonely core.
- Examples of feeling: walking through a crowded summer Seoul night alone,
  watching the city move on without you, missing someone amid the neon glow
- Avoid clichés. Make it feel real and specific to modern Seoul life.

LYRICS FORMAT — STRICT line counts and character limits for natural 3:30 duration.
This is the MOST IMPORTANT rule. If lyrics are too long, the song runs 4:00-4:30 which is WRONG.
Section headers carry production cues. Section labels stay in English.

EXACT TEMPLATE (copy this structure precisely):

[Intro, <production cue>]
← NO lyric lines here. Header only. Instrumental.

[Verse 1]
← exactly 4 lines, each 7-11 Korean characters

[Pre-Chorus, <cue>]
← exactly 4 lines, each 8-9 characters

[Chorus, <cue>]
← exactly 5 lines, each 7-13 characters (line 1 = hook with Seoul place from title)

[Verse 2, <cue>]
← exactly 4 lines, each 8-12 characters

[Pre-Chorus]
← exactly 4 lines, each 8-9 characters

[Chorus, <cue>]
← exactly 5 lines, same hook with slight word changes

[Bridge, <cue>]
← exactly 4 lines, each 6-9 characters (SHORT, reflective)

[Final Chorus, <cue>]
← exactly 5 lines, each 8-12 characters (climactic)

[Outro, <cue>]
← exactly 2 lines, each 10-13 characters (a Seoul spot)

HARD LIMITS (NEVER violate):
- Each line is a SHORT phrase: 6-13 Korean characters. NEVER longer.
- Count characters per line. A line like "비가 내리는 서울의 골목길에 너와 나의 기억이" is TOO LONG (split it).
- Verse/Pre-Chorus: 4 lines each. Chorus: 5 lines. Bridge: 4 lines. Outro: 2 lines.
- TOTAL lyric characters (excluding headers): 280-340 MAX. Count and verify.
- If you exceed 340 characters, DELETE words until under 340.

CORRECT EXAMPLE (study the SHORT line lengths — 7-13 chars each):
[Verse 1]
종로 오거리에서
시계를 본 순간
너와 마주친 그 날이
불쑥 떠올랐어

[Chorus, Hook guitar riff + Harmony]
동대문에서 너를 떠올려
지나간 시간 속에서
익숙했던 그 거리 풍경이
왜 오늘 따라
그리운지 몰라

[Bridge, Lead guitar solo]
우린 끝났지만
마음은 계속 흘러
잊으려 해도
잊혀지지 않아

[Outro, Fading city echo]
동대문 네온 아래서
너는 아직 내 안에 있어

WRONG EXAMPLE (lines too long — DO NOT do this):
[Verse 1]
비가 내리는 서울의 골목길에 너와 나의 기억이 스며들어가  ← 28 chars, WAY too long
흔들리는 불빛과 함께 걷고 싶어 이 순간을 영원히  ← too long

STYLE FORMAT — write a RICH style: BRIGHT SUMMER city pop with nostalgic urban loneliness (300-500 chars). NO saxophone. The mood is REFRESHING and upbeat yet WISTFUL — the feeling of summer in a fast-changing city where you feel quietly isolated. Match these examples:

Example 1: "Bright summer Korean city pop with J-pop nostalgic energy (early 80s Seoul), crisp upbeat groove (BPM 114), sparkling electric piano, shimmering analog synths, tight rhythmic funk guitar, punchy slap bass, clean bright drums, expressive low female vocals with retro reverb, refreshing yet wistful mood, bittersweet urban loneliness in a fast-changing city"

Example 2: "Refreshing city pop with J-pop sophistication (early 80s Seoul summer), upbeat mid-tempo groove (BPM 115), glistening electric piano, bright analog synth stabs, choppy funk guitar, melodic slap bass, crisp drums, emotive low female vocals with vintage reverb and subtle vibrato, nostalgic and lonely under the city lights, summer-night melancholy"

Example 3: "Crisp summer Korean city pop (J-pop influenced, early 80s), driving funky groove (BPM 113), bright Rhodes piano, sparkling synth arpeggios, tight rhythm guitar comping, punchy bass, clean snappy drums, expressive female vocals with retro reverb, cheerful yet quietly isolated feeling, the loneliness of a fast-moving city, neon summer nostalgia"

Required elements (vary each time):
- Genre: "Bright/Refreshing/Crisp summer Korean city pop" + J-pop nostalgic + early 80s Seoul
- Tempo: BPM 112-116 (UPBEAT, not slow — state explicitly)
- Energy: crisp, upbeat, driving, sparkling, glistening (NOT calm/dreamy/mellow)
- Guitar: tight rhythmic funk guitar, choppy funk guitar comping
- Keys: sparkling/glistening electric piano, bright Rhodes
- Synths: shimmering analog synths, bright synth stabs/arpeggios
- Bass: punchy slap bass, melodic bass (energetic)
- Drums: clean bright/crisp/snappy drums
- Vocal: "expressive low female vocals with retro reverb and subtle vibrato"
- MOOD (critical): refreshing YET wistful, bittersweet urban loneliness, nostalgic and lonely in a fast-changing city, summer-night melancholy, cheerful yet quietly isolated

AVOID these words: calm, dreamy, mellow, gentle, soft groove, quiet (too sleepy).
USE these instead: bright, crisp, upbeat, sparkling, refreshing, driving — paired with the emotional loneliness.

CRITICAL: NEVER mention saxophone, sax, brass solos, or horn leads. Guitar+keys+synth driven J-citypop.



Lyrics: realistic, lyrical, specific Seoul places and scenes. Concrete imagery (버스 정류장, 카페, 골목, 가로등, 네온). Varied sentence endings, no instrument names in sung lines. Original only — never copy existing songs."""


def _make_user_prompt(concept: str, generate: str = "all") -> str:
    """Build user prompt for AI generation."""
    if generate == "title":
        return f"Concept: {concept}\n\nGenerate 1 short Korean song title (Seoul place-name based). Return JSON: {{\"title\": \"...\"}}"
    if generate == "style":
        return f"Concept: {concept}\n\nGenerate a rich J-pop nostalgic Korean city pop style (300-500 chars, English, NO saxophone, include BPM 110-114). Return JSON: {{\"style\": \"...\"}}"
    if generate == "lyrics":
        return (
            f"Concept: {concept}\n\n"
            "Generate Korean lyrics following the EXACT section template. "
            "CRITICAL: each line must be 6-13 Korean characters (SHORT phrases). "
            "Total lyrics 280-340 characters MAX so the song fits in 3:30. "
            "Structure: Intro(instrumental)/Verse1(4)/Pre-Chorus(4)/Chorus(5)/Verse2(4)/"
            "Pre-Chorus(4)/Chorus(5)/Bridge(4)/Final Chorus(5)/Outro(2). "
            'Return JSON: {"lyrics": "..."}'
        )

    return (
        f"Concept: {concept}\n\n"
        "Create a Seoul Records city pop song. Return JSON only.\n"
        "CRITICAL LYRICS RULE: each line 6-13 Korean chars (SHORT), total 280-340 chars MAX for 3:30 duration. "
        "Do NOT write long lines — the song must not exceed 3:30.\n"
        '{"title": "Korean Seoul place-name title", '
        '"style": "J-pop nostalgic Korean city pop, 300-500 chars, NO sax, BPM 110-114", '
        '"lyrics": "10 sections, short lines, 280-340 chars total"}'
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
        title="동대문에서 너를 떠올려",
        style="Bright summer Korean city pop with J-pop nostalgic energy (early 80s Seoul), crisp upbeat groove (BPM 114), sparkling electric piano, shimmering analog synths, tight rhythmic funk guitar, punchy slap bass, clean bright drums, expressive low female vocals with retro reverb and subtle vibrato, refreshing yet wistful, bittersweet urban loneliness in a fast-changing city, neon summer melancholy",
        lyrics="""[Intro, Guitar strums + busy city noise fade-in]

[Verse 1]
종로 오거리에서
시계를 본 순간
너와 마주친 그 날이
불쑥 떠올랐어

[Pre-Chorus, Bright comping guitar]
백화점 불빛 아래
수줍게 잡은 손
그 작은 떨림이
아직도 남아 있어

[Chorus, Hook guitar riff + Harmony]
동대문에서 너를 떠올려
지나간 시간 속에서
익숙했던 그 거리 풍경이
왜 오늘 따라
그리운지 몰라

[Verse 2, Muted funk guitar + warm keys]
길게 뻗은 지하철 소리
우리 대화 같아
조금씩 멀어지고
사라져가는 말들

[Pre-Chorus]
너 없는 주말 밤
혼자 걷는 서울
모든 게 그대로인데
너만 없다는 게 달라

[Chorus, Layered rhythm + emotional lift]
동대문에서 너를 떠올려
멀어진 기억이지만
이 노래가 울려 퍼지면
어디선가 넌
같은 하늘을 볼까

[Bridge, Lead guitar solo + pad swell]
우린 끝났지만
마음은 계속 흘러
잊으려 해도
잊혀지지 않아

[Final Chorus, Expanded groove + backing vocal]
동대문에서 너를 떠올려
바쁜 사람들 속에도
우리의 시간이 머물던
그 밤 공기 속에
네 목소릴 느껴

[Outro, Fading city echo + single guitar note]
동대문 네온 아래서
너는 아직 내 안에 있어""",
    ),
    SongPromptPackage(
        title="을지로 새벽 골목",
        style="Refreshing city pop with J-pop sophistication (early 80s Seoul summer), upbeat groove (BPM 115), glistening electric piano, bright synth stabs, choppy funk guitar, melodic slap bass, crisp drums, emotive low female vocals with vintage reverb and subtle vibrato, nostalgic and lonely under the city lights, summer-night melancholy",
        lyrics="""[Intro, Rhodes piano + distant traffic hum]

[Verse 1]
을지로 골목 끝에
불 켜진 작은 창
너와 마시던 커피
온기가 떠올라

[Pre-Chorus, Soft synth swell]
좁은 길 사이로
스며든 새벽 공기
그때 네 목소리가
귓가에 맴돌아

[Chorus, Warm groove + Layered harmony]
을지로 새벽 골목에서
혼자 너를 그려봐
지워진 줄 알았던 마음이
이 거리 위에
다시 번져가

[Verse 2, Nylon guitar + warm keys]
인쇄소 불빛 아래
밤새 걷던 우리
말없이 나눈 시선
이젠 흐릿해져

[Pre-Chorus]
식어버린 골목
너의 자리만 비어
모든 게 그대로인데
나만 멈춰 있어

[Chorus, Expanded rhythm + emotional lift]
을지로 새벽 골목에서
혼자 너를 그려봐
멀어진 시간 속에서도
네 미소만은
선명히 남아

[Bridge, Electric piano solo + pad swell]
돌아갈 수 없어도
마음은 그 골목에
잊으려 해봐도
발길이 멈춰

[Final Chorus, Full band + backing vocal]
을지로 새벽 골목에서
너의 이름 불러봐
우리가 머물던 그 밤이
아직 이곳에
숨 쉬고 있어

[Outro, Fading echo + single piano note]
을지로 불빛 아래서
너는 아직 내 곁에 있어""",
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
