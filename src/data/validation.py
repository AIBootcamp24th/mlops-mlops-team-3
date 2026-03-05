from __future__ import annotations

import pandas as pd


def _ensure_columns(df: pd.DataFrame, required_cols: list[str]) -> None:
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"필수 컬럼이 누락되었습니다: {missing_cols}")


def _ensure_numeric(df: pd.DataFrame, cols: list[str]) -> None:
    non_numeric_cols = [col for col in cols if not pd.api.types.is_numeric_dtype(df[col])]
    if non_numeric_cols:
        raise ValueError(f"숫자형 컬럼이 아닙니다: {non_numeric_cols}")


def _ensure_non_negative(df: pd.DataFrame, cols: list[str]) -> None:
    negative_cols = [col for col in cols if (df[col] < 0).any()]
    if negative_cols:
        raise ValueError(f"음수 값이 허용되지 않는 컬럼입니다: {negative_cols}")


def validate_training_frame(df: pd.DataFrame, feature_cols: list[str], target_col: str) -> None:
    if df.empty:
        raise ValueError("학습 데이터가 비어 있습니다.")
    _ensure_columns(df, feature_cols + [target_col])
    _ensure_numeric(df, feature_cols + [target_col])
    _ensure_non_negative(df, feature_cols)


def validate_inference_frame(df: pd.DataFrame, feature_cols: list[str]) -> None:
    if df.empty:
        raise ValueError("추론 데이터가 비어 있습니다.")
    _ensure_columns(df, feature_cols)
    _ensure_numeric(df, feature_cols)
    _ensure_non_negative(df, feature_cols)
