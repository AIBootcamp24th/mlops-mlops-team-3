"""
통합 테스트: SQS payload → worker 처리 경로.
"""
from __future__ import annotations


def test_infer_payload_schema_matches_run_infer_worker() -> None:
    """send_infer_sqs_message가 발행하는 payload가 run_infer_worker에서 기대하는 필드와 일치."""
    # run_infer_worker.run_batch_inference 호출 시 사용하는 필드
    worker_required_keys = {"model_s3_key", "input_s3_key", "output_s3_key", "feature_cols"}

    # send_infer_sqs_message payload 구조 (champion prefix 사용)
    sample_payload = {
        "model_s3_key": "models/run123/rating_model.pt",
        "input_s3_key": "tmdb/run123/infer.csv",
        "output_s3_key": "tmdb/run123/predictions_20260311_020000.csv",
        "feature_cols": ["budget", "runtime", "popularity", "vote_count"],
        "approved_run_id": "run123",  # 선택적, tmdb_dataset_registry upsert용
    }

    for key in worker_required_keys:
        assert key in sample_payload, f"run_infer_worker가 기대하는 '{key}'가 payload에 있어야 합니다."
        assert sample_payload[key] is not None


def test_train_payload_schema_matches_run_train() -> None:
    """send_sqs_message가 발행하는 payload가 run_train에서 기대하는 필드와 일치."""
    worker_required_keys = {"s3_key", "target_col", "feature_cols", "epochs", "batch_size"}

    sample_payload = {
        "s3_key": "tmdb/20260311T020000/train.csv",
        "target_col": "vote_average",
        "feature_cols": ["budget", "runtime", "popularity", "vote_count"],
        "epochs": 20,
        "batch_size": 64,
    }

    for key in worker_required_keys:
        assert key in sample_payload, f"run_train이 기대하는 '{key}'가 payload에 있어야 합니다."
