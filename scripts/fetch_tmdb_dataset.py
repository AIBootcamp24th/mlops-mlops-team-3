from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from src.config import settings
from src.constants import FEATURE_COLS, TARGET_COL
from src.data.crawler import TMDBCollector
from src.data.s3_io import upload_file


def _required_columns() -> list[str]:
    return FEATURE_COLS + [TARGET_COL, "original_language"]


def _apply_column_defaults(df):
    defaults = {"budget": 0.0, "runtime": 0.0}
    out = df.copy()
    for col, value in defaults.items():
        if col not in out.columns:
            out[col] = value
    return out


def main() -> None:
    max_pages = int(os.getenv("TMDB_MAX_PAGES", "5"))
    train_key = os.getenv("AIRFLOW_TRAIN_S3_KEY", "tmdb/latest/train.csv")
    infer_key = os.getenv("AIRFLOW_INFER_S3_KEY", "tmdb/latest/infer.csv")

    collector = TMDBCollector(settings.tmdb_api_key)
    df = collector.fetch_tmdb_data(max_pages=max_pages, korean_only=False)
    if df.empty:
        raise RuntimeError("TMDB 데이터 수집 결과가 비어 있습니다.")

    df = _apply_column_defaults(df)
    required_cols = _required_columns()
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise RuntimeError(f"수집 데이터 필수 컬럼 누락: {missing_cols}")

    # 한국 영화 우선 사용, 없으면 전체 데이터로 폴백하여 파이프라인 중단을 방지합니다.
    ko_df = df[df["original_language"] == "ko"].copy()
    if ko_df.empty:
        print("경고: original_language='ko' 데이터가 없어 전체 수집본으로 폴백합니다.")
        selected_df = df
    else:
        selected_df = ko_df

    # 학습/추론 공용 raw 데이터셋으로 동일 소스를 사용합니다.
    final_df = selected_df[required_cols].dropna().copy()
    if final_df.empty:
        raise RuntimeError("dropna 이후 유효한 데이터가 없습니다.")

    with TemporaryDirectory() as tmpdir:
        local_csv = Path(tmpdir) / "tmdb_latest.csv"
        final_df.to_csv(local_csv, index=False)
        train_uri = upload_file(str(local_csv), settings.aws_s3_raw_bucket, train_key)
        infer_uri = upload_file(str(local_csv), settings.aws_s3_raw_bucket, infer_key)

    print(
        "TMDB dataset 업로드 완료: "
        f"rows={len(final_df)}, train={train_uri}, infer={infer_uri}, max_pages={max_pages}"
    )


if __name__ == "__main__":
    main()
