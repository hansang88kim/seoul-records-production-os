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

SYSTEM_PROMPT = """You are the A&R director and songwriter for Seoul Records, a Korean citypop music label.

Style rules:
- Genre: 1980-1990s Japanese nostalgic citypop adapted to Korean Seoul sensibility
- Language: Korean lyrics only (section labels like [Intro], [Chorus] in English)
- Vocal: Low, thick 20s female vocal, breath-driven, no belting
- Instruments: CP-70/DX7/Wurlitzer/FM bell/chorus guitar intro (no drums initially)
- BANNED: sax lead, drum fill-ins, tom fills, snare rolls, EDM risers, trot, enka, toy percussion
- BPM: 108-116, usually minor key
- Duration: MAXIMUM 3:30 (DO NOT exceed 3 minutes 30 seconds)
- Title: Short natural Korean (like "밤이 지나면"), no region+emotion combos
- Lyrics: Realistic lyrical young-adult, varied endings
- Lyrics length: 120-140 words MAX to keep song under 3:30
- CRITICAL: shorter lyrics = shorter song. Keep it concise.
- Theme: Seoul locale, 1980-90s/Y2K mood

Lyrics structure:
[Intro] - "(4마디 음원 (instrumental only))"
[Verse 1] - 3-4 lines (concise)
[Pre-Chorus] - 2 lines
[Chorus] - 3-4 lines (unique hook, memorable)
[Verse 2] - 3-4 lines
[Chorus] - same as first (repeat)
[Bridge] - 2 lines (optional, keep short)
[Outro] - "(4마디 음원 (instrumental only))"

No instrument names in lyrics. No "~다" overuse. Original only."""


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
        '{"title": "Korean title", "style": "tags under 200 chars, MUST include BPM 108-116", "lyrics": "full lyrics with sections"}'
    )


# ─── Mock Provider ───────────────────────────────────────────────────────────

MOCK_SONGS = [
    SongPromptPackage(
        title="늦은 전화",
        style="Japanese citypop, 112 BPM, A minor, DX7, chorus guitar, warm bass, soft synth, low female vocal, calm",
        lyrics="""[Intro]
(4마디 음원 (instrumental only))

[Verse 1]
새벽 두 시 불빛 아래
핸드폰만 내려다봐
보낸 말은 읽음 표시
대답 없는 밤이 길어

[Pre-Chorus]
괜찮다고 말해도
마음은 멈추질 않아

[Chorus]
늦은 전화 한 통이면
돌아갈 수 있을까
말없이 스쳐간 우리
다시 만날 수 있을까

[Verse 2]
택시 창에 비친 네온
흐려지는 거리 위로
주머니 속 메모 하나
차마 보내지 못한 말

[Pre-Chorus]
웃어봐도 소용없어
이 밤은 너무 길어

[Chorus]
늦은 전화 한 통이면
돌아갈 수 있을까
말없이 스쳐간 우리
다시 만날 수 있을까

[Bridge]
조금만 용기가 있었다면
이 밤도 달랐을까

[Outro]
(4마디 음원 (instrumental only))""",
    ),
    SongPromptPackage(
        title="서울 끝자락",
        style="Japanese citypop, 110 BPM, F# minor, CP-70, FM bell, mellow bass, synth pad, low female vocal, nostalgic",
        lyrics="""[Intro]
(4마디 음원 (instrumental only))

[Verse 1]
마지막 버스 지나가고
텅 빈 정류장에 서서
잡을 수 없는 시간처럼
너도 멀어져만 가

[Pre-Chorus]
돌아보면 별거 아닌데
왜 자꾸 생각나는지

[Chorus]
서울 끝자락 어딘가에
우리의 밤이 남아있어
아무도 모르는 그 골목
아직도 불이 켜져 있어

[Verse 2]
편의점 앞 벤치 위에
남겨둔 커피 한 잔
식어버린 온기처럼
우리도 그렇게 됐어

[Pre-Chorus]
잊으려고 걸어봐도
발걸음이 여길 향해

[Chorus]
서울 끝자락 어딘가에
우리의 밤이 남아있어
아무도 모르는 그 골목
아직도 불이 켜져 있어

[Bridge]
한 번만 더 만날 수 있다면
그때는 놓지 않을게

[Outro]
(4마디 음원 (instrumental only))""",
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
                "temperature": 0.85,
                "max_tokens": 2000,
            },
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)

    def generate_song_package(self, concept: str, locked: dict | None = None) -> SongPromptPackage:
        data = self._call(concept, "all")
        return SongPromptPackage(
            title=data.get("title", ""),
            style=data.get("style", ""),
            lyrics=data.get("lyrics", ""),
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
        return os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    @staticmethod
    def is_available() -> bool:
        return bool(os.getenv("GOOGLE_GEMINI_API_KEY", "").strip())

    def _call(self, concept: str, generate: str = "all") -> dict:
        import requests
        api_key = os.getenv("GOOGLE_GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("GOOGLE_GEMINI_API_KEY not set")

        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.MODEL_NAME}:generateContent?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": SYSTEM_PROMPT + "\n\n" + _make_user_prompt(concept, generate)}]}],
                "generationConfig": {"temperature": 0.85, "maxOutputTokens": 2000},
            },
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)

    def generate_song_package(self, concept: str, locked: dict | None = None) -> SongPromptPackage:
        data = self._call(concept, "all")
        return SongPromptPackage(
            title=data.get("title", ""),
            style=data.get("style", ""),
            lyrics=data.get("lyrics", ""),
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
