from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import torch

from src.config import settings
from src.data.preprocess import filter_korean_movies
from src.data.s3_io import download_file, upload_file
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
        x = torch.tensor(df[feature_cols].values, dtype=torch.float32)

        model = RatingRegressor(input_dim=len(feature_cols))
        model.load_state_dict(torch.load(local_model, map_location="cpu"))
        model.eval()

        with torch.no_grad():
            pred = model(x).view(-1).numpy()

        out_df = df.copy()
        out_df["predicted_rating"] = pred
        out_df.to_csv(local_output, index=False)

        return upload_file(local_output, settings.aws_s3_pred_bucket, output_s3_key)
