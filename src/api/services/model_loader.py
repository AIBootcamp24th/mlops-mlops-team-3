from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

import torch

from src.config import settings
from src.data.s3_io import download_file
from src.train.model import RatingRegressor

DEFAULT_FEATURE_COLS = ["budget", "runtime", "popularity", "vote_count"]


def get_feature_cols() -> list[str]:
    raw = os.getenv("API_FEATURE_COLS", "")
    if not raw.strip():
        return DEFAULT_FEATURE_COLS
    parsed = [item.strip() for item in raw.split(",") if item.strip()]
    return parsed or DEFAULT_FEATURE_COLS


def load_model() -> RatingRegressor:
    local_model_path = os.getenv("API_LOCAL_MODEL_PATH", "").strip()
    if local_model_path and Path(local_model_path).exists():
        state_dict = torch.load(local_model_path, map_location="cpu")
    else:
        model_s3_key = os.getenv("API_MODEL_S3_KEY", "").strip()
        if not model_s3_key:
            raise RuntimeError(
                "모델 파일이 없습니다. API_LOCAL_MODEL_PATH 또는 API_MODEL_S3_KEY를 설정하세요."
            )

        with TemporaryDirectory() as tmpdir:
            local_model = str(Path(tmpdir) / "rating_model.pt")
            download_file(settings.aws_s3_model_bucket, model_s3_key, local_model)
            state_dict = torch.load(local_model, map_location="cpu")

    model = RatingRegressor(input_dim=len(get_feature_cols()))
    model.load_state_dict(state_dict)
    model.eval()
    return model
