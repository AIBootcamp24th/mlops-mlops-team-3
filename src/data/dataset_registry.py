"""
RDS/Aurora tmdb_dataset_registry 테이블에 CSV 메타데이터를 upsert합니다.

export_db_to_s3, export_infer_to_s3, 배치 추론 완료 시 호출됩니다.
"""
from __future__ import annotations

from sqlalchemy import text

from src.data.database import SessionLocal

CSV_TYPE_TRAIN = "train"
CSV_TYPE_INFER = "infer"
CSV_TYPE_PREDICTIONS = "predictions"


def upsert_dataset_registry(
    approved_run_id: str,
    csv_type: str,
    s3_key: str,
    row_count: int | None = None,
    dag_id: str | None = None,
    dag_run_id: str | None = None,
) -> None:
    """
    tmdb_dataset_registry에 레코드를 upsert합니다.
    s3_key 기준으로 중복 시 row_count, dag_id, dag_run_id, created_at을 갱신합니다.
    """
    db = SessionLocal()
    try:
        query = text("""
            INSERT INTO tmdb_dataset_registry
                (approved_run_id, csv_type, s3_key, row_count, dag_id, dag_run_id)
            VALUES
                (:approved_run_id, :csv_type, :s3_key, :row_count, :dag_id, :dag_run_id)
            ON DUPLICATE KEY UPDATE
                row_count = COALESCE(VALUES(row_count), row_count),
                dag_id = COALESCE(VALUES(dag_id), dag_id),
                dag_run_id = COALESCE(VALUES(dag_run_id), dag_run_id)
        """)
        db.execute(
            query,
            {
                "approved_run_id": approved_run_id,
                "csv_type": csv_type,
                "s3_key": s3_key,
                "row_count": row_count,
                "dag_id": dag_id,
                "dag_run_id": dag_run_id,
            },
        )
        db.commit()
    finally:
        db.close()
