"""
app/ui/ai_songwriter.py — AI Songwriter (ChatGPT / Gemini)
Generates title, lyrics, and style based on a concept prompt.
API key from .env: OPENAI_API_KEY or GOOGLE_GEMINI_API_KEY
"""
from __future__ import annotations

import json
import os
import logging

logger = logging.getLogger(__name__)

# ─── Seoul Records prompt template ──────────────────────────────────────────

SYSTEM_PROMPT = """You are the A&R director and songwriter for Seoul Records, a Korean citypop music label.
Your job is to create song titles, lyrics, and style tags for AI music generation (Suno).

Style rules:
- Genre: 1980-1990s Japanese nostalgic citypop adapted to Korean Seoul sensibility
- Language: Korean lyrics only (section labels like [Intro], [Chorus] stay in English)
- Vocal: Low, thick 20s female vocal, breath-driven, no belting or high notes
- Instruments: CP-70/DX7/Wurlitzer/FM bell/chorus guitar for intro (no drums initially), drums enter naturally later
- BANNED: sax lead, drum fill-ins, tom fills, snare rolls, EDM risers, trot, enka, toy percussion
- BPM: 110-114, usually minor key
- Duration target: 3:30-4:00
- Title: Short, natural Korean song title (like "밤이 지나면", "늦은 대답"), no region+emotion combos
- Lyrics tone: Realistic, lyrical young-adult colloquial, varied sentence endings
- Theme: Seoul locale (Namsan, rooftop, city night), 1980-90s/Y2K mood

Lyrics structure:
[Intro] - exactly "(4마디 음원 (instrumental only))"
[Verse 1] - 4 lines
[Pre-Chorus] - 2 lines  
[Chorus] - 4 lines (unique hook phrase, never repeated from other songs)
[Verse 2] - 4 lines
[Pre-Chorus] - 2 lines
[Chorus] - 4 lines (same as first chorus)
[Bridge] - 2 lines (sung lyrics)
[Outro] - exactly "(4마디 음원 (instrumental only))"

Target: ~160 words lyrics text only (excluding section labels).
Each chorus hook phrase must be unique and memorable.
No instrument names in lyrics. No "~다" ending overuse. No personifying objects with "~야"."""

USER_PROMPT_TEMPLATE = """Create a new Seoul Records citypop song with this concept:

Concept: {concept}

Respond in this exact JSON format only (no markdown, no explanation):
{{
  "title": "Korean song title",
  "style": "comma-separated style tags under 200 characters for Suno",
  "lyrics": "full lyrics with [Intro], [Verse 1], etc sections"
}}"""


def generate_song_concept(concept: str, provider: str = "openai") -> dict | None:
    """
    Generate title/lyrics/style from a concept using AI API.
    Returns {"title": ..., "lyrics": ..., "style": ...} or None on failure.
    """
    if provider == "gemini":
        return _generate_gemini(concept)
    return _generate_openai(concept)


def _generate_openai(concept: str) -> dict | None:
    """Generate via OpenAI ChatGPT API."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        import requests
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_PROMPT_TEMPLATE.format(concept=concept)},
                ],
                "temperature": 0.85,
                "max_tokens": 2000,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]

        # Parse JSON from response
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)

    except Exception as e:
        logger.error("OpenAI generation failed: %s", e)
        return None


def _generate_gemini(concept: str) -> dict | None:
    """Generate via Google Gemini API."""
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        import requests
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{
                    "parts": [{
                        "text": SYSTEM_PROMPT + "\n\n" + USER_PROMPT_TEMPLATE.format(concept=concept)
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.85,
                    "maxOutputTokens": 2000,
                },
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["candidates"][0]["content"]["parts"][0]["text"]

        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)

    except Exception as e:
        logger.error("Gemini generation failed: %s", e)
        return None


def get_available_providers() -> list[str]:
    """Return list of configured AI providers."""
    providers = []
    if os.getenv("OPENAI_API_KEY", "").strip():
        providers.append("openai")
    if os.getenv("GOOGLE_GEMINI_API_KEY", "").strip():
        providers.append("gemini")
    return providers
