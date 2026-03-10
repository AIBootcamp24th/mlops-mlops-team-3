from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler

from src.config import INFERENCE_RESULT_PATH, MODEL_PATH, RAW_DATA_PATH
from src.train.model import RatingRegressor


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "release_date" in df.columns:
        df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")
        df["release_year"] = df["release_date"].dt.year.fillna(0).astype(int)
        df["release_month"] = df["release_date"].dt.month.fillna(0).astype(int)
    else:
        df["release_year"] = 0
        df["release_month"] = 0

    for col in ["popularity", "runtime", "budget", "vote_count"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["log_popularity"] = np.log1p(df["popularity"])
    df["log_budget"] = np.log1p(df["budget"])
    df["log_vote_count"] = np.log1p(df["vote_count"])

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


def build_scaler_from_checkpoint(
    checkpoint: dict,
    feature_count: int,
) -> StandardScaler:
    scaler = StandardScaler()

    mean = np.array(checkpoint.get("scaler_mean", [0.0] * feature_count), dtype=float)
    scale = np.array(checkpoint.get("scaler_scale", [1.0] * feature_count), dtype=float)
    var = np.array(checkpoint.get("scaler_var", [1.0] * feature_count), dtype=float)

    scaler.mean_ = mean
    scaler.scale_ = np.where(scale == 0.0, 1.0, scale)
    scaler.var_ = np.where(var < 1e-12, 1.0, var)
    scaler.n_features_in_ = feature_count

    return scaler


def load_model_and_metadata(model_path: Path):
    checkpoint = torch.load(model_path, map_location="cpu")

    if checkpoint is None:
        raise ValueError(f"- 모델 파일이 비어 있습니다: {model_path}")

    if not isinstance(checkpoint, dict):
        raise ValueError(f"- 체크포인트 형식이 올바르지 않습니다: {type(checkpoint)}")

    if "model_state_dict" not in checkpoint:
        raise ValueError("- checkpoint에 model_state_dict가 없습니다.")

    feature_cols = checkpoint.get("feature_cols")
    if not feature_cols:
        raise ValueError("- checkpoint에 feature_cols가 없습니다.")

    hidden_dims = tuple(checkpoint.get("hidden_dims", [128, 64]))
    dropout = float(checkpoint.get("dropout", 0.2))

    model = RatingRegressor(
        input_dim=len(feature_cols),
        hidden_dims=hidden_dims,
        dropout=dropout,
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    scaler = build_scaler_from_checkpoint(checkpoint, len(feature_cols))

    return model, scaler, feature_cols, checkpoint


def main() -> None:
    raw_path = Path(RAW_DATA_PATH)
    model_path = Path(MODEL_PATH)
    save_path = Path(INFERENCE_RESULT_PATH)

    if not raw_path.exists():
        raise FileNotFoundError(f"- 원본 데이터 파일이 없습니다: {raw_path}")

    if not model_path.exists():
        raise FileNotFoundError(f"- 모델 파일이 없습니다: {model_path}")

    df = pd.read_csv(raw_path)
    print(f"- 원본 데이터 로드 완료: {len(df)}건")

    if "original_language" in df.columns:
        df = df[df["original_language"] == "ko"].copy()
        print(f"- 한국 영화 필터링 완료: {len(df)}건")

    if "vote_count" in df.columns:
        df["vote_count"] = pd.to_numeric(df["vote_count"], errors="coerce").fillna(0)

    if "vote_average" in df.columns:
        df["vote_average"] = pd.to_numeric(df["vote_average"], errors="coerce").fillna(0)

    if "vote_count" in df.columns and "vote_average" in df.columns:
        df = df[(df["vote_count"] >= 10) & (df["vote_average"] > 0)].copy()
        print(f"- 평가용 필터 적용 완료: {len(df)}건")

    df = add_features(df)

    model, scaler, feature_cols, checkpoint = load_model_and_metadata(model_path)

    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0

    X = df[feature_cols].copy().fillna(0)
    X_scaled = scaler.transform(X)
    X_tensor = torch.tensor(X_scaled, dtype=torch.float32)

    with torch.no_grad():
        preds = model(X_tensor).view(-1).cpu().numpy()

    preds = np.clip(preds, 0, 10)
    df["predicted_rating"] = preds

    if "vote_average" in df.columns:
        df["abs_error"] = (df["vote_average"] - df["predicted_rating"]).abs()

    save_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(save_path, index=False)
    print(f"- 추론 완료: {save_path}")

    print(f"- 사용 피처 수: {len(feature_cols)}")
    print(f"- checkpoint best_epoch: {checkpoint.get('best_epoch')}")
    print(f"- checkpoint best_val_rmse: {checkpoint.get('best_val_rmse')}")

    show_cols = ["title", "release_date", "vote_average", "predicted_rating", "abs_error"]
    show_cols = [col for col in show_cols if col in df.columns]

    if "abs_error" in df.columns:
        print("\n- abs_error 가장 작은 10건")
        print(df[show_cols].sort_values("abs_error").head(10))

        print("\n- abs_error 가장 큰 10건")
        print(df[show_cols].sort_values("abs_error", ascending=False).head(10))

        print("\n- abs_error 요약")
        print(df["abs_error"].describe())
    else:
        print(df[show_cols].head(10))


if __name__ == "__main__":
    main()
