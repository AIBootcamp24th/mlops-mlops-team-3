import os

import joblib
import numpy as np
import pandas as pd
import torch

from src.config import BASE_DIR, RAW_DATA_PATH, RESULT_DIR
from src.model.network import RatingPredictor

FEATURE_COLS = ["watch_ratio", "popularity", "runtime", "budget"]


def _generate_watch_ratio(rating: float) -> float:
    z = (rating - 5.0) / 2.0
    ratio = 1.0 / (1.0 + np.exp(-z))
    return float(np.clip(ratio, 0.05, 0.98))


def _is_korean_movie(row: pd.Series) -> bool:
    country_data = str(row.get("origin_country", "")).upper()
    original_lang = str(row.get("original_language", "")).lower()
    return ("KR" in country_data) or (original_lang == "ko")


def _build_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    feature_df = df.copy()

    feature_df["watch_ratio"] = feature_df["vote_average"].fillna(0).apply(_generate_watch_ratio)
    feature_df["popularity"] = feature_df["popularity"].fillna(0.0).astype(float)
    feature_df["runtime"] = feature_df["runtime"].fillna(120.0).astype(float)
    feature_df.loc[feature_df["runtime"] <= 0, "runtime"] = 120.0
    feature_df["budget"] = feature_df["budget"].fillna(0.0).astype(float)

    feature_df["popularity"] = feature_df["popularity"].clip(upper=500)
    feature_df["budget"] = feature_df["budget"].clip(upper=300_000_000)

    return feature_df


def load_model(device: torch.device) -> RatingPredictor:
    model_path = os.path.join(BASE_DIR, "artifacts", "rating_model.pt")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"- 모델 파일이 없습니다: {model_path}")

    model = RatingPredictor(input_dim=len(FEATURE_COLS)).to(device)
    state_dict = torch.load(model_path, map_location=device)
    model.load_state_dict(state_dict)
    model.eval()
    return model


def run_local_inference() -> str:
    if not os.path.exists(RAW_DATA_PATH):
        raise FileNotFoundError(f"- 원본 데이터 파일이 없습니다: {RAW_DATA_PATH}")

    os.makedirs(RESULT_DIR, exist_ok=True)
    output_path = os.path.join(RESULT_DIR, "inference_check.csv")

    df = pd.read_csv(RAW_DATA_PATH)
    print(f"- 원본 데이터 로드 완료: {len(df)}건")

    korean_mask = df.apply(_is_korean_movie, axis=1)
    df = df.loc[korean_mask].copy()
    print(f"- 한국 영화 필터링 완료: {len(df)}건")

    if df.empty:
        raise ValueError("- 한국 영화 데이터가 없습니다.")

    feature_df = _build_feature_frame(df)

    missing_cols = [col for col in FEATURE_COLS if col not in feature_df.columns]
    if missing_cols:
        raise ValueError(f"- 추론에 필요한 feature가 없습니다: {missing_cols}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_model(device)

    scaler_path = os.path.join(RESULT_DIR, "scaler.joblib")

    if not os.path.exists(scaler_path):
        raise FileNotFoundError(f"스케일러 파일이 없습니다: {scaler_path}")

    scaler = joblib.load(scaler_path)

    X = feature_df[FEATURE_COLS]
    X_scaled = scaler.transform(X)
    X_tensor = torch.tensor(X_scaled, dtype=torch.float32).to(device)

    with torch.no_grad():
        predictions = model(X_tensor).squeeze().cpu().numpy()

    out_df = df.copy()
    predictions = np.clip(predictions * 10.0, 0.0, 10.0)
    out_df["predicted_rating"] = predictions

    keep_cols = [
        col
        for col in ["title", "release_date", "vote_average", "predicted_rating"]
        if col in out_df.columns
    ]
    out_df = out_df[keep_cols].sort_values(by="predicted_rating", ascending=False)

    out_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"- 추론 완료: {output_path}")
    print(out_df.head(10).to_string(index=False))

    return output_path


if __name__ == "__main__":
    run_local_inference()
