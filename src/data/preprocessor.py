from pathlib import Path

import numpy as np
import pandas as pd

from src.config import PROCESSED_DATA_PATH, RAW_DATA_PATH


def load_raw_data() -> pd.DataFrame:
    df = pd.read_csv(RAW_DATA_PATH)
    print(f"- 원본 데이터 로드 완료: {len(df)}건")
    return df


def filter_data(df: pd.DataFrame) -> pd.DataFrame:
    if "vote_count" in df.columns:
        df["vote_count"] = pd.to_numeric(df["vote_count"], errors="coerce").fillna(0)

    if "vote_average" in df.columns:
        df["vote_average"] = pd.to_numeric(df["vote_average"], errors="coerce").fillna(0)

    df = df[df["vote_count"] >= 10].copy()
    df = df[df["vote_average"] > 0].copy()

    print(f"- 필터링 후 데이터 수: {len(df)}건")
    return df


def add_date_features(df: pd.DataFrame) -> pd.DataFrame:
    if "release_date" in df.columns:
        df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
        df["release_year"] = df["release_date"].dt.year.fillna(0).astype(int)
        df["release_month"] = df["release_date"].dt.month.fillna(0).astype(int)
    else:
        df["release_year"] = 0
        df["release_month"] = 0

    return df


def add_log_features(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["popularity", "runtime", "budget", "vote_count"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["log_popularity"] = np.log1p(df["popularity"])
    df["log_budget"] = np.log1p(df["budget"])
    df["log_vote_count"] = np.log1p(df["vote_count"])

    return df

def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    current_year = pd.Timestamp.now().year

    df["movie_age"] = current_year - df["release_year"]
    df["movie_age"] = df["movie_age"].clip(lower=0)

    runtime_safe = df["runtime"].replace(0, np.nan)
    vote_count_safe = df["vote_count"].replace(0, np.nan)

    df["budget_per_runtime"] = df["budget"] / runtime_safe
    df["budget_per_runtime"] = df["budget_per_runtime"].replace([np.inf, -np.inf], np.nan).fillna(0)
    df["log_budget_per_runtime"] = np.log1p(df["budget_per_runtime"])

    df["popularity_per_vote"] = df["popularity"] / vote_count_safe
    df["popularity_per_vote"] = (
        df["popularity_per_vote"].replace([np.inf, -np.inf], np.nan).fillna(0)
    )
    df["log_popularity_per_vote"] = np.log1p(df["popularity_per_vote"])

    return df


def add_adult_feature(df: pd.DataFrame) -> pd.DataFrame:
    if "adult" not in df.columns:
        df["adult"] = 0

    df["adult"] = (
        df["adult"]
        .astype(str)
        .str.lower()
        .map({"true": 1, "false": 0, "1": 1, "0": 0})
        .fillna(0)
        .astype(int)
    )
    return df


def add_genre_features(df: pd.DataFrame) -> pd.DataFrame:
    genre_cols = [col for col in df.columns if col.startswith("genre_")]
    valid_genre_cols = []

    for col in genre_cols:
        if col == "genre_count":
            continue

        numeric_col = pd.to_numeric(df[col], errors="coerce")
        non_null = numeric_col.dropna()
        unique_vals = set(non_null.unique())

        if len(non_null) > 0 and unique_vals.issubset({0, 1}):
            df[col] = numeric_col.fillna(0).astype(int)
            valid_genre_cols.append(col)

    if valid_genre_cols:
        df["genre_count"] = df[valid_genre_cols].sum(axis=1)
    else:
        df["genre_count"] = 0

    return df


def fill_missing_numeric(df: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = [
        "popularity",
        "runtime",
        "budget",
        "vote_count",
        "release_year",
        "release_month",
        "log_popularity",
        "log_budget",
        "log_vote_count",
        "movie_age",
        "budget_per_runtime",
        "log_budget_per_runtime",
        "popularity_per_vote",
        "log_popularity_per_vote",
        "adult",
        "genre_count",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


def save_processed_data(df: pd.DataFrame) -> None:
    Path(PROCESSED_DATA_PATH).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED_DATA_PATH, index=False)
    print(f"- 전처리 완료: {PROCESSED_DATA_PATH}")


def main():
    df = load_raw_data()
    df = filter_data(df)
    df = add_date_features(df)
    df = add_log_features(df)
    df = add_derived_features(df)
    df = add_adult_feature(df)
    df = add_genre_features(df)
    df = fill_missing_numeric(df)
    save_processed_data(df)


if __name__ == "__main__":
    main()
