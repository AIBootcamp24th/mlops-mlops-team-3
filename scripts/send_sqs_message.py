from __future__ import annotations

from src.constants import FEATURE_COLS, TARGET_COL
from src.config import settings
from src.data.sqs_client import send_message


def main() -> None:
    payload = {
        "s3_key": "tmdb/latest/train.csv",
        "target_col": TARGET_COL,
        "feature_cols": FEATURE_COLS,
        "epochs": 10,
        "batch_size": 64,
        "learning_rate": 0.001,
    }
    message_id = send_message(settings.train_queue_url, payload)
    print(f"SQS message sent: {message_id}")


if __name__ == "__main__":
    main()
