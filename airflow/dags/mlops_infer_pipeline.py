"""
배치 추론 파이프라인: SQS dispatch → 별도 워커가 큐 소비 → 결과 검증.
"""
from __future__ import annotations

import os
import time
from datetime import datetime

from airflow import DAG
from airflow.datasets import Dataset
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


def verify_infer_result(output_s3_key: str, bucket: str, timeout_sec: int = 300, poll_interval: int = 15) -> None:
    """S3에 추론 결과 파일이 생성될 때까지 대기 후 검증."""
    import boto3
    from botocore.exceptions import ClientError

    s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION"))
    elapsed = 0
    while elapsed < timeout_sec:
        try:
            s3.head_object(Bucket=bucket, Key=output_s3_key)
            obj = s3.get_object(Bucket=bucket, Key=output_s3_key)
            body = obj["Body"].read().decode("utf-8")
            lines = [ln for ln in body.strip().split("\n") if ln]
            if len(lines) < 2:
                raise RuntimeError(f"추론 결과 파일이 비어있거나 헤더만 있습니다: {output_s3_key}")
            print(f"추론 결과 검증 완료: {output_s3_key}, {len(lines)-1}건")
            return
        except ClientError as e:
            if e.response["Error"]["Code"] != "404":
                raise
        elapsed += poll_interval
        time.sleep(poll_interval)
    raise RuntimeError(f"타임아웃: {timeout_sec}초 내에 추론 결과 파일을 찾을 수 없습니다: {output_s3_key}")


def _dispatch_infer_message(**context) -> str:
    """추론 메시지 발행 후 output_s3_key를 XCom에 반환."""
    import subprocess

    ds = context["ds_nodash"]
    ts = context["ts_nodash"]
    output_s3_key = f"pred/batch/{ds}_{ts}.csv"
    env = os.environ.copy()
    env["OUTPUT_S3_KEY"] = output_s3_key
    env["PYTHONPATH"] = "/opt/airflow/project"
    subprocess.run(
        ["python", "scripts/send_infer_sqs_message.py"],
        cwd="/opt/airflow/project",
        env=env,
        check=True,
    )
    return output_s3_key


def _verify_infer_result(**context) -> None:
    """XCom에서 output_s3_key를 받아 S3 결과 검증."""
    ti = context["ti"]
    output_s3_key = ti.xcom_pull(task_ids="dispatch_infer_message")
    bucket = os.getenv("AWS_S3_PRED_BUCKET", "")
    if not bucket:
        raise RuntimeError("AWS_S3_PRED_BUCKET이 설정되지 않았습니다.")
    verify_infer_result(output_s3_key, bucket)


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

    dispatch_infer = PythonOperator(
        task_id="dispatch_infer_message",
        python_callable=_dispatch_infer_message,
        outlets=[INFER_DISPATCH_DATASET],
    )

    verify_infer = PythonOperator(
        task_id="verify_infer_result",
        python_callable=_verify_infer_result,
    )

    env_check >> dispatch_infer >> verify_infer
