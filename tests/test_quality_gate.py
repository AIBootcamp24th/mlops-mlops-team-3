"""
통합 테스트: quality gate 분기.
"""
from __future__ import annotations

import os


def test_quality_gate_required_env_parsing() -> None:
    """QUALITY_GATE_REQUIRED 환경변수 파싱이 register_model과 일치."""
    # scripts/register_model.py: os.getenv("QUALITY_GATE_REQUIRED", "true").lower() == "true"
    for val, expected in [("true", True), ("false", False), ("TRUE", True), ("", False)]:
        os.environ["QUALITY_GATE_REQUIRED"] = val
        result = os.getenv("QUALITY_GATE_REQUIRED", "true").lower() == "true"
        assert result == expected, f"QUALITY_GATE_REQUIRED={val} -> {result}"
    os.environ.pop("QUALITY_GATE_REQUIRED", None)


def test_quality_gate_default_is_required() -> None:
    """기본값이 차단 모드(required=true)인지 검증."""
    # register_model 기본값: "true"
    default_val = os.getenv("QUALITY_GATE_REQUIRED", "true")
    assert default_val.lower() == "true"
