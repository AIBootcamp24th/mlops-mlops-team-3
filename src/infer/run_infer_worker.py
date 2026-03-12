from __future__ import annotations

import json
import time
from typing import Any

from src.config import settings
from src.data.sqs_client import delete_message, receive_message
from src.infer.run_batch_infer import run_batch_inference


def _load_payload() -> dict[str, Any] | None:
    message = receive_message(settings.infer_queue_url)
    if not message:
        return None
    payload = json.loads(message["Body"])
    payload["_receipt_handle"] = message["ReceiptHandle"]
    return payload


def main() -> None:
    poll_seconds = 10
    while True:
        payload = _load_payload()
        if payload is None:
            print(f"추론 큐 메시지가 없습니다. {poll_seconds}초 후 재시도합니다.")
            time.sleep(poll_seconds)
            continue

        try:
            output_uri = run_batch_inference(
                model_s3_key=payload["model_s3_key"],
                input_s3_key=payload["input_s3_key"],
                output_s3_key=payload["output_s3_key"],
                feature_cols=payload["feature_cols"],
                approved_run_id=payload.get("approved_run_id"),
            )
            print(f"Batch inference output uploaded: {output_uri}")
            delete_message(settings.infer_queue_url, payload["_receipt_handle"])
        except Exception:
            # 실패 시 메시지를 삭제하지 않아 SQS 재처리 정책을 따릅니다.
            raise


if __name__ == "__main__":
    main()
