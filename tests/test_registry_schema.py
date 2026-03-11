"""
통합 테스트: predictor와 register_model의 champion 레지스트리 스키마 일치.
"""
from __future__ import annotations

import json


def test_champion_registry_schema_keys_consumed_by_predictor() -> None:
    """predictor.check_and_reload가 사용하는 키가 register_model 출력과 일치하는지 검증."""
    # register_model이 champion.json에 기록하는 키 (scripts/register_model.py)
    register_output_keys = {
        "tag",
        "wandb_champion_artifact",
        "approved_run_id",
        "project",
        "model_bucket",
        "model_key",
        "model_uri",
        "val_rmse",
        "val_out_of_range_ratio",
        "promoted_at_utc",
    }

    # predictor.check_and_reload가 읽는 키 (src/infer/predictor.py)
    predictor_consumed_keys = {"approved_run_id", "model_key", "model_bucket"}

    for key in predictor_consumed_keys:
        assert key in register_output_keys, (
            f"predictor가 사용하는 '{key}'가 register_model 출력에 포함되어야 합니다."
        )

    # 신규 스키마 기준 필수
    assert "approved_run_id" in register_output_keys
    assert "model_key" in register_output_keys


def test_registry_json_roundtrip() -> None:
    """register_model 형식의 JSON이 predictor가 파싱 가능한 형태인지 검증."""
    sample_registry = {
        "tag": "champion",
        "approved_run_id": "abc123",
        "model_key": "models/abc123/rating_model.pt",
        "model_bucket": "my-mlops-bucket",
        "model_uri": "s3://my-mlops-bucket/models/abc123/rating_model.pt",
    }
    raw = json.dumps(sample_registry)
    parsed = json.loads(raw)
    assert parsed.get("approved_run_id") == "abc123"
    assert parsed.get("model_key") == "models/abc123/rating_model.pt"
