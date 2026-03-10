from __future__ import annotations

import json
import random
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import numpy as np
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
from src.data.validation import validate_training_frame
from src.monitor.wandb_logger import init_run
from src.train.model import RatingRegressor
from src.train.trainer import evaluate, train_one_epoch


def _load_payload(max_attempts: int = 6, wait_seconds: int = 10) -> dict[str, Any]:
    # dispatch 직후 SQS 반영/경합 이슈를 고려해 짧은 폴링 재시도를 수행한다.
    for attempt in range(1, max_attempts + 1):
        message = receive_message(settings.train_queue_url, wait_seconds=wait_seconds)
        if message:
            payload = json.loads(message["Body"])
            payload["_receipt_handle"] = message["ReceiptHandle"]
            return payload
        print(f"학습 큐 폴링 재시도 {attempt}/{max_attempts}: 메시지 없음")

    raise RuntimeError("학습 큐 메시지가 없습니다.")


def _set_global_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


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
    seed = int(payload.get("seed", settings.train_seed))
    tuning_profile = str(payload.get("tuning_profile", "default"))

    _set_global_seed(seed)

    run = init_run(
        {
            "s3_key": s3_key,
            "data_version": s3_key,
            "target_col": target_col,
            "feature_cols": feature_cols,
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "hidden_dims": hidden_dims,
            "dropout": dropout,
            "seed": seed,
            "tuning_profile": tuning_profile,
        }
    )

    run.summary["status"] = "running"
    run.summary["data_version"] = s3_key
    success = False
    try:
        with TemporaryDirectory() as tmpdir:
            local_data = str(Path(tmpdir) / "train.csv")
            download_file(settings.aws_s3_raw_bucket, s3_key, local_data)
            df = pd.read_csv(local_data)
            df = filter_korean_movies(df, require_language_col=True)
            df = df[feature_cols + [target_col]].dropna()
            validate_training_frame(df, feature_cols, target_col)

            # Guard tiny datasets from S3 (e.g., bootstrap/test uploads) so
            # orchestration can still proceed without split/BatchNorm errors.
            if len(df) < 3:
                repeat = (3 + len(df) - 1) // max(1, len(df))
                df = pd.concat([df] * repeat, ignore_index=True).head(3)
                print("경고: 학습 데이터가 3건 미만이라 샘플을 복제해 최소 학습 조건을 맞췄습니다.")

            sample_count = len(df)
            test_size = max(1, int(round(sample_count * 0.2)))
            if sample_count - test_size < 1:
                test_size = sample_count - 1
            train_df, val_df = train_test_split(df, test_size=test_size, random_state=seed)
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

            best_val_rmse = float("inf")
            best_out_of_range_ratio = float("inf")
            best_epoch = 0
            best_state_dict: dict[str, Any] | None = None
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
                is_better = (
                    val_rmse < best_val_rmse
                    or (val_rmse == best_val_rmse and out_of_range_ratio < best_out_of_range_ratio)
                )
                if is_better:
                    best_val_rmse = val_rmse
                    best_out_of_range_ratio = out_of_range_ratio
                    best_epoch = epoch
                    # Store the best checkpoint to avoid quality regressions in later epochs.
                    best_state_dict = deepcopy(model.state_dict())

                run.log(
                    {
                        "epoch": epoch,
                        "train_loss": train_loss,
                        "val_rmse": val_rmse,
                        "val_out_of_range_ratio": out_of_range_ratio,
                    }
                )

            model_path = str(Path(tmpdir) / "rating_model.pt")
            if best_state_dict is None:
                raise RuntimeError("학습 중 유효한 best checkpoint를 생성하지 못했습니다.")
            checkpoint = {
                "model_state_dict": best_state_dict,
                "feature_cols": feature_cols,
                "target_col": target_col,
                "hidden_dims": list(hidden_dims),
                "dropout": dropout,
                "scaler_mean": scaler.mean_.tolist(),
                "scaler_scale": scaler.scale_.tolist(),
                "scaler_var": scaler.var_.tolist(),
                "best_epoch": best_epoch,
                "best_val_rmse": best_val_rmse,
                "best_val_out_of_range_ratio": best_out_of_range_ratio,
            }
            torch.save(checkpoint, model_path)

            model_key = f"models/{run.id}/rating_model.pt"
            model_uri = upload_file(model_path, settings.aws_s3_model_bucket, model_key)
            run.summary["model_uri"] = model_uri
            run.summary["train_rows"] = len(train_df)
            run.summary["val_rows"] = len(val_df)
            run.summary["best_epoch"] = best_epoch
            run.summary["final_val_rmse"] = best_val_rmse
            run.summary["final_val_out_of_range_ratio"] = best_out_of_range_ratio

            artifact = wandb.Artifact(name=f"rating-model-{run.id}", type="model")
            artifact.add_file(model_path)
            run.log_artifact(artifact)

        delete_message(settings.train_queue_url, payload["_receipt_handle"])
        run.summary["status"] = "success"
        success = True
    except Exception as exc:
        run.summary["status"] = "failed"
        run.summary["error"] = str(exc)
        raise
    finally:
        if not success:
            run.summary["message_deleted"] = False
        run.finish()


if __name__ == "__main__":
    main()
