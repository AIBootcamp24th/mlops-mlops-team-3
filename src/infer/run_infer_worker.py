from __future__ import annotations

import json
from typing import Any

from src.config import settings
from src.data.sqs_client import delete_message, receive_message
from src.infer.run_batch_infer import run_batch_inference


def _load_payload() -> dict[str, Any]:
    message = receive_message(settings.infer_queue_url)
    if not message:
        raise RuntimeError("추론 큐 메시지가 없습니다.")
    payload = json.loads(message["Body"])
    payload["_receipt_handle"] = message["ReceiptHandle"]
    return payload


def main() -> None:
    payload = _load_payload()
    try:
        output_uri = run_batch_inference(
            model_s3_key=payload["model_s3_key"],
            input_s3_key=payload["input_s3_key"],
            output_s3_key=payload["output_s3_key"],
            feature_cols=payload["feature_cols"],
        )
        print(f"Batch inference output uploaded: {output_uri}")
        delete_message(settings.infer_queue_url, payload["_receipt_handle"])
    except Exception:
        # 실패 시 메시지를 삭제하지 않아 SQS 재처리 정책을 따릅니다.
        raise


if __name__ == "__main__":
    main()
