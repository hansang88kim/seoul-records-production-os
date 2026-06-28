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

SYSTEM_PROMPT = """You are the A&R director and songwriter for Seoul Records, a Korean city pop label.

GENRE: Classic Korean city pop (late 70s-early 80s Seoul style), warm Rhodes piano, analog synths with tape noise, vintage slow groove, sentimental female vocals with lo-fi warmth, nostalgic Seoul street mood.

CRITICAL RULES:
- Language: Korean lyrics only (section labels in English)
- Vocal: Low, thick, sentimental female vocal with lo-fi warmth
- BPM: 108-116 (usually 112)
- Duration: TARGET exactly 3:30 (3 minutes 30 seconds). Keep lyrics tight.
- BANNED: sax lead, drum fill-ins, tom fills, snare rolls, EDM risers, trot, enka, toy percussion
- Title: Short natural Korean (like "남산타워에서 보낸 편지", "밤이 지나면")
- Original lyrics only, no copying

LYRICS FORMAT (use inline production cues in section headers like the example):
[Intro, Synth brass hit + City FX]
[Verse 1]
(4 lines Korean)
[Pre-Chorus, Bright synth build]
(4 lines Korean)
[Chorus, Hooky groove + Vocal layering]
(5 lines Korean, memorable hook)
[Verse 2, Funk guitar loop + Light percussion]
(4 lines Korean)
[Pre-Chorus, Arpeggio synth flow]
(4 lines Korean)
[Chorus, Expanded harmony + Brass stabs]
(5 lines Korean, same hook with slight variation)
[Bridge, Emotional synth solo]
((4 lines Korean in parentheses, soft))
[Final Chorus, Full band + Bright climax]
(5 lines Korean, climactic)
[Outro, Rhodes piano + Fade FX]
((2 lines Korean in parentheses))

Total lyrics ~150-180 words to fit 3:30. Natural lyrical Korean, varied endings.
No instrument names inside the sung lyric lines themselves (only in section headers)."""


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
        '{"title": "Korean title", "style": "Classic Korean city pop style description, MUST include BPM 108-116", "lyrics": "full lyrics with sections"}'
    )


# ─── Mock Provider ───────────────────────────────────────────────────────────

MOCK_SONGS = [
    SongPromptPackage(
        title="남산타워에서 보낸 편지",
        style="Classic Korean city pop (early 80s Seoul), warm Rhodes piano, analog synths with tape noise, slow vintage groove (BPM 112), sentimental female vocals, nostalgic Seoul street mood",
        lyrics="""[Intro, Synth brass hit + City FX]

[Verse 1]
서울 밤하늘 아래
붉게 빛나던 그 타워
너와 나란히 올랐던
그날의 기억이 선명해

[Pre-Chorus, Bright synth build]
손을 놓을까 말까
숨이 막히던 순간들
그 짧은 망설임이
이별이 될 줄 몰랐어

[Chorus, Hooky groove + Vocal layering]
남산타워에서 보낸 편지
그 안에 담긴 내 맘을
별빛보다 더 조용히
너에게 보내고 있어
잊지 못할 그 밤처럼

[Verse 2, Funk guitar loop + Light percussion]
네가 좋아하던 노래
지금 라디오에 나와
우연히 들은 그 멜로디
너를 향해 되돌아가

[Pre-Chorus, Arpeggio synth flow]
헤어졌던 그날 밤
웃으면서 인사했지
근데 마음은 아직
너를 놓지 못했어

[Chorus, Expanded harmony + Brass stabs]
남산타워에서 보낸 편지
조금 늦은 후회지만
이 노래를 들었다면
한 번쯤은 생각해 줘
우리가 걸었던 그 밤을

[Bridge, Emotional synth solo]
(가을 바람에 실려)
(너의 향기가 떠올라)
(잊은 줄 알았던 마음이)
(다시 피어나고 있어)

[Final Chorus, Full band + Bright climax]
남산타워에서 보낸 편지
밤하늘을 닮은 그날
한 줄씩 적어 내려간
내 진심을 기억해 줘
영원히 간직할 너라는 계절

[Outro, Rhodes piano + Fade FX]
(남산타워 위에서 쓴 편지 한 장)
(너에게 도착하길 바래)""",
    ),
    SongPromptPackage(
        title="늦은 골목 불빛",
        style="Classic Korean city pop (early 80s Seoul style), warm Rhodes piano, mellow analog synth pads with tape warmth, slow vintage groove (BPM 110), soft sentimental female vocals, late-night Seoul alley mood",
        lyrics="""[Intro, Warm Rhodes + Vinyl crackle]

[Verse 1]
골목 끝 작은 불빛
혼자 켜져 있던 그곳
너를 기다리던 밤이
아직도 거기 멈춰 있어

[Pre-Chorus, Soft synth swell]
지나간 계절처럼
너도 멀어져 갔지만
이 거리 어딘가엔
우리 흔적이 남아

[Chorus, Smooth groove + Layered vocals]
늦은 골목 불빛 아래
나는 아직 서성여
돌아올 리 없는 너를
오늘도 그려보고 있어
식지 않는 그 밤처럼

[Verse 2, Chorus guitar + Light brush drums]
편의점 창에 비친
흐릿한 내 얼굴 위로
너의 미소가 겹쳐져
자꾸만 멈춰 서게 해

[Pre-Chorus, Rising arpeggio]
잊으려 애써봐도
발걸음은 이곳으로
마음이 기억하는
그 골목 그 불빛

[Chorus, Expanded harmony + Warm brass]
늦은 골목 불빛 아래
나는 아직 서성여
돌아올 리 없는 너를
오늘도 그려보고 있어
식지 않는 그 밤처럼

[Bridge, Tender synth solo]
(차가운 밤공기 속에)
(너의 온기를 찾아)
(꺼지지 않는 불빛처럼)
(나는 여기 남아있어)

[Final Chorus, Full band + Bright climax]
늦은 골목 불빛 아래
이제는 알 것 같아
놓지 못한 그 마음이
오늘도 나를 붙잡아
영원히 빛날 너라는 밤

[Outro, Rhodes piano + Fade FX]
(골목 끝 그 불빛 하나)
(아직도 너를 비춰)""",
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

        prompt_text = SYSTEM_PROMPT + "\n\n" + _make_user_prompt(concept, generate)

        # Try the configured model, then fall back to known-good models
        models_to_try = [self.MODEL_NAME, "gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash"]
        seen = set()
        last_error = ""

        for model in models_to_try:
            if model in seen:
                continue
            seen.add(model)

            try:
                resp = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{"parts": [{"text": prompt_text}]}],
                        "generationConfig": {
                            "temperature": 0.9,
                            "maxOutputTokens": 4000,
                            "responseMimeType": "application/json",
                        },
                    },
                    timeout=60,
                )

                if resp.status_code != 200:
                    try:
                        last_error = resp.json().get("error", {}).get("message", "")[:150]
                    except Exception:
                        last_error = f"HTTP {resp.status_code}"
                    logger.warning("Gemini model %s failed: %s", model, last_error)
                    continue

                data = resp.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    last_error = "응답에 candidates 없음 (안전 필터 차단 가능)"
                    continue

                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    last_error = "응답에 content 없음"
                    continue

                content = parts[0].get("text", "").strip()
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                return json.loads(content)

            except requests.exceptions.RequestException as e:
                last_error = f"네트워크: {type(e).__name__}"
                continue
            except json.JSONDecodeError as e:
                last_error = f"JSON 파싱 실패: {str(e)[:80]}"
                continue

        raise RuntimeError(f"Gemini 생성 실패 — {last_error}")

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
