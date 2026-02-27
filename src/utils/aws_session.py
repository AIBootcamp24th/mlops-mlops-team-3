import boto3

from src.config import settings


def get_boto3_session() -> boto3.session.Session:
    return boto3.session.Session(
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
        region_name=settings.aws_region,
    )
