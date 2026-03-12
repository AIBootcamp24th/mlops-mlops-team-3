"""
champion_registry 유틸리티 테스트.
"""
from __future__ import annotations

import pytest

from src.utils.champion_registry import (
    champion_infer_key,
    champion_predictions_key,
    champion_s3_prefix,
    champion_train_key,
)


def test_champion_s3_prefix() -> None:
    assert champion_s3_prefix("run123") == "tmdb/run123"


def test_champion_train_key() -> None:
    assert champion_train_key("run123") == "tmdb/run123/train.csv"


def test_champion_infer_key() -> None:
    assert champion_infer_key("run123") == "tmdb/run123/infer.csv"


def test_champion_predictions_key() -> None:
    assert champion_predictions_key("run123", ds="20260313", ts="020000") == (
        "tmdb/run123/predictions_20260313_020000.csv"
    )


def test_champion_predictions_key_default() -> None:
    assert champion_predictions_key("run123") == "tmdb/run123/predictions_batch.csv"
