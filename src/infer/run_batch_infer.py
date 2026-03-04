from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
import torch

from src.config import settings
from src.data.preprocess import filter_korean_movies
from src.data.s3_io import download_file, upload_file
from src.data.validation import validate_inference_frame
from src.train.model import RatingRegressor


def run_batch_inference(
    model_s3_key: str,
    input_s3_key: str,
    output_s3_key: str,
    feature_cols: list[str],
) -> str:
    with TemporaryDirectory() as tmpdir:
        local_model = str(Path(tmpdir) / "model.pt")
        local_input = str(Path(tmpdir) / "input.csv")
        local_output = str(Path(tmpdir) / "predictions.csv")

        download_file(settings.aws_s3_model_bucket, model_s3_key, local_model)
        download_file(settings.aws_s3_raw_bucket, input_s3_key, local_input)

        df = pd.read_csv(local_input)
        df = filter_korean_movies(df, require_language_col=True)

        checkpoint = torch.load(local_model, map_location="cpu")
        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
            checkpoint_feature_cols = checkpoint.get("feature_cols")
            if isinstance(checkpoint_feature_cols, list) and checkpoint_feature_cols:
                feature_cols = checkpoint_feature_cols

            validate_inference_frame(df, feature_cols)
            feature_frame = df[feature_cols]
            mean = np.array(checkpoint.get("scaler_mean", [0.0] * len(feature_cols)), dtype=float)
            scale = np.array(checkpoint.get("scaler_scale", [1.0] * len(feature_cols)), dtype=float)
            safe_scale = np.where(scale == 0.0, 1.0, scale)
            scaled_x = (feature_frame.values - mean) / safe_scale
            x = torch.tensor(scaled_x, dtype=torch.float32)

            hidden_dims = tuple(checkpoint.get("hidden_dims", [128, 64]))
            dropout = float(checkpoint.get("dropout", 0.2))
            model = RatingRegressor(
                input_dim=len(feature_cols), hidden_dims=hidden_dims, dropout=dropout
            )
            model.load_state_dict(checkpoint["model_state_dict"])
        else:
            validate_inference_frame(df, feature_cols)
            x = torch.tensor(df[feature_cols].values, dtype=torch.float32)
            model = RatingRegressor(input_dim=len(feature_cols))
            model.load_state_dict(checkpoint)
        model.eval()

        with torch.no_grad():
            pred = model(x).view(-1).numpy()
            pred = np.clip(pred, 0.0, 10.0)

        out_df = df.copy()
        out_df["predicted_rating"] = pred
        out_df.to_csv(local_output, index=False)

        return upload_file(local_output, settings.aws_s3_pred_bucket, output_s3_key)
