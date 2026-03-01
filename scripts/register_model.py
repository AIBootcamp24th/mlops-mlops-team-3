from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

import wandb

from src.config import settings


def _parse_s3_key(s3_uri: str) -> str:
    parsed = urlparse(s3_uri)
    if parsed.scheme != "s3" or not parsed.path:
        raise ValueError(f"유효한 S3 URI가 아닙니다: {s3_uri}")
    return parsed.path.lstrip("/")


def select_batch_model() -> dict[str, Any]:
    if settings.wandb_api_key:
        os.environ["WANDB_API_KEY"] = settings.wandb_api_key

    api = wandb.Api()
    project = f"{settings.wandb_entity}/{settings.wandb_project}" if settings.wandb_entity else settings.wandb_project
    runs = api.runs(project)
    if not runs:
        raise RuntimeError("W&B run 이 존재하지 않습니다.")

    best_candidate: dict[str, Any] | None = None
    for run in runs:
        if run.state != "finished":
            continue

        model_uri = str(run.summary.get("model_uri", "")).strip()
        if not model_uri:
            continue

        val_rmse = run.summary.get("val_rmse")
        try:
            metric = float(val_rmse)
        except (TypeError, ValueError):
            continue

        feature_cols_raw = run.summary.get("feature_cols", [])
        if not isinstance(feature_cols_raw, list) or not feature_cols_raw:
            feature_cols_raw = ["budget", "runtime", "popularity", "vote_count"]
        feature_cols = [str(col) for col in feature_cols_raw]

        candidate = {
            "run_id": run.id,
            "model_uri": model_uri,
            "model_s3_key": _parse_s3_key(model_uri),
            "val_rmse": metric,
            "feature_cols": feature_cols,
            "selected_by": "lowest_val_rmse",
        }
        if best_candidate is None or metric < best_candidate["val_rmse"]:
            best_candidate = candidate

    if best_candidate is None:
        raise RuntimeError("배치 추론에 사용할 finished run/model_uri/val_rmse 조합을 찾지 못했습니다.")
    return best_candidate


def main() -> None:
    parser = argparse.ArgumentParser(description="W&B run에서 배치 추론용 모델 후보를 선택합니다.")
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="선택 결과를 저장할 JSON 파일 경로",
    )
    args = parser.parse_args()

    selected = select_batch_model()
    json_payload = json.dumps(selected, ensure_ascii=False)

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(f"{json_payload}\n", encoding="utf-8")

    print(json_payload)


if __name__ == "__main__":
    main()
