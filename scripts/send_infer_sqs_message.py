from __future__ import annotations

from datetime import datetime

from src.config import settings
from src.constants import FEATURE_COLS
from src.data.sqs_client import send_message


def main() -> None:
    model_s3_key = settings.api_model_s3_key or "models/latest/rating_model.pt"
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    payload = {
        "model_s3_key": model_s3_key,
        "input_s3_key": "tmdb/latest/infer.csv",
        "output_s3_key": f"pred/batch/{timestamp}.csv",
        "feature_cols": FEATURE_COLS,
    }
    message_id = send_message(settings.infer_queue_url, payload)
    print(f"SQS infer message sent: {message_id}")


if __name__ == "__main__":
    main()
