from __future__ import annotations

import math

import torch

from src.api.schemas.predict import PredictRequest


def _sanitize_rating(raw_value: float) -> float:
    """서빙 응답에서 평점을 0~10 범위로 안정화한다."""
    if not math.isfinite(raw_value):
        return 0.0
    bounded = max(0.0, min(10.0, raw_value))
    return round(bounded, 2)


@torch.no_grad()
def predict_one(model: torch.nn.Module, feature_cols: list[str], item: PredictRequest) -> float:
    feature_map = item.model_dump()
    x = torch.tensor([[feature_map[col] for col in feature_cols]], dtype=torch.float32)
    pred = model(x)
    return _sanitize_rating(float(pred.view(-1).item()))


@torch.no_grad()
def predict_many(
    model: torch.nn.Module, feature_cols: list[str], items: list[PredictRequest]
) -> list[float]:
    rows = []
    for item in items:
        feature_map = item.model_dump()
        rows.append([feature_map[col] for col in feature_cols])

    x = torch.tensor(rows, dtype=torch.float32)
    pred = model(x).view(-1).tolist()
    return [_sanitize_rating(float(raw)) for raw in pred]
