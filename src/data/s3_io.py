from __future__ import annotations

from pathlib import Path

from src.utils.aws_session import get_boto3_session


def download_file(bucket: str, key: str, local_path: str) -> str:
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    s3 = get_boto3_session().client("s3")
    s3.download_file(bucket, key, local_path)
    return local_path


def upload_file(local_path: str, bucket: str, key: str) -> str:
    s3 = get_boto3_session().client("s3")
    s3.upload_file(local_path, bucket, key)
    return f"s3://{bucket}/{key}"
