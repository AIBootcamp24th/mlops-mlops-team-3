from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator


def validate_runtime_env() -> None:
    import os

    required_vars = [
        "AWS_REGION",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "TRAIN_QUEUE_URL",
    ]
    missing = [name for name in required_vars if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"필수 환경변수가 누락되었습니다: {missing}")


with DAG(
    dag_id="mlops_train_pipeline",
    start_date=datetime(2026, 3, 1),
    schedule="0 2 * * *",
    catchup=False,
    tags=["mlops", "train", "sqs", "wandb"],
) as dag:
    env_check = PythonOperator(
        task_id="validate_env",
        python_callable=validate_runtime_env,
    )

    dispatch_train = BashOperator(
        task_id="dispatch_train_message",
        append_env=True,
        env={"PYTHONPATH": "/opt/airflow/project"},
        bash_command=(
            "cd /opt/airflow/project && "
            "python scripts/send_sqs_message.py"
        ),
    )

    quality_gate = BashOperator(
        task_id="quality_gate_candidate",
        append_env=True,
        env={
            "PYTHONPATH": "/opt/airflow/project",
            "QUALITY_GATE_REQUIRED": "false",
        },
        bash_command=(
            "cd /opt/airflow/project && "
            "python scripts/register_model.py"
        ),
    )

    env_check >> dispatch_train >> quality_gate
