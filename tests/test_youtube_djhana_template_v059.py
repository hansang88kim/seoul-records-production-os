"""
tests/test_youtube_djhana_template_v059.py — v1.0.0-alpha.59

The user provided a fixed Seoul Records / DJ HANA title + description frame
(mood keywords, FAQ, copyright block) and asked that ONLY the tracklist be
auto-filled from the actually uploaded audio, keeping everything else
constant. They also enumerated several YouTube setup options (monetization
on, content self-rating "해당 사항 없음", end screen, cards, AI-use "예",
not-made-for-kids) — of which only made_for_kids is settable via the Data
API; the rest have no API and must be done in Studio, so we surface them
as a post-upload checklist rather than pretending to automate them.
"""
from __future__ import annotations

import re

import pytest

from services.youtube import metadata_generator as MG
from services.youtube import seo_description as MG_SEO


def _chapters():
    return [
        {"timestamp": "00:00", "title": "Lazy Paradise"},
        {"timestamp": "3:24", "title": "Sunset Fever"},
        {"timestamp": "1:03:10", "title": "Take Me High"},
    ]


def test_default_title_is_seo_playlist_frame():
    # v1.0.0-alpha.98: DJ HANA removed → SEO city-pop PLAYLIST title frame.
    meta = MG.generate_all_metadata("", "Korea", 61, "", "", 60)
    assert "서울 시티팝" in meta["title"]
    assert "Korean Seoul City pop Vol.61" in meta["title"]
    assert "[Playlist]" in meta["title"]
    assert "DJ HANA" not in meta["title"]


def test_description_has_fixed_frame_sections():
    # no API key in tests → deterministic fallback template
    desc = MG_SEO.generate_seo_description(_chapters(), use_llm=False)
    assert "🏖️ 감성 키워드" in desc
    assert "🎧 추천 무드" in desc
    assert "DJ HANA" not in desc          # persona removed
    assert "FAQ 자주 묻는 질문" in desc
    assert "Q1." in desc and "Q3." in desc
    assert "🎵 저작권 안내" in desc
    assert "© All rights reserved." in desc
    assert "#KoreanCityPop" in desc       # SEO hashtags


def test_tracklist_is_injected_from_real_chapters():
    desc = MG_SEO.generate_seo_description(_chapters(), use_llm=False)
    # Timestamps normalised to HH:MM:SS, numbered, real titles used verbatim.
    assert "00:00:00  01. Lazy Paradise" in desc
    assert "00:03:24  02. Sunset Fever" in desc
    assert "01:03:10  03. Take Me High" in desc
    # Track count reflects the real chapters.
    assert "총 3곡" in desc


def test_tracklist_does_not_fabricate_feat_names():
    """The generated tracklist must use ONLY the real chapter titles."""
    desc = MG_SEO.generate_seo_description(_chapters(), use_llm=False)
    assert "(feat." not in desc


def test_no_chapters_uses_placeholder_not_fake_list():
    desc = MG_SEO.generate_seo_description([], use_llm=False)
    assert "자동으로 생성" in desc or "자동 생성" in desc
    # Must not contain a numbered real-looking track line.
    assert not re.search(r"\n00:00:00  01\. \w", desc)


def test_timestamp_normalisation():
    assert MG._normalise_timestamp("0:00") == "00:00:00"
    assert MG._normalise_timestamp("3:24") == "00:03:24"
    assert MG._normalise_timestamp("1:03:10") == "01:03:10"
    assert MG._normalise_timestamp("12:50") == "00:12:50"


def test_made_for_kids_false_is_in_payload():
    """The one YouTube setting that IS API-settable from the user's list."""
    from services.youtube.upload_payload_service import build_upload_payload
    payload = build_upload_payload("T", "d", ["citypop"])
    assert payload["status"]["selfDeclaredMadeForKids"] is False


def test_studio_manual_steps_cover_the_non_api_options():
    steps = MG.STUDIO_MANUAL_STEPS
    joined = " ".join(steps)
    # Each option the user asked for that the API cannot do must be listed.
    assert "수익 창출" in joined
    assert "자가 평가" in joined or "해당 사항 없음" in joined
    assert "최종 화면" in joined
    assert "카드" in joined
    assert "AI 사용" in joined or "변경된 콘텐츠" in joined


def test_generate_all_metadata_exposes_studio_steps():
    meta = MG.generate_all_metadata("", "", 1, "", "", 60)
    assert "studio_manual_steps" in meta
    assert len(meta["studio_manual_steps"]) >= 5


def test_ui_renders_studio_checklist_helper():
    from pathlib import Path
    src = Path("app/tabs/youtube_package.py").read_text(encoding="utf-8")
    assert "_render_studio_manual_checklist" in src
    assert "STUDIO_MANUAL_STEPS" in src
    assert "monetization" in src  # one-click monetization link


def test_legacy_template_still_available_when_opted_out():
    meta = MG.generate_all_metadata("Korea CityPop", "Korea", 1, "",
                                    "", 60, use_seo_template=False)
    # Old English auto-description path, not the SEO playlist frame.
    assert "[Playlist]" not in meta["title"]
    assert "감성 키워드" not in meta["description"]
