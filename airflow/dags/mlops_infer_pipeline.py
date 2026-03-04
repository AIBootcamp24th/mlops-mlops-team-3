from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from urllib.error import URLError
from urllib.request import Request, urlopen

import boto3
from airflow import DAG
from airflow.datasets import Dataset
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator

INFER_S3_KEY = os.getenv("AIRFLOW_INFER_S3_KEY", "tmdb/latest/infer.csv")


def _env_or_default(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value


INFER_DATASET_URI = _env_or_default(
    "AIRFLOW_INFER_DATASET_URI",
    f"s3://{_env_or_default('AWS_S3_RAW_BUCKET', 'mlops-raw-bucket')}/{INFER_S3_KEY}",
)


def _notify_slack(message: str) -> None:
    webhook_url = os.getenv("AIRFLOW_SLACK_WEBHOOK_URL", "").strip()
    if not webhook_url:
        print(f"[SlackSkip] {message}")
        return

    payload = json.dumps({"text": message}).encode("utf-8")
    request = Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:  # nosec B310
            if response.status >= 400:
                raise RuntimeError(f"Slack webhook 호출 실패: status={response.status}")
    except URLError as exc:
        raise RuntimeError(f"Slack webhook 호출 실패: {exc}") from exc


def _task_failure_callback(context: dict) -> None:
    ti = context.get("task_instance")
    dag_id = context.get("dag").dag_id if context.get("dag") else "unknown_dag"
    task_id = ti.task_id if ti else "unknown_task"
    run_id = context.get("run_id", "unknown_run")
    log_url = getattr(ti, "log_url", "")
    _notify_slack(
        f"[Airflow][Infer][FAILED] dag={dag_id}, task={task_id}, run_id={run_id}, log={log_url}"
    )


def validate_runtime_env() -> None:
    required_vars = [
        "AWS_REGION",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_S3_RAW_BUCKET",
        "INFER_QUEUE_URL",
    ]
    missing = [name for name in required_vars if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"필수 환경변수가 누락되었습니다: {missing}")


def choose_dispatch_or_skip() -> str:
    bucket = os.getenv("AWS_S3_RAW_BUCKET", "")
    region = os.getenv("AWS_REGION", "")
    if not bucket:
        return "skip_dispatch"

    s3 = boto3.client("s3", region_name=region or None)
    try:
        response = s3.head_object(Bucket=bucket, Key=INFER_S3_KEY)
        if int(response.get("ContentLength", 0)) <= 0:
            return "skip_dispatch"
    except Exception as exc:  # pragma: no cover - airflow runtime path
        print(f"[DataQuality] infer raw 데이터 확인 실패: {exc}")
        return "skip_dispatch"
    return "dispatch_infer_message"


def notify_skip() -> None:
    bucket = os.getenv("AWS_S3_RAW_BUCKET", "")
    _notify_slack(
        f"[Airflow][Infer][SKIP] 입력 데이터 검증 실패: s3://{bucket}/{INFER_S3_KEY}"
    )


default_args = {
    "owner": "mlops",
    "depends_on_past": False,
    "retries": int(os.getenv("AIRFLOW_TASK_RETRIES", "2")),
    "retry_delay": timedelta(minutes=int(os.getenv("AIRFLOW_TASK_RETRY_DELAY_MIN", "5"))),
    "execution_timeout": timedelta(minutes=int(os.getenv("AIRFLOW_TASK_TIMEOUT_MIN", "20"))),
    "on_failure_callback": _task_failure_callback,
}

with DAG(
    dag_id="mlops_infer_pipeline",
    start_date=datetime(2026, 2, 27),
    end_date=datetime(2026, 3, 11, 23, 59, 59),
    schedule=[Dataset(INFER_DATASET_URI)],
    catchup=False,
    default_args=default_args,
    tags=["mlops", "infer", "sqs", "batch", "dataset"],
) as dag:
    env_check = PythonOperator(
        task_id="validate_env",
        python_callable=validate_runtime_env,
    )

    branch_quality = BranchPythonOperator(
        task_id="branch_data_quality",
        python_callable=choose_dispatch_or_skip,
    )

    dispatch_infer = BashOperator(
        task_id="dispatch_infer_message",
        append_env=True,
        env={"PYTHONPATH": "/opt/airflow/project", "AIRFLOW_INFER_S3_KEY": INFER_S3_KEY},
        bash_command=(
            "cd /opt/airflow/project && "
            "python scripts/send_infer_sqs_message.py"
        ),
    )

    skip_dispatch = PythonOperator(
        task_id="skip_dispatch",
        python_callable=notify_skip,
    )
    end_node = EmptyOperator(task_id="end_node")

    env_check >> branch_quality
    branch_quality >> dispatch_infer >> end_node
    branch_quality >> skip_dispatch >> end_node
