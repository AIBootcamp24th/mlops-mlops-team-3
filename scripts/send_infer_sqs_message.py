from __future__ import annotations

import json
from datetime import datetime

from src.config import settings
from src.constants import FEATURE_COLS
from src.data.sqs_client import send_message
from src.utils.aws_session import get_boto3_session


def _resolve_champion_model_key() -> str:
    if settings.api_model_s3_key:
        return settings.api_model_s3_key
    if not settings.api_model_registry_key:
        raise RuntimeError("API_MODEL_REGISTRY_KEY가 비어 있습니다.")
    if not settings.aws_s3_model_bucket:
        raise RuntimeError("AWS_S3_MODEL_BUCKET이 비어 있습니다.")

    s3 = get_boto3_session().client("s3")
    obj = s3.get_object(Bucket=settings.aws_s3_model_bucket, Key=settings.api_model_registry_key)
    raw = obj["Body"].read().decode("utf-8")
    registry = json.loads(raw)
    model_key = str(registry.get("model_key", "")).strip()
    if not model_key:
        raise RuntimeError("champion registry에 model_key가 없습니다.")
    return model_key


def main() -> None:
    import os

    model_s3_key = _resolve_champion_model_key()
    output_s3_key = os.getenv("OUTPUT_S3_KEY")
    if not output_s3_key:
        output_s3_key = f"pred/batch/{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.csv"
    payload = {
        "model_s3_key": model_s3_key,
        "input_s3_key": "tmdb/latest/infer.csv",
        "output_s3_key": output_s3_key,
        "feature_cols": FEATURE_COLS,
    }
    message_id = send_message(settings.infer_queue_url, payload)
    print(f"SQS infer message sent: {message_id}")
    print(f"OUTPUT_S3_KEY={output_s3_key}")


if __name__ == "__main__":
    main()
