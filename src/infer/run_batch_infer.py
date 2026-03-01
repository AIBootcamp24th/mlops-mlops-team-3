from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import UTC, datetime

import pandas as pd
import torch

from src.config import settings
from src.data.s3_io import download_file, upload_file
from src.train.model import RatingRegressor

logger = logging.getLogger(__name__)


def _parse_feature_cols(feature_cols: str) -> list[str]:
    cols = [col.strip() for col in feature_cols.split(",") if col.strip()]
    if not cols:
        raise ValueError("feature_cols는 최소 1개 이상 필요합니다.")
    return cols


def _validate_feature_columns(df: pd.DataFrame, feature_cols: list[str]) -> None:
    missing_cols = [col for col in feature_cols if col not in df.columns]
    if missing_cols:
        missing_joined = ", ".join(missing_cols)
        raise ValueError(f"입력 CSV에 필요한 feature 컬럼이 없습니다: {missing_joined}")


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
        _validate_feature_columns(df, feature_cols)
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


def main() -> None:
    parser = argparse.ArgumentParser(description="S3 기반 배치 평점 추론을 실행합니다.")
    parser.add_argument("--model-s3-key", required=True, help="모델 버킷 내 모델 키")
    parser.add_argument("--input-s3-key", required=True, help="원천 버킷 내 입력 CSV 키")
    parser.add_argument("--output-s3-key", required=True, help="예측 버킷 내 출력 CSV 키")
    parser.add_argument(
        "--feature-cols",
        default="budget,runtime,popularity,vote_count",
        help="쉼표(,)로 구분된 feature 컬럼 목록",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    feature_cols = _parse_feature_cols(args.feature_cols)
    logger.info("배치 추론 시작: model=%s input=%s", args.model_s3_key, args.input_s3_key)

    output_uri = run_batch_inference(
        model_s3_key=args.model_s3_key,
        input_s3_key=args.input_s3_key,
        output_s3_key=args.output_s3_key,
        feature_cols=feature_cols,
    )

    result = {
        "model_s3_key": args.model_s3_key,
        "input_s3_key": args.input_s3_key,
        "output_s3_key": args.output_s3_key,
        "output_uri": output_uri,
        "feature_cols": feature_cols,
        "executed_at": datetime.now(UTC).isoformat(),
    }
    print(json.dumps(result, ensure_ascii=False))
    logger.info("배치 추론 완료: output=%s", output_uri)


if __name__ == "__main__":
    main()
