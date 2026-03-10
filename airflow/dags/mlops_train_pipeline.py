from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.datasets import Dataset
from airflow.operators.bash import BashOperator
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

    # AWS 자격 증명은 정적 키 대신 IAM Role(Instance Profile)도 허용한다.
    try:
        boto3.client("sts", region_name=os.getenv("AWS_REGION")).get_caller_identity()
    except Exception as exc:  # pragma: no cover - 환경 검증 로직
        raise RuntimeError(
            "AWS 자격 증명을 확인할 수 없습니다. "
            "AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY 또는 EC2 IAM Role을 확인하세요."
        ) from exc


with DAG(
    dag_id="mlops_train_pipeline",
    default_args={"owner": "mlops-team3"},
    start_date=datetime(2026, 2, 27),
    end_date=datetime(2026, 3, 15, 23, 59, 59),
    schedule="0 2 * * *",
    catchup=False,
    tags=["mlops", "train", "sqs", "wandb"],
) as dag:
    # latest 고정 키 대신 Airflow 실행 시점 기반 키를 사용한다.
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
            "TRAIN_DATA_S3_KEY": train_data_s3_key,
        },
        bash_command=(
            "cd /opt/airflow/project && "
            "python scripts/sync_tmdb_to_db.py"
        ),
    )

    dispatch_train = BashOperator(
        task_id="dispatch_train_message",
        append_env=True,
        env={
            "PYTHONPATH": "/opt/airflow/project",
            "TRAIN_DATA_S3_KEY": train_data_s3_key,
        },
        outlets=[TRAIN_DISPATCH_DATASET],
        bash_command=(
            "cd /opt/airflow/project && "
            "python scripts/send_sqs_message.py"
        ),
    )

    run_train_once = BashOperator(
        task_id="run_train_worker_once",
        append_env=True,
        env={"PYTHONPATH": "/opt/airflow/project"},
        bash_command=(
            "cd /opt/airflow/project && "
            "python -m src.train.run_train"
        ),
    )

    quality_gate = BashOperator(
        task_id="quality_gate_candidate",
        append_env=True,
        env={
            "PYTHONPATH": "/opt/airflow/project",
            "QUALITY_GATE_REQUIRED": "false",
            "QUALITY_GATE_MAX_RUNS": "50",
        },
        bash_command=(
            "cd /opt/airflow/project && "
            "python scripts/register_model.py"
        ),
    )

    env_check >> sync_tmdb_to_db >> dispatch_train >> run_train_once >> quality_gate
