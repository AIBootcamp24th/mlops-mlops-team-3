from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.datasets import Dataset
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

DATASET_DOCS_URL = "https://github.com/AIBootcamp24th/mlops-mlops-team-3/tree/main/mlops_project/docs"
INFER_DISPATCH_DATASET = Dataset(
    "s3://team-prj-group3/mlops/datasets/infer-dispatch",
    extra={
        "description": "배치 추론 디스패치 메시지 생성 결과 데이터셋",
        "owner": "mlops-team3",
        "docs_url": DATASET_DOCS_URL,
    },
)


def validate_runtime_env() -> None:
    import os
    import boto3

    required_vars = [
        "AWS_REGION",
        "INFER_QUEUE_URL",
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
    dag_id="mlops_infer_pipeline",
    default_args={"owner": "mlops-team3"},
    start_date=datetime(2026, 2, 27),
    end_date=datetime(2026, 3, 15, 23, 59, 59),
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
        outlets=[INFER_DISPATCH_DATASET],
        bash_command=(
            "cd /opt/airflow/project && "
            "python scripts/send_infer_sqs_message.py"
        ),
    )

    env_check >> dispatch_infer
