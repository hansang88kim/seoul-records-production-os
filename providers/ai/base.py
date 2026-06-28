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

GENRE: Retro Seoul city pop (1970s-80s influence), dreamy analog synths, mellow funk guitars, slow groove rhythm, vintage tape warmth, androgynous female vocals with soft reverb and subtle vibrato.

CRITICAL RULES:
- Language: Korean lyrics only (section labels + production cues in headers)
- Vocal: Low, mature, androgynous female vocal, nostalgic tone, soft reverb
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

LYRICS FORMAT — follow this EXACT structure for natural 3:30 duration.
Section headers carry production cues (Korean or English). Each line is a SHORT phrase (7-13 Korean characters, average 9). This precise length is what makes the song land at ~3:30.

EXACT STRUCTURE (10 sections, 280-340 chars total — SHORTER is better for 3:30):
[Intro, <production cue>]          ← NO lyrics (instrumental, leave empty)
[Verse 1]                          ← 4 lines, 7-12 chars each
[Pre-Chorus, <cue>]                ← 4 lines, 8-11 chars each
[Chorus, <cue>]                    ← 5 lines, 6-13 chars (hook line = Seoul place from title)
[Verse 2, <cue>]                   ← 4 lines, 8-12 chars each
[Pre-Chorus]                       ← 4 lines, 8-11 chars each
[Chorus, <cue>]                    ← 5 lines, same hook, slight variation
[Bridge, <cue>]                    ← 4 lines, 6-9 chars each (shorter, reflective)
[Final Chorus, <cue>]              ← 5 lines, climactic, 8-12 chars
[Outro, <cue>]                     ← 2 lines, 10-14 chars (a specific Seoul spot)

LINE LENGTH RULES (critical for 3:30 timing):
- Verse/Pre-Chorus lines: 7-11 Korean characters
- Chorus lines: 6-13 characters (first line = the hook with Seoul place)
- Bridge lines: 6-9 characters (shorter, slower)
- Outro lines: 10-14 characters
- NEVER write long run-on lines. Keep each line a short singable phrase.

FORMATTING (must be exact):
- Blank line between every section
- One lyric phrase per line (no commas joining multiple phrases)
- Intro has header only, no lyric lines under it
- Section labels stay in English: [Verse 1], [Chorus], [Bridge], [Outro]
- Production cues in the header after comma

Example of correct formatting (study the line lengths):
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

STYLE FORMAT — write a RICH retro Seoul city pop style (300-500 chars). Match these examples closely:

Example 1: "Retro Seoul city pop (1970s-80s influence), dreamy analog synths, mellow funk guitars, slow groove rhythm (BPM 112), vintage tape warmth, androgynous female vocals with soft reverb and subtle vibrato"

Example 2: "Retro Korean city pop (late 70s Seoul), mellow tempo (BPM 111), lo-fi vinyl texture, vintage electric piano, soft brass hits, gentle funk guitar, nostalgic androgynous female vocals with light reverb and vibrato, emotional night-drive atmosphere"

Example 3: "Retro Seoul city pop (early 1980s vibe), melancholic electric piano, lo-fi synth textures, steady bassline groove (BPM 110), ambient train sounds, nostalgic androgynous female vocals with analog saturation, quiet night journey feeling"

Required elements (vary each time):
- "Retro Seoul/Korean city pop" + era (late 70s / early 80s / 1970s-80s)
- Tempo: BPM 108-114 (state it explicitly)
- Keys/piano: vintage electric piano, melancholic electric piano, Rhodes
- Synths: dreamy analog synths, lo-fi synth textures
- Guitar: mellow funk guitar, gentle funk guitar
- Texture: lo-fi vinyl texture, vintage tape warmth, analog saturation
- Vocal: "androgynous female vocals with soft reverb and subtle vibrato"
- Atmosphere: emotional night-drive, quiet night journey, nostalgic Seoul night
- Optional: soft brass hits, ambient train sounds, steady bassline groove

Always include "androgynous female vocals" and "BPM 108-114". Keep it evocative and cohesive like the examples.

Lyrics: realistic, lyrical, specific Seoul places and scenes. Concrete imagery (버스 정류장, 카페, 골목, 가로등, 네온). Varied sentence endings, no instrument names in sung lines. Original only — never copy existing songs."""


def _make_user_prompt(concept: str, generate: str = "all") -> str:
    """Build user prompt for AI generation."""
    if generate == "title":
        return f"Concept: {concept}\n\nGenerate 1 short Korean song title. Return JSON: {{\"title\": \"...\"}}"
    if generate == "style":
        return f"Concept: {concept}\n\nGenerate Suno style tags (under 200 chars, English). Return JSON: {{\"style\": \"...\"}}"
    if generate == "lyrics":
        return f"Concept: {concept}\n\nGenerate Korean lyrics with section structure. Return JSON: {{\"lyrics\": \"...\"}}"

    return (
        f"Concept: {concept}\n\n"
        "Create a Seoul Records citypop song. Return JSON only:\n"
        '{"title": "Korean title", "style": "rich detailed Japanese city pop style (400-700 chars), MUST include BPM 108-116", "lyrics": "full lyrics with sections"}'
    )


# ─── Mock Provider ───────────────────────────────────────────────────────────

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
        style="Retro Korean city pop (late 70s Seoul), mellow tempo (BPM 111), lo-fi vinyl texture, vintage electric piano, soft brass hits, gentle funk guitar, dreamy analog synths, nostalgic androgynous female vocals with light reverb and subtle vibrato, vintage tape warmth, emotional night-drive atmosphere, quiet Seoul night journey feeling",
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
        style="Retro Seoul city pop (early 1980s vibe), melancholic electric piano, lo-fi synth textures, steady bassline groove (BPM 110), mellow funk guitar, ambient train sounds, dreamy analog synths, nostalgic androgynous female vocals with analog saturation and soft reverb, vintage tape warmth, quiet night journey feeling",
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
                       "generated_at": datetime.now(timezone.utc).isoformat(), "concept": concept},
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
                       "generated_at": datetime.now(timezone.utc).isoformat(), "concept": concept},
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
