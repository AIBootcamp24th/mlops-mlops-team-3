from __future__ import annotations

from typing import Any

import wandb

from src.constants import FEATURE_COLS, TARGET_COL
from src.config import settings
from src.data.sqs_client import send_message


def _project_name() -> str:
    if settings.wandb_entity:
        return f"{settings.wandb_entity}/{settings.wandb_project}"
    return settings.wandb_project


def _to_int_list(value: Any, default: list[int]) -> list[int]:
    if not isinstance(value, list):
        return default
    try:
        return [int(v) for v in value]
    except (TypeError, ValueError):
        return default


def _select_best_profile() -> dict[str, Any] | None:
    if not settings.wandb_api_key:
        return None

    api = wandb.Api()
    runs = api.runs(_project_name())

    best_metrics: tuple[float, float] | None = None
    best_profile: dict[str, Any] | None = None

    for run in runs:
        if run.state != "finished":
            continue
        if str(run.summary.get("status", "")) != "success":
            continue

        rmse = float(run.summary.get("final_val_rmse", float("inf")))
        out_of_range = float(run.summary.get("final_val_out_of_range_ratio", float("inf")))
        if rmse == float("inf") or out_of_range == float("inf"):
            continue

        metrics = (rmse, out_of_range)
        if best_metrics is not None and metrics >= best_metrics:
            continue

        best_metrics = metrics
        best_profile = {
            "tuning_profile": str(run.config.get("tuning_profile", "auto_best")),
            "learning_rate": float(run.config.get("learning_rate", 0.001)),
            "hidden_dims": _to_int_list(run.config.get("hidden_dims"), [128, 64]),
            "dropout": float(run.config.get("dropout", 0.2)),
            "epochs": int(run.config.get("epochs", 20)),
            "batch_size": int(run.config.get("batch_size", 64)),
            "seed": int(run.config.get("seed", settings.train_seed)),
        }

    return best_profile


def main() -> None:
    fallback_profile = {
        "tuning_profile": "baseline",
        "learning_rate": 0.001,
        "hidden_dims": [128, 64],
        "dropout": 0.2,
        "epochs": 20,
        "batch_size": 64,
        "seed": settings.train_seed,
    }
    selected_profile = fallback_profile
    try:
        best_profile = _select_best_profile()
        if best_profile is not None:
            selected_profile = best_profile
    except Exception as exc:
        print(f"경고: W&B best profile 조회 실패. baseline으로 진행합니다. ({exc})")

    payload = {
        "s3_key": "tmdb/latest/train.csv",
        "target_col": TARGET_COL,
        "feature_cols": FEATURE_COLS,
        **selected_profile,
    }

    message_id = send_message(settings.train_queue_url, payload)
    print(
        f"SQS message sent: {message_id} "
        f"(profile={payload['tuning_profile']}, lr={payload['learning_rate']}, "
        f"hidden_dims={payload['hidden_dims']}, dropout={payload['dropout']}, "
        f"epochs={payload['epochs']}, batch_size={payload['batch_size']})"
    )


if __name__ == "__main__":
    main()
