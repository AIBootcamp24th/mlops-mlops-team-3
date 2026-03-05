from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.datasets import Dataset
from airflow.operators.python import PythonOperator

TRAIN_DISPATCH_DATASET = Dataset("s3://team-prj-group3/mlops/datasets/train-dispatch")
INFER_DISPATCH_DATASET = Dataset("s3://team-prj-group3/mlops/datasets/infer-dispatch")


def log_dataset_event() -> None:
    print("Dataset event detected: train/infer dispatch updated.")


with DAG(
    dag_id="mlops_datasets_observer",
    start_date=datetime(2026, 2, 27),
    schedule=[TRAIN_DISPATCH_DATASET, INFER_DISPATCH_DATASET],
    catchup=False,
    tags=["mlops", "datasets", "observer"],
) as dag:
    PythonOperator(
        task_id="log_dataset_event",
        python_callable=log_dataset_event,
    )
