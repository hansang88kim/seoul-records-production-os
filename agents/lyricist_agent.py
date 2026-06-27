"""
LyricistAgent — generates original lyrics in the target language.

v0.1: Returns structured mock lyrics.
v0.2+: Will call LLM (OpenAI / Gemini) with language-pack-aware prompts.

RULES:
- Generate lyrics DIRECTLY in the target language. Never translate Korean source.
- Use city-mood vocabulary appropriate to the selected city (Seoul, Tokyo, etc.)
- Do not over-localize into traditional local music styles.
- Local flavor is OFF by default.
"""

from __future__ import annotations
import random
from typing import Optional

# ---------------------------------------------------------------------------
# Mock lyric pools per language pack
# ---------------------------------------------------------------------------

_MOCK_LYRICS: dict[str, list[str]] = {
    "ko_kr_seoul": [
        """[Verse]
도시의 불빛이 흐르는 밤
창문 너머 젖은 거리 위로
네 목소리가 멀어져 가도
이 도시는 여전히 빛나고 있어

[Pre-Chorus]
혼자 걷는 골목길에
네 향기가 남아 있어

[Chorus]
서울의 밤은 깊어가고
나는 여기 서 있어
빗속에 번진 네온 빛처럼
우리의 기억도 흩어져""",

        """[Verse]
늦은 밤 택시 창문 밖으로
강변의 빛이 흘러내리고
너와 함께 듣던 노래가
라디오에서 흘러나와

[Pre-Chorus]
그때의 우리로 돌아갈 수 없어
그래도 이 노래만큼은

[Chorus]
기억해줘 이 도시의 밤을
우리가 걸었던 그 길을
차갑게 식어버린 커피처럼
사랑도 그렇게 지나가""",
    ],
    "ja_jp_tokyo": [
        """[Verse]
深夜の東京 雨に濡れた
アスファルトに映る街の灯り
あなたの声が遠くなっても
この街はまだ輝いている""",
    ],
}

_DEFAULT_LYRICS = _MOCK_LYRICS["ko_kr_seoul"][0]


class LyricistAgent:
    """Generates original lyrics for a track."""

    def __init__(self, language_pack: str = "ko_kr_seoul"):
        self.language_pack = language_pack

    def generate_lyrics(
        self,
        title: str,
        style_tags: list[str],
        theme: Optional[str] = None,
    ) -> str:
        """
        Generate lyrics for the given title and style.

        v0.1: Returns mock lyrics from the language-pack pool.
        """
        pool = _MOCK_LYRICS.get(self.language_pack, _MOCK_LYRICS["ko_kr_seoul"])
        return random.choice(pool)

    def regenerate_verse(self, current_lyrics: str) -> str:
        """Regenerate only the verse section. v0.1: returns a new full mock."""
        return self.generate_lyrics("", [])

    def regenerate_chorus(self, current_lyrics: str) -> str:
        """Regenerate only the chorus section. v0.1: returns a new full mock."""
        return self.generate_lyrics("", [])
