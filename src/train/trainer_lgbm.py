"""
[EXPERIMENTAL] LightGBM 기반 평점 예측 학습.
운영 파이프라인은 PyTorch run_train을 사용합니다.
"""
from pathlib import Path

import joblib
import lightgbm as lgb
import pandas as pd
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split

from src.config import (
    MODEL_DIR,
    PROCESSED_DATA_PATH,
)

LGBM_MODEL_PATH = str(Path(MODEL_DIR) / "rating_lgbm.pkl")
LGBM_FEATURE_COLS_PATH = str(Path(MODEL_DIR) / "lgbm_feature_cols.pkl")


def get_feature_columns(df: pd.DataFrame):
    numeric_features = [
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

    genre_features = []
    for col in df.columns:
        if col.startswith("genre_") and col != "genre_count":
            numeric_col = pd.to_numeric(df[col], errors="coerce")
            non_null = numeric_col.dropna()
            unique_vals = set(non_null.unique())

            if len(non_null) > 0 and unique_vals.issubset({0, 1}):
                genre_features.append(col)

    feature_cols = numeric_features + genre_features

    feature_cols = list(dict.fromkeys(feature_cols))

    return feature_cols


def main():
    df = pd.read_csv(PROCESSED_DATA_PATH)
    print(f"- 학습 데이터 로드 완료: {len(df)}건")

    feature_cols = get_feature_columns(df)
    target_col = "vote_average"

    X = df[feature_cols].copy()
    y = pd.to_numeric(df[target_col], errors="coerce").fillna(0)

    X_train, X_val, y_train, y_val = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
    )

    model = lgb.LGBMRegressor(
        objective="regression",
        metric="mae",
        n_estimators=500,
        learning_rate=0.03,
        num_leaves=31,
        max_depth=-1,
        min_child_samples=20,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_alpha=0.0,
        reg_lambda=0.0,
        random_state=42,
        n_jobs=-1,
    )

    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        eval_metric="mae",
        callbacks=[
            lgb.early_stopping(stopping_rounds=50),
            lgb.log_evaluation(period=50),
        ],
    )

    val_preds = model.predict(X_val)
    val_preds = val_preds.clip(0, 10)

    mae = mean_absolute_error(y_val, val_preds)
    print(f"\n- Validation MAE: {mae:.6f}")

    importance_df = pd.DataFrame(
        {
            "feature": feature_cols,
            "importance": model.feature_importances_,
        }
    ).sort_values("importance", ascending=False)

    print("\n- Feature Importance Top 20")
    print(importance_df.head(20).to_string(index=False))

    Path(MODEL_DIR).mkdir(parents=True, exist_ok=True)
    joblib.dump(model, LGBM_MODEL_PATH)
    joblib.dump(feature_cols, LGBM_FEATURE_COLS_PATH)

    print(f"\n- LightGBM 모델 저장 완료: {LGBM_MODEL_PATH}")
    print(f"- LightGBM feature 목록 저장 완료: {LGBM_FEATURE_COLS_PATH}")


if __name__ == "__main__":
    main()
