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


def copy_object(
    source_bucket: str,
    source_key: str,
    dest_bucket: str,
    dest_key: str,
) -> str:
    """S3 객체를 다른 키로 복사. 동일 버킷 내 복사도 지원."""
    s3 = get_boto3_session().client("s3")
    copy_source = {"Bucket": source_bucket, "Key": source_key}
    s3.copy_object(
        CopySource=copy_source,
        Bucket=dest_bucket,
        Key=dest_key,
    )
    return f"s3://{dest_bucket}/{dest_key}"
