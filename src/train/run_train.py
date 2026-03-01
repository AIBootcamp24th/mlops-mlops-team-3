from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import torch
import wandb
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader

from src.config import settings
from src.data.dataset import RatingsDataset
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


def build_training_metadata(
    *,
    run_id: str,
    model_uri: str,
    val_rmse: float,
    feature_cols: list[str],
    target_col: str,
    train_s3_key: str,
    epochs: int,
    batch_size: int,
    learning_rate: float,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "model_uri": model_uri,
        "val_rmse": float(val_rmse),
        "feature_cols": feature_cols,
        "target_col": target_col,
        "train_s3_key": train_s3_key,
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "created_at": datetime.now(UTC).isoformat(),
    }


def main() -> None:
    payload = _load_payload()
    s3_key = payload["s3_key"]
    target_col = payload.get("target_col", "rating")
    feature_cols = payload.get("feature_cols", ["budget", "runtime", "popularity", "vote_count"])
    epochs = int(payload.get("epochs", 10))
    batch_size = int(payload.get("batch_size", 64))
    learning_rate = float(payload.get("learning_rate", 1e-3))

    run = init_run(
        {
            "s3_key": s3_key,
            "target_col": target_col,
            "feature_cols": feature_cols,
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
        }
    )

    with TemporaryDirectory() as tmpdir:
        local_data = str(Path(tmpdir) / "train.csv")
        download_file(settings.aws_s3_raw_bucket, s3_key, local_data)
        df = pd.read_csv(local_data)

        train_df, val_df = train_test_split(df, test_size=0.2, random_state=42)
        train_ds = RatingsDataset(train_df, feature_cols=feature_cols, target_col=target_col)
        val_ds = RatingsDataset(val_df, feature_cols=feature_cols, target_col=target_col)
        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

        model = RatingRegressor(input_dim=len(feature_cols))
        optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

        final_val_rmse = float("inf")
        for epoch in range(1, epochs + 1):
            train_loss = train_one_epoch(model, train_loader, optimizer)
            val_rmse = evaluate(model, val_loader)
            run.log({"epoch": epoch, "train_loss": train_loss, "val_rmse": val_rmse})
            final_val_rmse = val_rmse

        model_path = str(Path(tmpdir) / "rating_model.pt")
        torch.save(model.state_dict(), model_path)

        model_key = f"models/{run.id}/rating_model.pt"
        model_uri = upload_file(model_path, settings.aws_s3_model_bucket, model_key)
        run.summary["model_uri"] = model_uri
        run.summary["val_rmse"] = final_val_rmse
        run.summary["feature_cols"] = feature_cols
        run.summary["target_col"] = target_col

        artifact = wandb.Artifact(name=f"rating-model-{run.id}", type="model")
        artifact.add_file(model_path)
        run.log_artifact(artifact)

        metadata = build_training_metadata(
            run_id=run.id,
            model_uri=model_uri,
            val_rmse=final_val_rmse,
            feature_cols=feature_cols,
            target_col=target_col,
            train_s3_key=s3_key,
            epochs=epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
        )
        metadata_path = str(Path(tmpdir) / "training_metadata.json")
        with open(metadata_path, "w", encoding="utf-8") as fp:
            json.dump(metadata, fp, ensure_ascii=False, indent=2)

        metadata_key = f"models/{run.id}/training_metadata.json"
        metadata_uri = upload_file(metadata_path, settings.aws_s3_model_bucket, metadata_key)
        run.summary["metadata_uri"] = metadata_uri

    delete_message(settings.train_queue_url, payload["_receipt_handle"])
    run.finish()


if __name__ == "__main__":
    main()
