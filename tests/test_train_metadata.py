from src.train.run_train import build_training_metadata


def test_build_training_metadata_contains_required_fields() -> None:
    metadata = build_training_metadata(
        run_id="run-123",
        model_uri="s3://team-mlops/models/run-123/rating_model.pt",
        val_rmse=0.8123,
        feature_cols=["budget", "runtime", "popularity", "vote_count"],
        target_col="rating",
        train_s3_key="tmdb/latest/train.csv",
        epochs=10,
        batch_size=64,
        learning_rate=0.001,
    )

    assert metadata["run_id"] == "run-123"
    assert metadata["model_uri"].endswith("rating_model.pt")
    assert metadata["val_rmse"] == 0.8123
    assert metadata["feature_cols"] == ["budget", "runtime", "popularity", "vote_count"]
    assert metadata["target_col"] == "rating"
    assert metadata["train_s3_key"] == "tmdb/latest/train.csv"
    assert metadata["epochs"] == 10
    assert metadata["batch_size"] == 64
    assert metadata["learning_rate"] == 0.001
    assert "created_at" in metadata
