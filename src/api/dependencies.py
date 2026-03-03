from __future__ import annotations

from functools import lru_cache

import torch
from fastapi import HTTPException

from src.api.services.model_loader import get_feature_cols, load_model


@lru_cache(maxsize=1)
def _cached_model() -> torch.nn.Module:
    return load_model()


def get_model_dep() -> torch.nn.Module:
    try:
        return _cached_model()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "모델 로드에 실패했습니다. "
                "`API_LOCAL_MODEL_PATH` 또는 `API_MODEL_S3_KEY` 설정을 확인하세요."
            ),
        ) from exc


def get_feature_cols_dep() -> list[str]:
    return get_feature_cols()
