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
- Duration: TARGET 3:30 exactly. Keep lyrics tight (~150-180 words).
- BANNED inside sung lines: sax lead, drum fill-ins, tom fills, snare rolls, EDM, trot, enka

TITLE STYLE (Seoul place-name based, like the user's favorites):
- "명동에서 종로까지", "을지로 밤길에서", "서울의 밤", "청계천 거리"
- Use REAL Seoul locations: 명동, 종로, 을지로, 청계천, 뚝섬, 삼각지, 마포, 한강, 남산, 건대, 성수, 압구정, 신촌, 홍대, 이태원
- Natural, evocative, place + mood. Short.

LYRICS FORMAT — section headers carry production cues (Korean or English mix):
[Intro, 한강 바람 소리 + 로즈 피아노]
[Verse 1]
(4 lines Korean — concrete Seoul scene, real places)
[Pre-Chorus, 레트로 패드 + 드라이브 기타]
(4 lines Korean)
[Chorus, 따뜻한 리듬 + 코러스 하모니]
(5 lines Korean — hook references the Seoul place from the title)
[Verse 2, Nylon guitar + soft percussion]
(4 lines Korean — another Seoul location detail)
[Pre-Chorus, 섬세한 신스 레이어]
(4 lines Korean)
[Chorus, 감정이 쌓이는 진행]
(5 lines Korean — hook variation)
[Bridge, Electric piano solo + dreamy fade]
((4 lines Korean in parentheses, soft confession))
[Final Chorus, Emotional climax]
(5 lines Korean — climactic)
[Outro, 한강 소리 + 페이드아웃 피아노]
((2 lines Korean in parentheses — a specific Seoul spot))

STYLE FORMAT — write a RICH, professional Suno style prompt (Suno allows up to 1000 chars, so be detailed and evocative, 400-700 chars ideal):

Structure the style with these layers:
1. Genre + era: "Japanese city pop, late-1990s Seoul nostalgia"
2. Key + tempo: "A minor, 112 BPM, mid-tempo groove"
3. Keyboards: pick from CP-70 electric piano, DX7 FM keys, Rhodes, Wurlitzer, analog synth pads
4. Guitar: chorus guitar, clean funk guitar, nylon guitar, light wah
5. Bass: warm bass, slap bass, mellow sub bass
6. Texture: soft synth layers, tape warmth, vinyl crackle, plate reverb, lo-fi cassette texture, wide stereo
7. Vocal: "low thick female vocal, breath-driven, intimate, no belting, soft reverb, subtle vibrato"
8. Mood: calm, nostalgic, bittersweet, dreamy, late-night, neon-lit
9. Scene: "1990s Seoul night, city lights, midnight streets"

Example (rich, ~500 chars):
"Japanese city pop with late-1990s Seoul nostalgia, A minor, 112 BPM mid-tempo groove. Warm CP-70 electric piano and glassy DX7 FM keys lead, layered with soft analog synth pads. Chorus-drenched clean guitar, warm rounded bass, gentle brushed drums entering after a 4-bar intro. Low thick female vocal, breath-driven and intimate, soft plate reverb, subtle vibrato, no belting. Tape warmth, faint vinyl crackle, wide stereo image. Bittersweet, calm, neon-lit midnight Seoul mood, city lights reflecting on wet streets."

Vary key (A/D/F#/E/G minor), tempo (108-116 BPM), keyboards, and mood each time. Make it feel like a real professional producer wrote it.

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

MOCK_SONGS = [
    SongPromptPackage(
        title="뚝섬 가는 밤",
        style="Japanese city pop with late-1990s Seoul nostalgia, A minor, 112 BPM mid-tempo groove. Warm CP-70 electric piano and glassy DX7 FM keys lead, layered with soft analog synth pads. Chorus-drenched clean guitar, warm rounded bass, gentle brushed drums entering after a 4-bar intro. Low thick female vocal, breath-driven and intimate, soft plate reverb, subtle vibrato, no belting. Tape warmth, faint vinyl crackle, wide stereo image. Bittersweet, calm, neon-lit midnight Seoul mood, city lights on wet streets.",
        lyrics="""[Intro, 한강 바람 소리 + 로즈 피아노]

[Verse 1]
네가 먼저 웃어준 그날 밤
뚝섬 가는 길은 짧았지
손끝에 닿은 온기 하나로
모든 게 선명했던 계절

[Pre-Chorus, 레트로 패드 + 드라이브 기타]
네 말투, 네 걸음
아직 내 안에 살아
그때는 몰랐던 마음
이제서야 느껴져

[Chorus, 따뜻한 리듬 + 코러스 하모니]
뚝섬 가는 밤
우리의 마지막 여름
아무도 없는 강변에
너의 향기만 남았어
서울의 밤이 조용히 물들어

[Verse 2, Nylon guitar + soft percussion]
다정했던 목소리
버스 정류장 너머로 퍼지고
말없이 걷던 그 거리
이제는 나 혼자야

[Pre-Chorus, 섬세한 신스 레이어]
지나간 계절 속
네가 머문 자리를
천천히 돌아보며
나는 너를 부르고 있어

[Chorus, 감정이 쌓이는 진행]
뚝섬 가는 밤
조용히 너를 그리워해
멀어진 두 발자국 사이로
흔들리는 내 마음
다시 널 보내고 있어

[Bridge, Electric piano solo + dreamy fade]
(조금만 더 곁에 있었다면)
(우리의 시간은 달랐을까)
(이젠 모든 게 흐릿해져도)
(그 밤은 그대로 남아)

[Final Chorus, Emotional climax]
뚝섬 가는 밤
잊지 못할 그 장면
강물처럼 흘러가도
네 미소만은 선명해
이 밤은 너로 가득 차

[Outro, 한강 소리 + 페이드아웃 피아노]
(건대입구역 출구 앞)
(그 자리에 멈춰 선 나)""",
    ),
    SongPromptPackage(
        title="삼각지에서의 마지막 밤",
        style="Japanese city pop, early-1980s Seoul evening mood, F# minor, 110 BPM slow groove. Mellow Rhodes piano and Wurlitzer keys over lush analog synth pads. Soft nylon-string guitar, rounded mellow bass, light brushed percussion. Low warm female vocal, breath-driven, dreamy and nostalgic, gentle reverb, delicate falsetto touches. Vintage tape saturation, lo-fi cassette texture, plate reverb, wide stereo. Wistful, tender, late-night Seoul alley mood under amber streetlights.",
        lyrics="""[Intro, 트래픽 노이즈 & 잔잔한 전자피아노]

[Verse 1]
지하철 4호선 종착역 근처
네 손을 놓고 말았던 순간
불 꺼진 다방 유리창 너머
우리의 그림자만 남았어

[Pre-Chorus, 따뜻한 브라스 톤]
너의 뒷모습을 바라보다
한참을 서 있던 그 골목
말 한마디 못한 채
시간에 묻혔던 사랑

[Chorus, 감성 코러스 + 베이스 드라이브]
삼각지에서의 마지막 밤
그때 넌 울지 않았지만
네가 없는 이 거리는
지금도 내 맘을 울려
가로등만 너를 알고 있어

[Verse 2, 빈티지 기타 리프]
통닭집 앞 혼잣말처럼
자꾸만 네 이름을 부르고
사라진 웃음, 젖은 기억
밤마다 나를 흔들어

[Pre-Chorus, 피아노 + 신스 배킹]
이 골목엔 아직
너의 발자국이 살아
누가 대신 그 길을 걸어도
난 널 잊지 못할 거야

[Chorus, 가창감 있는 리드 & 하모니]
삼각지에서의 마지막 밤
마음은 아직 그 자리에
돌아갈 수는 없지만
기억은 떠나지 않아
그날 너와 멈춘 시간

[Bridge, 아날로그 베이스 + 드리미 신스]
(마지막이라도 안아줄 걸)
(그 말 한마디를 왜 못 했을까)
(지금이라도 말하고 싶어)
(삼각지의 밤은 길었어)

[Final Chorus, 감정 폭발 하이라이트]
삼각지에서의 마지막 밤
우리의 계절은 끝났지만
그날의 그 노래는
아직도 내 안에서 흐르고 있어
서울의 밤, 널 품고 있어

[Outro, 도시 소음 + 로즈 피아노 페이드]
(삼각지 사거리 불빛 아래)
(혼자 남은 나만의 밤)""",
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

        # Build model list: configured → live-queried available models → fallbacks
        models_to_try = [self.MODEL_NAME]
        available = self.list_models(api_key)
        # Prefer flash models (faster, cheaper), then any available
        flash_models = [m for m in available if "flash" in m and "lite" not in m]
        models_to_try += flash_models + available
        models_to_try += [
            "gemini-flash-latest", "gemini-3-flash", "gemini-3.5-flash",
            "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash",
        ]

        seen = set()
        last_error = "사용 가능한 모델을 찾지 못함"

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
                    logger.warning("Gemini model %s: %s", model, last_error)
                    continue

                data = resp.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    last_error = "안전 필터 차단 (candidates 없음)"
                    continue

                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    fr = candidates[0].get("finishReason", "")
                    last_error = f"응답 비어있음 (finishReason: {fr})"
                    continue

                content = parts[0].get("text", "").strip()
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                logger.info("Gemini success with model: %s", model)
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
