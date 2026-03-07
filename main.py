import os

import pandas as pd
from dotenv import load_dotenv
from torch.utils.data import DataLoader

from src.config import BATCH_SIZE, MAX_PAGE, RAW_DATA_PATH, RESULT_DIR
from src.data.crawler import TMDBCollector
from src.data.database import engine
from src.data.dataset import RatingsDataset
from src.data.preprocessor import DataPreprocessor

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

    df_filtered = df_raw[essential_features].copy()

    df_filtered["runtime"] = df_filtered["runtime"].replace(0, 120).fillna(120)
    df_filtered["budget"] = df_filtered["budget"].fillna(0)

    df_filtered = df_filtered[df_filtered["vote_count"] > 0]

    print(f"- 필터링 후 학습 가능 샘플 수: 총 {len(df_filtered)}개\n")

    preprocessor = DataPreprocessor(df_filtered)
    preprocessor.run()

    preprocessor.save(dst_dir=RESULT_DIR, filename="rating_data")

    processed_path = os.path.join(RESULT_DIR, "rating_data.csv")
    df_ready = pd.read_csv(processed_path)

    train_features = ["watch_ratio", "popularity", "runtime", "budget"]
    target_col = "target_rating"

    dataset = RatingsDataset(df_ready, feature_cols=train_features, target_col=target_col)
    train_loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

    for x, y in train_loader:
        print(f"\n- [검증] 입력(X) 형태: {x.shape}")
        print(f"- [검증] 타겟(Y) 형태: {y.shape}\n")
        break


if __name__ == "__main__":
    main()
