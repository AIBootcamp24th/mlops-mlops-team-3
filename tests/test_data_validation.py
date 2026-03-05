import pandas as pd
import pytest

from src.data.validation import validate_inference_frame, validate_training_frame


def test_validate_training_frame_success() -> None:
    df = pd.DataFrame(
        {
            "budget": [1.0, 2.0],
            "runtime": [90.0, 100.0],
            "popularity": [10.0, 20.0],
            "vote_count": [50.0, 100.0],
            "vote_average": [7.1, 8.0],
        }
    )
    validate_training_frame(df, ["budget", "runtime", "popularity", "vote_count"], "vote_average")


def test_validate_training_frame_raises_for_negative_feature() -> None:
    df = pd.DataFrame(
        {
            "budget": [-1.0],
            "runtime": [90.0],
            "popularity": [10.0],
            "vote_count": [50.0],
            "vote_average": [7.0],
        }
    )
    with pytest.raises(ValueError, match="음수 값이 허용되지 않는 컬럼"):
        validate_training_frame(df, ["budget", "runtime", "popularity", "vote_count"], "vote_average")


def test_validate_inference_frame_raises_for_missing_column() -> None:
    df = pd.DataFrame(
        {
            "budget": [1.0],
            "runtime": [90.0],
            "popularity": [10.0],
        }
    )
    with pytest.raises(ValueError, match="필수 컬럼이 누락"):
        validate_inference_frame(df, ["budget", "runtime", "popularity", "vote_count"])
