"""
tests/test_premium_export_registration_v081.py — Premium (form) renders register
as standard final deliverables (v1.0.0-alpha.81).

The Premium HTML/Playwright renderer writes 16:9 / 1:1 thumbnails to the SAME
standard export filenames the PIL Exports flow uses, then calls
asset_exporter.register_exports() so downstream (Exports checklist/preview,
Production QA, Video Renderer, YouTube Package) all pick them up. These tests
cover the registration mechanism (no Playwright needed — the render output is
simulated by writing files with the canonical names).
"""
from __future__ import annotations

import json

import pytest

from services.thumbnail import session_store as ss
from services.thumbnail import asset_exporter as ae
from services.thumbnail import asset_types as AT


@pytest.fixture(autouse=True)
def studio_tmp(monkeypatch, tmp_path):
    monkeypatch.setattr(ss, "_studio_root", lambda: tmp_path / "thumbnail_studio")
    yield


_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _write_export(sid, asset_type):
    exports = ss.session_path(sid) / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    p = exports / ae.export_filename(sid, asset_type)
    p.write_bytes(_PNG)
    return p


def test_rebuild_manifest_registers_both_ratios():
    sess = ss.create_session("korea", "night", "Form Vol.1")
    sid = sess["session_id"]
    _write_export(sid, AT.YOUTUBE_THUMBNAIL_16X9)
    _write_export(sid, AT.STREAMING_COVER_1X1)

    assets = ae.rebuild_manifest_from_disk(sid)
    by_type = {a["asset_type"]: a for a in assets}
    assert AT.YOUTUBE_THUMBNAIL_16X9 in by_type
    assert AT.STREAMING_COVER_1X1 in by_type
    assert by_type[AT.YOUTUBE_THUMBNAIL_16X9]["aspect_ratio"] == "16:9"
    assert by_type[AT.STREAMING_COVER_1X1]["aspect_ratio"] == "1:1"


def test_register_exports_writes_loadable_manifest():
    sess = ss.create_session("korea", "night", "Form Vol.2")
    sid = sess["session_id"]
    _write_export(sid, AT.YOUTUBE_THUMBNAIL_16X9)
    _write_export(sid, AT.STREAMING_COVER_1X1)

    mpath = ae.register_exports(sid)
    assert json.loads(open(mpath, encoding="utf-8").read())  # non-empty JSON
    loaded = ae.load_asset_manifest(sid)
    types = {a["asset_type"] for a in loaded}
    assert {AT.YOUTUBE_THUMBNAIL_16X9, AT.STREAMING_COVER_1X1} <= types


def test_register_only_lists_files_that_exist():
    sess = ss.create_session("korea", "night", "Form Vol.3")
    sid = sess["session_id"]
    _write_export(sid, AT.YOUTUBE_THUMBNAIL_16X9)  # only 16:9, no cover / video bg

    assets = ae.rebuild_manifest_from_disk(sid)
    types = {a["asset_type"] for a in assets}
    assert types == {AT.YOUTUBE_THUMBNAIL_16X9}


def test_registered_files_match_export_filename_convention_project_linked(tmp_path, monkeypatch):
    # project-linked session → filenames carry the project slug, and the
    # registration must find them via the same export_filename().
    proj = tmp_path / "song_projects" / "seoul-citypop-vol-01"
    proj.mkdir(parents=True)
    sess = ss.create_session("korea", "night", "Linked Vol.1", project_folder=str(proj))
    sid = sess["session_id"]
    p16 = _write_export(sid, AT.YOUTUBE_THUMBNAIL_16X9)
    assert "seoul-citypop-vol-01" in p16.name   # slug in filename

    assets = ae.rebuild_manifest_from_disk(sid)
    assert any(a["asset_type"] == AT.YOUTUBE_THUMBNAIL_16X9 for a in assets)
    assert assets[0]["path"].endswith(p16.name)


def test_premium_registered_thumbnail_shows_in_exports_checklist_path():
    # The Exports checklist checks exports_dir / export_filename(sid, atype);
    # a Premium-registered file must satisfy that exact path.
    sess = ss.create_session("korea", "night", "Form Vol.4")
    sid = sess["session_id"]
    p = _write_export(sid, AT.YOUTUBE_THUMBNAIL_16X9)
    checklist_path = ss.session_path(sid) / "exports" / ae.export_filename(sid, AT.YOUTUBE_THUMBNAIL_16X9)
    assert checklist_path == p and checklist_path.exists()
