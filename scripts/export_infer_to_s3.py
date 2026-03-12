"""
movies_raw를 S3 tmdb/{approved_run_id}/infer.csv로 내보냅니다.

champion registry에서 approved_run_id를 읽어 경로를 결정합니다.
추론 파이프라인에서 dispatch_infer_message 전에 실행됩니다.
"""
from __future__ import annotations

import os
from tempfile import TemporaryDirectory

import pandas as pd
from sqlalchemy import text

from src.config import settings
from src.data.database import SessionLocal
from src.data.dataset_registry import CSV_TYPE_INFER, upsert_dataset_registry
from src.data.s3_io import upload_file
from src.utils.champion_registry import champion_infer_key, resolve_approved_run_id


def _approved_run_id_from_s3_key(s3_key: str) -> str | None:
    """tmdb/{run_id}/infer.csv 형식에서 run_id 추출."""
    parts = s3_key.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "tmdb":
        return parts[1]
    return None


def export_infer_to_s3(s3_key: str | None = None) -> str:
    """movies_raw를 S3에 infer.csv로 업로드."""
    approved_run_id: str | None = None
    if s3_key is None:
        approved_run_id = resolve_approved_run_id()
        if not approved_run_id:
            raise RuntimeError(
                "champion registry에 approved_run_id가 없습니다. "
                "품질 게이트를 통과한 학습이 먼저 완료되어야 합니다."
            )
        s3_key = champion_infer_key(approved_run_id)
    else:
        approved_run_id = _approved_run_id_from_s3_key(s3_key)

    print("- DB 데이터(movies_raw) S3 infer.csv 내보내기 시작")
    db = SessionLocal()
    try:
        query = text("SELECT * FROM movies_raw")
        result = db.execute(query)
        df = pd.DataFrame(result.fetchall(), columns=result.keys())

        if df.empty:
            print("- 경고: DB에 데이터가 없습니다.")
            return ""

        print(f"- DB 데이터 로드 완료: {len(df)}건")

        with TemporaryDirectory() as tmpdir:
            local_csv = os.path.join(tmpdir, "infer.csv")
            df.to_csv(local_csv, index=False)
            s3_uri = upload_file(local_csv, settings.aws_s3_raw_bucket, s3_key)
            print(f"- S3 업로드 완료: {s3_uri}")

            if approved_run_id:
                try:
                    upsert_dataset_registry(
                        approved_run_id=approved_run_id,
                        csv_type=CSV_TYPE_INFER,
                        s3_key=s3_key,
                        row_count=len(df),
                        dag_id=os.getenv("AIRFLOW_CTX_DAG_ID"),
                        dag_run_id=os.getenv("AIRFLOW_CTX_DAG_RUN_ID"),
                    )
                except Exception:
                    pass
            return s3_uri

    except Exception as e:
        print(f"- 데이터 내보내기 실패: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    s3_custom_key = os.getenv("INFER_DATA_S3_KEY")
    export_infer_to_s3(s3_custom_key)
