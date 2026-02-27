from __future__ import annotations

import json
from typing import Any

from src.utils.aws_session import get_boto3_session


def send_message(queue_url: str, payload: dict[str, Any]) -> str:
    sqs = get_boto3_session().client("sqs")
    response = sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
    return response["MessageId"]


def receive_message(queue_url: str, wait_seconds: int = 10) -> dict[str, Any] | None:
    sqs = get_boto3_session().client("sqs")
    response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=wait_seconds,
    )
    messages = response.get("Messages", [])
    if not messages:
        return None
    return messages[0]


def delete_message(queue_url: str, receipt_handle: str) -> None:
    sqs = get_boto3_session().client("sqs")
    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
