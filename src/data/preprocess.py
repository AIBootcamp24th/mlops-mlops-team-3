from __future__ import annotations

import pandas as pd

from src.constants import KOREAN_LANGUAGE_CODE, LANGUAGE_COL


def filter_korean_movies(df: pd.DataFrame, require_language_col: bool = False) -> pd.DataFrame:
    if LANGUAGE_COL not in df.columns:
        if require_language_col:
            raise ValueError(f"'{LANGUAGE_COL}' 컬럼이 없어 한국 영화 필터를 적용할 수 없습니다.")
        return df

    return df[df[LANGUAGE_COL] == KOREAN_LANGUAGE_CODE].copy()
