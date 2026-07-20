"""
services/youtube/description_translator.py — v1.0.0-alpha.60

Translate the fixed Seoul Records / DJ HANA description frame into the
song's language when that language is NOT Korean (e.g. Thai, Vietnamese,
Indonesian, Japanese). The Korean frame is the source of truth; for a
foreign-language playlist we localise the human-readable copy (mood line,
FAQ, copyright notice) so the description reads natively to that audience.

Design decisions:
  * The TRACKLIST is never sent to the model and never translated — it is
    injected verbatim from the real uploaded audio (timestamps + exact
    filenames/titles). Only the surrounding prose frame is translated, then
    the untouched tracklist is spliced back in. This guarantees timestamps
    and track identifiers are never corrupted by the model.
  * Tags are intentionally NOT translated — they stay English for maximum
    city-pop search reach (handled in metadata_generator.generate_tags).
  * Provider order: OpenAI → Gemini → (no key / failure) original Korean.
    We NEVER hard-fail an upload because translation was unavailable; we
    fall back to the Korean frame and let the caller proceed.
  * No secrets are logged. API keys come from env only.

The title is short and brand-y ("[Playlist] 서울 시티팝 …"); by default we
also offer a translated title but keep the bracketed English tail so the
channel branding stays recognisable across languages.
"""
from __future__ import annotations

import json
import os
import re
import logging

logger = logging.getLogger(__name__)


# lyric_language (from providers/ai/languages.py) → human target language.
# Korean is the source; anything mapping to "Korean" means "no translation".
_LANG_NAMES = {
    "korean": "Korean",
    "japanese": "Japanese",
    "thai": "Thai",
    "vietnamese": "Vietnamese",
    "indonesian": "Indonesian (Bahasa Indonesia)",
    "english": "English",
    "spanish": "Spanish",
}

_TRACKLIST_MARKER = "🎧 Seoul City Pop / Retro Korean City Pop Playlist"
# v1.0.0-alpha.121: the marker line now carries the chosen city, so match it by
# shape instead of by the old fixed Seoul string.
_TRACKLIST_MARKER_RE = re.compile(r"^🎧 .*City Pop.*Playlist$", re.MULTILINE)


def needs_translation(language_key: str) -> bool:
    """True when the song language is a non-Korean supported language."""
    if not language_key:
        return False
    key = language_key.strip().lower()
    return key in _LANG_NAMES and key != "korean"


def _split_frame_and_tracklist(description: str) -> tuple[str, str, str]:
    """
    Split the DJ HANA description into (head, tracklist_block, tail) so the
    tracklist can be preserved verbatim. The tracklist sits between the
    '🎧 … Mixset / Playlist' marker and the 'FAQ 자주 묻는 질문' section.
    Returns ("", full, "") if the expected structure isn't found (caller
    then translates the whole thing, minus any numeric timestamp lines).
    """
    m = _TRACKLIST_MARKER_RE.search(description or "")
    if not m or "FAQ" not in description:
        return "", description, ""
    marker = m.group(0)
    head, rest = description.split(marker, 1)
    head = head + marker + "\n"
    # rest starts with the tracklist, then a blank line, then 'FAQ ...'
    faq_idx = rest.find("FAQ")
    tracklist_block = rest[:faq_idx]
    tail = rest[faq_idx:]
    return head, tracklist_block, tail


def _translation_prompt(text: str, target_language: str) -> str:
    return (
        f"You are a professional localizer for a music channel. Translate the "
        f"following YouTube description into {target_language}. This is for a "
        f"nostalgic city-pop / nu-disco playlist channel.\n\n"
        f"STRICT RULES:\n"
        f"- Translate naturally and idiomatically into {target_language}, as a "
        f"native music blogger would write it.\n"
        f"- Keep ALL emoji exactly where they are.\n"
        f"- Do NOT translate or alter: the brand names 'Seoul Records', "
        f"'Seoul City Pop', hashtags (words starting with #), or the "
        f"'© All rights reserved …' English legal line (keep that line in "
        f"English, you may append a natural {target_language} sentence before "
        f"it if helpful).\n"
        f"- Preserve the overall line/section structure and blank lines.\n"
        f"- Do NOT add commentary. Return ONLY the translated text.\n\n"
        f"Return a JSON object of the exact form {{\"translated\": \"...\"}} and "
        f"nothing else.\n\n"
        f"TEXT TO TRANSLATE:\n{text}"
    )


# ── General-purpose RAW LLM callers (v1.0.0-alpha.109) ───────────────────────
# Return the model's raw text output (NOT a translation-specific field). Env-only
# keys, never logged. Reused by seo_description (sections JSON) and
# concept_suggester (plain concept) — those need the raw output, not {"translated"}.
def _openai_chat(prompt: str, json_mode: bool = True) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import requests
        # NOTE: OpenAIProvider.MODEL_NAME is an INSTANCE @property — reading it off
        # the CLASS returns the property object (→ JSON TypeError). Read the env
        # directly, exactly like the working song-generation path does.
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4000,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json=body, timeout=60,
        )
        data = resp.json()
        if not isinstance(data, dict) or "choices" not in data:
            return None
        return (data["choices"][0]["message"]["content"] or "").strip() or None
    except Exception as e:
        logger.warning("OpenAI call failed: %s", type(e).__name__)
        return None


def _gemini_chat(prompt: str, json_mode: bool = True) -> str | None:
    api_key = os.getenv("GOOGLE_GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import requests
        from providers.ai.base import GeminiProvider
        models = GeminiProvider.list_models(api_key)
        model = models[0] if models else "gemini-2.5-flash"
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:generateContent?key={api_key}")
        resp = requests.post(url, json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 4000},
        }, timeout=60)
        data = resp.json()
        text = ""
        for c_item in data.get("candidates", []):
            for part in c_item.get("content", {}).get("parts", []):
                text += part.get("text", "")
        return text.replace("```json", "").replace("```", "").strip() or None
    except Exception as e:
        logger.warning("Gemini call failed: %s", type(e).__name__)
        return None


def call_llm_raw(prompt: str, json_mode: bool = True,
                 provider_order: tuple[str, ...] = ("openai", "gemini")) -> str | None:
    """Try providers in order; return the first non-empty RAW text output."""
    for prov in provider_order:
        out = _openai_chat(prompt, json_mode) if prov == "openai" else _gemini_chat(prompt, json_mode)
        if out:
            return out
    return None


def _call_openai(prompt: str) -> str | None:
    """Translation-specific: expects a {"translated": "..."} JSON object."""
    raw = _openai_chat(prompt, json_mode=True)
    if not raw:
        return None
    try:
        return str(json.loads(raw).get("translated", "")).strip() or None
    except Exception:
        return None


def _call_gemini(prompt: str) -> str | None:
    """Translation-specific: expects {"translated": "..."} JSON (or raw text)."""
    raw = _gemini_chat(prompt, json_mode=True)
    if not raw:
        return None
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            out = str(json.loads(m.group()).get("translated", "")).strip()
            if out:
                return out
        except Exception:
            pass
    return raw or None


def _translate_text(text: str, target_language: str,
                    provider_order: tuple[str, ...] = ("openai", "gemini")) -> str | None:
    prompt = _translation_prompt(text, target_language)
    for prov in provider_order:
        out = _call_openai(prompt) if prov == "openai" else _call_gemini(prompt)
        if out:
            logger.info("Description translated via %s → %s", prov, target_language)
            return out
    return None


def translate_description(description: str, language_key: str,
                          provider_order: tuple[str, ...] = ("openai", "gemini")) -> dict:
    """
    Translate the DJ HANA description frame into the song's language,
    preserving the tracklist verbatim.

    Returns a dict:
      {
        "translated": bool,       # whether translation actually happened
        "language": str,          # target language name (or "Korean")
        "description": str,       # final description (translated or original)
        "provider": str | None,   # which provider produced it, if any
      }

    Never raises for translation issues — on any failure or missing key it
    returns the original Korean description with translated=False.
    """
    key = (language_key or "").strip().lower()
    if not needs_translation(key):
        return {"translated": False, "language": "Korean",
                "description": description, "provider": None}

    target = _LANG_NAMES[key]
    head, tracklist_block, tail = _split_frame_and_tracklist(description)

    if head and tail:
        # Translate head + tail separately, keep tracklist verbatim.
        translated_head = _translate_text(head, target, provider_order)
        translated_tail = _translate_text(tail, target, provider_order)
        if translated_head and translated_tail:
            final = translated_head.rstrip() + "\n\n" + tracklist_block.strip() \
                    + "\n\n" + translated_tail.lstrip()
            # Figure out which provider succeeded (head's).
            prov = "openai" if os.getenv("OPENAI_API_KEY", "").strip() else "gemini"
            return {"translated": True, "language": target,
                    "description": final, "provider": prov}
        # Partial failure → fall back to original.
        return {"translated": False, "language": "Korean",
                "description": description, "provider": None}

    # Structure not recognised → translate whole thing but protect any
    # timestamp lines by not special-casing (model instructed to preserve).
    translated = _translate_text(description, target, provider_order)
    if translated:
        prov = "openai" if os.getenv("OPENAI_API_KEY", "").strip() else "gemini"
        return {"translated": True, "language": target,
                "description": translated, "provider": prov}
    return {"translated": False, "language": "Korean",
            "description": description, "provider": None}
