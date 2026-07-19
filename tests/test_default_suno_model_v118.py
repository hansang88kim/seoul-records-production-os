"""v1.0.0-alpha.118 — Suno 기본 모델을 v5.5 → v5로 변경.

UI 셀렉트박스 기본 선택값과 model 키가 없을 때의 fallback이 모두 v5여야 한다.
"""
import json


def test_default_suno_model_is_v5_and_selectable():
    from app.ui.composer_panel import SUNO_MODELS, DEFAULT_SUNO_MODEL

    assert DEFAULT_SUNO_MODEL == "v5"
    # 셀렉트박스 index 계산이 ValueError 없이 되려면 목록에 있어야 한다
    assert DEFAULT_SUNO_MODEL in SUNO_MODELS


def test_song_lab_uses_shared_default():
    from app.tabs import song_lab
    from app.ui.composer_panel import SUNO_MODELS, DEFAULT_SUNO_MODEL

    # Auto Batch 셀렉트박스가 composer_panel의 목록/기본값을 그대로 쓴다
    assert song_lab.SUNO_MODELS is SUNO_MODELS
    assert song_lab.DEFAULT_SUNO_MODEL == DEFAULT_SUNO_MODEL


def test_prompt_dataclass_defaults_are_v5():
    from app.models import TrackPrompt
    from providers.ai.base import SongPromptPackage

    assert TrackPrompt().model == "v5"
    assert SongPromptPackage().model == "v5"


def test_snapshot_fallback_is_v5_when_model_missing(tmp_path):
    """settings에 model 키가 없어도 v5.5로 새지 않는다."""
    from services.metadata_consistency_service import create_prompt_snapshot

    snap = create_prompt_snapshot(
        track_dir=tmp_path / "track01",
        title="밤이 지나면",
        style="citypop",
        lyrics="…",
        settings={"vocal_gender": "Female"},   # model 없음
    )
    assert snap["model"] == "v5"

    saved = json.loads((tmp_path / "track01" / "prompt_snapshot.json").read_text(encoding="utf-8"))
    assert saved["model"] == "v5"


def test_no_v55_left_in_default_fallbacks():
    """기본값 자리에 v5.5가 남아있지 않은지(회귀 방지)."""
    from pathlib import Path

    targets = [
        "app/tabs/song_lab.py",
        "app/models.py",
        "providers/ai/base.py",
        "services/metadata_consistency_service.py",
        "workers/suno_generation_worker.py",
    ]
    root = Path(__file__).resolve().parent.parent
    for rel in targets:
        text = (root / rel).read_text(encoding="utf-8")
        assert '"v5.5")' not in text, f"{rel}에 v5.5 fallback이 남아있다"
        assert 'model: str = "v5.5"' not in text, f"{rel}에 v5.5 기본값이 남아있다"
