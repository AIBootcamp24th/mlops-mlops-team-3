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
        "INFER_QUEUE_URL",
    ]
    missing = [name for name in required_vars if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"필수 환경변수가 누락되었습니다: {missing}")


with DAG(
    dag_id="mlops_infer_pipeline",
    start_date=datetime(2026, 3, 1),
    schedule="30 2 * * *",
    catchup=False,
    tags=["mlops", "infer", "sqs", "batch"],
) as dag:
    env_check = PythonOperator(
        task_id="validate_env",
        python_callable=validate_runtime_env,
    )

    dispatch_infer = BashOperator(
        task_id="dispatch_infer_message",
        append_env=True,
        env={"PYTHONPATH": "/opt/airflow/project"},
        bash_command=(
            "cd /opt/airflow/project && "
            "python scripts/send_infer_sqs_message.py"
        ),
    )

    env_check >> dispatch_infer
