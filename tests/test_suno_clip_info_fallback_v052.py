"""
tests/test_suno_clip_info_fallback_v052.py — v1.0.0-alpha.52

SunoCliProvider.get_clip_info: if `suno info <id>` returns nothing for our
8-char id prefix (some suno-cli builds only resolve `info` by the FULL
clip id), fall back to `suno list` and match by prefix — the same
resolution approach create_song() already uses right after generation.

This directly targets the reported symptom "생성까지는 되는데 다운로드를
안함" — if `info` silently returned {} for a valid clip, the whole
auto-download pipeline would abort with "일부 클립 정보 조회 실패" on
every single song, with no further recourse.
"""
from __future__ import annotations

from unittest import mock

from providers.suno.suno_cli_provider import SunoCliProvider


def _provider():
    p = SunoCliProvider.__new__(SunoCliProvider)  # skip __init__/auth
    p._bin = "suno"
    return p


def test_get_clip_info_uses_info_command_when_it_works():
    p = _provider()
    with mock.patch(
        "providers.suno.suno_cli_provider._run_suno_json",
        return_value={"data": {"id": "8df69261-full-uuid", "duration": 214.0}},
    ) as m:
        info = p.get_clip_info("8df69261")
    assert info == {"id": "8df69261-full-uuid", "duration": 214.0}
    m.assert_called_once()
    assert m.call_args[0][0] == ["info", "8df69261"]


def test_get_clip_info_falls_back_to_list_when_info_returns_empty():
    p = _provider()

    def fake_run(args, timeout=30, suno_bin=None):
        if args[0] == "info":
            return {"data": {}}   # info found nothing for the prefix
        if args[0] == "list":
            return {"data": [
                {"id": "b099c8aa-full-uuid-here", "duration": 171.0},
                {"id": "8df69261-full-uuid-here", "duration": 208.0},
            ]}
        raise AssertionError(f"unexpected command {args}")

    with mock.patch("providers.suno.suno_cli_provider._run_suno_json",
                    side_effect=fake_run):
        info = p.get_clip_info("8df69261")
    assert info == {"id": "8df69261-full-uuid-here", "duration": 208.0}


def test_get_clip_info_falls_back_to_list_when_info_raises():
    from providers.suno.suno_cli_provider import ProviderError
    p = _provider()

    def fake_run(args, timeout=30, suno_bin=None):
        if args[0] == "info":
            raise ProviderError("not_found", "clip not found")
        if args[0] == "list":
            return {"data": [{"id": "8df69261-xyz", "duration": 200.0}]}
        raise AssertionError(f"unexpected command {args}")

    with mock.patch("providers.suno.suno_cli_provider._run_suno_json",
                    side_effect=fake_run):
        info = p.get_clip_info("8df69261")
    assert info == {"id": "8df69261-xyz", "duration": 200.0}


def test_get_clip_info_returns_empty_when_truly_not_found():
    p = _provider()

    def fake_run(args, timeout=30, suno_bin=None):
        if args[0] == "info":
            return {"data": {}}
        if args[0] == "list":
            return {"data": [{"id": "unrelated-clip-id", "duration": 100.0}]}
        raise AssertionError(f"unexpected command {args}")

    with mock.patch("providers.suno.suno_cli_provider._run_suno_json",
                    side_effect=fake_run):
        info = p.get_clip_info("8df69261")
    assert info == {}


def test_get_clip_info_list_fallback_handles_dict_shaped_clips():
    """suno-cli 응답이 {"clips": [...]} 형태로 올 수도 있음 — 이미 다른 경로에서
    처리하는 패턴과 동일하게 대응."""
    p = _provider()

    def fake_run(args, timeout=30, suno_bin=None):
        if args[0] == "info":
            return {"data": {}}
        if args[0] == "list":
            return {"data": {"clips": [{"id": "8df69261-abc", "duration": 190.0}]}}
        raise AssertionError(f"unexpected command {args}")

    with mock.patch("providers.suno.suno_cli_provider._run_suno_json",
                    side_effect=fake_run):
        info = p.get_clip_info("8df69261")
    assert info == {"id": "8df69261-abc", "duration": 190.0}
