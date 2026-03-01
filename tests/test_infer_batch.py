import shutil
from pathlib import Path

import pandas as pd
import pytest
import torch

from src.infer import run_batch_infer as infer_mod
from src.train.model import RatingRegressor


def _create_model_file(path: Path) -> None:
    model = RatingRegressor(input_dim=4)
    torch.save(model.state_dict(), path)


def test_run_batch_inference_success(tmp_path, monkeypatch) -> None:
    model_path = tmp_path / "model.pt"
    input_path = tmp_path / "input.csv"
    _create_model_file(model_path)

    pd.DataFrame(
        [
            {"budget": 100.0, "runtime": 120.0, "popularity": 1.2, "vote_count": 10.0},
            {"budget": 200.0, "runtime": 110.0, "popularity": 2.5, "vote_count": 20.0},
        ]
    ).to_csv(input_path, index=False)

    uploaded = {"key": "", "uri": ""}

    def fake_download_file(bucket: str, key: str, local_path: str) -> str:
        if key.endswith("rating_model.pt"):
            shutil.copy(model_path, local_path)
        else:
            shutil.copy(input_path, local_path)
        return local_path

    def fake_upload_file(local_path: str, bucket: str, key: str) -> str:
        out_df = pd.read_csv(local_path)
        assert "predicted_rating" in out_df.columns
        uploaded["key"] = key
        uploaded["uri"] = f"s3://{bucket}/{key}"
        return uploaded["uri"]

    monkeypatch.setattr(infer_mod, "download_file", fake_download_file)
    monkeypatch.setattr(infer_mod, "upload_file", fake_upload_file)

    uri = infer_mod.run_batch_inference(
        model_s3_key="models/run-a/rating_model.pt",
        input_s3_key="tmdb/latest/train.csv",
        output_s3_key="predictions/tmdb/run-a/predictions.csv",
        feature_cols=["budget", "runtime", "popularity", "vote_count"],
    )

    assert uri == uploaded["uri"]
    assert uploaded["key"] == "predictions/tmdb/run-a/predictions.csv"


def test_run_batch_inference_raises_on_missing_feature(tmp_path, monkeypatch) -> None:
    model_path = tmp_path / "model.pt"
    input_path = tmp_path / "input_missing_col.csv"
    _create_model_file(model_path)

    pd.DataFrame(
        [
            {"budget": 100.0, "runtime": 120.0, "popularity": 1.2},
        ]
    ).to_csv(input_path, index=False)

    def fake_download_file(bucket: str, key: str, local_path: str) -> str:
        if key.endswith("rating_model.pt"):
            shutil.copy(model_path, local_path)
        else:
            shutil.copy(input_path, local_path)
        return local_path

    monkeypatch.setattr(infer_mod, "download_file", fake_download_file)

    with pytest.raises(ValueError, match="feature 컬럼이 없습니다"):
        infer_mod.run_batch_inference(
            model_s3_key="models/run-b/rating_model.pt",
            input_s3_key="tmdb/latest/train.csv",
            output_s3_key="predictions/tmdb/run-b/predictions.csv",
            feature_cols=["budget", "runtime", "popularity", "vote_count"],
        )
