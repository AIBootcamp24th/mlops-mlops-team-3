from pathlib import Path
import shutil

import pandas as pd
import torch

from src.config import settings
from src.constants import FEATURE_COLS
from src.infer.run_batch_infer import run_batch_inference
from src.train.model import RatingRegressor


def test_run_batch_inference_supports_checkpoint_dict(tmp_path, monkeypatch) -> None:
    model = RatingRegressor(input_dim=len(FEATURE_COLS), hidden_dims=(128, 64), dropout=0.2)
    checkpoint_path = Path(tmp_path) / "rating_model.pt"
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "feature_cols": FEATURE_COLS,
            "hidden_dims": [128, 64],
            "dropout": 0.2,
            "scaler_mean": [0.0, 0.0, 0.0, 0.0],
            "scaler_scale": [1.0, 1.0, 1.0, 1.0],
            "scaler_var": [1.0, 1.0, 1.0, 1.0],
        },
        checkpoint_path,
    )

    input_path = Path(tmp_path) / "input.csv"
    pd.DataFrame(
        {
            "original_language": ["ko", "ko"],
            "budget": [100.0, 200.0],
            "runtime": [100.0, 120.0],
            "popularity": [20.0, 30.0],
            "vote_count": [300.0, 500.0],
        }
    ).to_csv(input_path, index=False)

    uploaded_paths: list[Path] = []
    persisted_output = Path(tmp_path) / "uploaded_predictions.csv"

    def fake_download_file(bucket: str, key: str, local_path: str) -> str:
        if key == "models/test.pt":
            shutil.copy(checkpoint_path, local_path)
        elif key == "raw/input.csv":
            shutil.copy(input_path, local_path)
        else:
            raise AssertionError("unexpected s3 key")
        return local_path

    def fake_upload_file(local_path: str, bucket: str, key: str) -> str:
        shutil.copy(local_path, persisted_output)
        uploaded_paths.append(persisted_output)
        return f"s3://{bucket}/{key}"

    monkeypatch.setattr("src.infer.run_batch_infer.download_file", fake_download_file)
    monkeypatch.setattr("src.infer.run_batch_infer.upload_file", fake_upload_file)
    monkeypatch.setattr(settings, "aws_s3_model_bucket", "model-bucket")
    monkeypatch.setattr(settings, "aws_s3_raw_bucket", "raw-bucket")
    monkeypatch.setattr(settings, "aws_s3_pred_bucket", "pred-bucket")

    out_uri = run_batch_inference(
        model_s3_key="models/test.pt",
        input_s3_key="raw/input.csv",
        output_s3_key="pred/out.csv",
        feature_cols=FEATURE_COLS,
    )

    assert out_uri == "s3://pred-bucket/pred/out.csv"
    assert uploaded_paths

    out_df = pd.read_csv(uploaded_paths[0])
    assert "predicted_rating" in out_df.columns
    assert out_df["predicted_rating"].between(0.0, 10.0).all()
