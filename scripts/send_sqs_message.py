from __future__ import annotations

from src.config import settings
from src.data.sqs_client import send_message


def main() -> None:
    payload = {
        "s3_key": "tmdb/latest/train.csv",
        "target_col": "rating",
        "feature_cols": ["budget", "runtime", "popularity", "vote_count"],
        "epochs": 10,
        "batch_size": 64,
        "learning_rate": 0.001,
    }
    message_id = send_message(settings.train_queue_url, payload)
    print(f"SQS message sent: {message_id}")


if __name__ == "__main__":
    main()
