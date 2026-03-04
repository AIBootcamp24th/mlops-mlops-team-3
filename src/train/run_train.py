from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pandas as pd
import torch
import wandb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader

from src.config import settings
from src.constants import FEATURE_COLS, TARGET_COL
from src.data.dataset import RatingsDataset
from src.data.preprocess import filter_korean_movies
from src.data.s3_io import download_file, upload_file
from src.data.sqs_client import delete_message, receive_message
from src.monitor.wandb_logger import init_run
from src.train.model import RatingRegressor
from src.train.trainer import evaluate, train_one_epoch


def _load_payload() -> dict[str, Any]:
    message = receive_message(settings.train_queue_url)
    if not message:
        raise RuntimeError("학습 큐 메시지가 없습니다.")
    payload = json.loads(message["Body"])
    payload["_receipt_handle"] = message["ReceiptHandle"]
    return payload


def main() -> None:
    payload = _load_payload()
    s3_key = payload["s3_key"]
    target_col = payload.get("target_col", TARGET_COL)
    feature_cols = payload.get("feature_cols", FEATURE_COLS)
    epochs = int(payload.get("epochs", 10))
    batch_size = int(payload.get("batch_size", 64))
    learning_rate = float(payload.get("learning_rate", 1e-3))
    hidden_dims = tuple(payload.get("hidden_dims", [128, 64]))
    dropout = float(payload.get("dropout", 0.2))

    run = init_run(
        {
            "s3_key": s3_key,
            "target_col": target_col,
            "feature_cols": feature_cols,
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "hidden_dims": hidden_dims,
            "dropout": dropout,
        }
    )

    with TemporaryDirectory() as tmpdir:
        local_data = str(Path(tmpdir) / "train.csv")
        download_file(settings.aws_s3_raw_bucket, s3_key, local_data)
        df = pd.read_csv(local_data)
        df = filter_korean_movies(df, require_language_col=True)
        df = df[feature_cols + [target_col]].dropna()

        train_df, val_df = train_test_split(df, test_size=0.2, random_state=42)
        scaler = StandardScaler()
        train_df = train_df.copy()
        val_df = val_df.copy()
        train_df[feature_cols] = scaler.fit_transform(train_df[feature_cols])
        val_df[feature_cols] = scaler.transform(val_df[feature_cols])

        train_ds = RatingsDataset(train_df, feature_cols=feature_cols, target_col=target_col)
        val_ds = RatingsDataset(val_df, feature_cols=feature_cols, target_col=target_col)
        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

        model = RatingRegressor(input_dim=len(feature_cols), hidden_dims=hidden_dims, dropout=dropout)
        optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

        for epoch in range(1, epochs + 1):
            train_loss = train_one_epoch(model, train_loader, optimizer)
            val_rmse = evaluate(model, val_loader)
            with torch.no_grad():
                full_x = torch.tensor(val_df[feature_cols].values, dtype=torch.float32)
                val_pred = model(full_x).view(-1).tolist()
            out_of_range_ratio = (
                sum(1 for value in val_pred if value < 0.0 or value > 10.0) / len(val_pred)
                if val_pred
                else 0.0
            )
            run.log(
                {
                    "epoch": epoch,
                    "train_loss": train_loss,
                    "val_rmse": val_rmse,
                    "val_out_of_range_ratio": out_of_range_ratio,
                }
            )

        model_path = str(Path(tmpdir) / "rating_model.pt")
        checkpoint = {
            "model_state_dict": model.state_dict(),
            "feature_cols": feature_cols,
            "target_col": target_col,
            "hidden_dims": list(hidden_dims),
            "dropout": dropout,
            "scaler_mean": scaler.mean_.tolist(),
            "scaler_scale": scaler.scale_.tolist(),
            "scaler_var": scaler.var_.tolist(),
        }
        torch.save(checkpoint, model_path)

        model_key = f"models/{run.id}/rating_model.pt"
        model_uri = upload_file(model_path, settings.aws_s3_model_bucket, model_key)
        run.summary["model_uri"] = model_uri

        artifact = wandb.Artifact(name=f"rating-model-{run.id}", type="model")
        artifact.add_file(model_path)
        run.log_artifact(artifact)

    delete_message(settings.train_queue_url, payload["_receipt_handle"])
    run.finish()


if __name__ == "__main__":
    main()
