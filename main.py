import os

import pandas as pd
from dotenv import load_dotenv

from src.config import MAX_PAGE, PROCESSED_DATA_PATH, RAW_DATA_PATH
from src.data.crawler import TMDBCollector
from src.data.database import engine
from src.data.preprocessor import (
    add_adult_feature,
    add_date_features,
    add_derived_features,
    add_genre_features,
    add_log_features,
    fill_missing_numeric,
    filter_data,
    save_processed_data,
)

load_dotenv()


def get_data_from_db():
    """DATABASE에서 수집된 데이터를 로드합니다."""
    query = "SELECT * FROM movies_raw"
    try:
        df = pd.read_sql(query, con=engine)
        return df
    except Exception as e:
        print(f"DB 로드 실패 --> {e}")
        return pd.DataFrame()


def main():
    api_key = os.getenv("TMDB_API_KEY")
    force_update = False

    df_raw = get_data_from_db()
    current_count = len(df_raw)

    target_min_count = MAX_PAGE * 20

    is_data_insufficient = (
        current_count < target_min_count
    )  # DB 갱신 조건: 목표 수량 미달 시 데이터 보충 및 기존 항목 업데이트 (1개라도 부족하면 수집 시작)

    if df_raw.empty or is_data_insufficient or force_update:
        print(
            f"- 데이터가 부족한 관계로 추가 수집 시작 (기존 데이터 수: {current_count}개, 목표 데이터 수: 약 {target_min_count}건)"
        )
        collector = TMDBCollector(api_key)
        df_raw = collector.fetch_tmdb_data(max_pages=MAX_PAGE)

        if df_raw.empty:
            print("- 에러: 데이터 수집에 실패했습니다.\n")
            return

        os.makedirs(os.path.dirname(RAW_DATA_PATH), exist_ok=True)
        df_raw.to_csv(RAW_DATA_PATH, index=False, encoding="utf-8-sig")
        print(f"\n- 신규 데이터 저장 및 반영 완료: {RAW_DATA_PATH}")

    else:
        print(
            f"- 기존 데이터로 진행 --> (기존 데이터 수: {current_count}건 / 목표 데이터 수: {target_min_count}건)"
        )

    if "tmdb_id" in df_raw.columns:
        df_raw = df_raw.rename(columns={"tmdb_id": "id"})

    essential_features = ["budget", "runtime", "popularity", "vote_count", "vote_average", "id"]
    missing_columns = [col for col in essential_features if col not in df_raw.columns]

    if missing_columns:
        print(f"- 에러: 필수 컬럼이 없습니다: {missing_columns}\n")
        return

    df_processed = filter_data(df_raw.copy())
    df_processed = add_date_features(df_processed)
    df_processed = add_log_features(df_processed)
    df_processed = add_derived_features(df_processed)
    df_processed = add_adult_feature(df_processed)
    df_processed = add_genre_features(df_processed)
    df_processed = fill_missing_numeric(df_processed)
    save_processed_data(df_processed)

    df_ready = pd.read_csv(PROCESSED_DATA_PATH)
    print(f"- 전처리 데이터 검증 완료: 총 {len(df_ready)}개")


if __name__ == "__main__":
    main()
