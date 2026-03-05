from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.datasets import Dataset
from airflow.operators.python import PythonOperator

DATASET_DOCS_URL = "https://github.com/AIBootcamp24th/mlops-mlops-team-3/tree/main/mlops_project/docs"
TRAIN_DISPATCH_DATASET = Dataset(
    "s3://team-prj-group3/mlops/datasets/train-dispatch",
    extra={
        "description": "학습 디스패치 메시지 생성 결과 데이터셋",
        "owner": "mlops-team3",
        "docs_url": DATASET_DOCS_URL,
    },
)
INFER_DISPATCH_DATASET = Dataset(
    "s3://team-prj-group3/mlops/datasets/infer-dispatch",
    extra={
        "description": "배치 추론 디스패치 메시지 생성 결과 데이터셋",
        "owner": "mlops-team3",
        "docs_url": DATASET_DOCS_URL,
    },
)


def log_dataset_event() -> None:
    print("Dataset event detected: train/infer dispatch updated.")


with DAG(
    dag_id="mlops_datasets_observer",
    default_args={"owner": "mlops-team3"},
    start_date=datetime(2026, 2, 27),
    schedule=[TRAIN_DISPATCH_DATASET, INFER_DISPATCH_DATASET],
    catchup=False,
    tags=["mlops", "datasets", "observer"],
) as dag:
    PythonOperator(
        task_id="log_dataset_event",
        python_callable=log_dataset_event,
    )
