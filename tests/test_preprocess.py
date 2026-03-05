import pandas as pd
import pytest

from src.data.preprocess import filter_korean_movies


def test_filter_korean_movies() -> None:
    df = pd.DataFrame(
        [
            {"title": "A", "original_language": "ko"},
            {"title": "B", "original_language": "en"},
            {"title": "C", "original_language": "ko"},
        ]
    )

    filtered = filter_korean_movies(df, require_language_col=True)
    assert len(filtered) == 2
    assert set(filtered["title"].tolist()) == {"A", "C"}


def test_filter_korean_movies_require_column_raises() -> None:
    df = pd.DataFrame([{"title": "A"}])
    with pytest.raises(ValueError):
        filter_korean_movies(df, require_language_col=True)
