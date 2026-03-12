from __future__ import annotations

import os
from datetime import datetime

from src.config import settings
from src.constants import FEATURE_COLS
from src.data.sqs_client import send_message
from src.utils.champion_registry import (
    champion_infer_key,
    champion_predictions_key,
    resolve_champion_model_key,
    resolve_approved_run_id,
)


def main() -> None:
    model_s3_key = resolve_champion_model_key()
    approved_run_id = resolve_approved_run_id()
    if not approved_run_id:
        raise RuntimeError(
            "champion registry에 approved_run_id가 없습니다. "
            "품질 게이트를 통과한 학습이 먼저 완료되어야 합니다."
        )

    output_s3_key = os.getenv("OUTPUT_S3_KEY")
    if not output_s3_key:
        ds = os.getenv("DATASET_DATE", datetime.utcnow().strftime("%Y%m%d"))
        ts = os.getenv("EXECUTION_TS", datetime.utcnow().strftime("%H%M%S"))
        output_s3_key = champion_predictions_key(approved_run_id, ds=ds, ts=ts)
    input_s3_key = champion_infer_key(approved_run_id)

    payload = {
        "model_s3_key": model_s3_key,
        "input_s3_key": input_s3_key,
        "output_s3_key": output_s3_key,
        "feature_cols": FEATURE_COLS,
        "approved_run_id": approved_run_id,
    }
    message_id = send_message(settings.infer_queue_url, payload)
    print(f"SQS infer message sent: {message_id}")
    print(f"OUTPUT_S3_KEY={output_s3_key}")


if __name__ == "__main__":
    main()
