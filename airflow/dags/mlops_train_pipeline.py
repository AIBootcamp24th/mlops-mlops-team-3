from __future__ import annotations

import subprocess
from datetime import datetime

from airflow import DAG
from airflow.datasets import Dataset
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator, ShortCircuitOperator

DATASET_DOCS_URL = "https://github.com/AIBootcamp24th/mlops-mlops-team-3/tree/main/mlops_project/docs"
TRAIN_DISPATCH_DATASET = Dataset(
    "s3://team-prj-group3/mlops/datasets/train-dispatch",
    extra={
        "description": "학습 디스패치 메시지 생성 결과 데이터셋",
        "owner": "mlops-team3",
        "docs_url": DATASET_DOCS_URL,
    },
)


def validate_runtime_env() -> None:
    import os
    import boto3

    required_vars = [
        "AWS_REGION",
        "TRAIN_QUEUE_URL",
    ]
    missing = [name for name in required_vars if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"필수 환경변수가 누락되었습니다: {missing}")

    try:
        boto3.client("sts", region_name=os.getenv("AWS_REGION")).get_caller_identity()
    except Exception as exc:
        raise RuntimeError(
            "AWS 자격 증명을 확인할 수 없습니다. "
            "AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY 또는 EC2 IAM Role을 확인하세요."
        ) from exc


def check_for_data_changes() -> bool:
    """exit 0 means change detected, exit 1 means no change."""
    try:
        result = subprocess.run(
            ["python", "scripts/check_data_change.py"],
            cwd="/opt/airflow/project",
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        return result.returncode == 0
    except Exception as e:
        print(f"Error checking for data changes: {e}")
        return True  # Default to True on error to be safe


with DAG(
    dag_id="mlops_train_pipeline",
    default_args={"owner": "mlops-team3"},
    start_date=datetime(2026, 2, 27),
    end_date=datetime(2026, 3, 15, 23, 59, 59),
    schedule="0 2 * * *",
    catchup=False,
    tags=["mlops", "train", "sqs", "wandb"],
) as dag:
    train_data_s3_key = "tmdb/{{ ts_nodash }}/train.csv"

    env_check = PythonOperator(
        task_id="validate_env",
        python_callable=validate_runtime_env,
    )

    sync_tmdb_to_db = BashOperator(
        task_id="sync_tmdb_to_db",
        append_env=True,
        env={
            "PYTHONPATH": "/opt/airflow/project",
        },
        bash_command="cd /opt/airflow/project && python scripts/sync_tmdb_to_db.py",
    )

    check_data = ShortCircuitOperator(
        task_id="check_data_change",
        python_callable=check_for_data_changes,
    )

    validate_quality = BashOperator(
        task_id="validate_data_quality",
        append_env=True,
        env={
            "PYTHONPATH": "/opt/airflow/project",
        },
        bash_command="cd /opt/airflow/project && python scripts/validate_data_quality.py",
    )

    export_s3 = BashOperator(
        task_id="export_db_to_s3",
        append_env=True,
        env={
            "PYTHONPATH": "/opt/airflow/project",
            "TRAIN_DATA_S3_KEY": train_data_s3_key,
        },
        bash_command="cd /opt/airflow/project && python scripts/export_db_to_s3.py",
    )

    dispatch_train = BashOperator(
        task_id="dispatch_train_message",
        append_env=True,
        env={
            "PYTHONPATH": "/opt/airflow/project",
            "TRAIN_DATA_S3_KEY": train_data_s3_key,
        },
        outlets=[TRAIN_DISPATCH_DATASET],
        bash_command="cd /opt/airflow/project && python scripts/send_sqs_message.py",
    )

    run_train_once = BashOperator(
        task_id="run_train_worker_once",
        append_env=True,
        env={"PYTHONPATH": "/opt/airflow/project"},
        bash_command="cd /opt/airflow/project && python -m src.train.run_train",
    )

    quality_gate = BashOperator(
        task_id="quality_gate_candidate",
        append_env=True,
        env={
            "PYTHONPATH": "/opt/airflow/project",
            "QUALITY_GATE_REQUIRED": "false",
            "QUALITY_GATE_MAX_RUNS": "50",
        },
        bash_command="cd /opt/airflow/project && python scripts/register_model.py",
    )

    env_check >> sync_tmdb_to_db >> check_data >> validate_quality >> export_s3 >> dispatch_train >> run_train_once >> quality_gate
