import os

import pandas as pd
from dotenv import load_dotenv
from torch.utils.data import DataLoader

from src.config import RAW_DATA_PATH, RESULT_DIR, TOTAL_PAGES
from src.data.crawler import TMDBCollector
from src.data.dataset import RatingsDataset
from src.data.preprocessor import DataPreprocessor

load_dotenv()


def main():
    api_key = os.getenv("TMDB_API_KEY")

    force_update = False

    if not os.path.exists(RAW_DATA_PATH) or force_update:
        collector = TMDBCollector(api_key)
        df_raw = collector.fetch_tmdb_data(max_pages=TOTAL_PAGES)

        if not df_raw.empty:
            os.makedirs(os.path.dirname(RAW_DATA_PATH), exist_ok=True)
            df_raw.to_csv(RAW_DATA_PATH, index=False, encoding="utf-8-sig")
            print(f"신규 데이터 저장 완료: {RAW_DATA_PATH}")

    else:
        if os.path.exists(RAW_DATA_PATH):
            df_raw = pd.read_csv(RAW_DATA_PATH)
            print(f"기존 데이터를 로드했습니다: {RAW_DATA_PATH}")
        else:
            print("에러: 데이터 파일이 없고 수집도 수행되지 않았습니다.")
            return

    essential_features = ["budget", "runtime", "popularity", "vote_count", "vote_average", "id"]
    missing_columns = [col for col in essential_features if col not in df_raw.columns]
    if missing_columns:
        print(f"에러: 필수 컬럼이 없습니다: {missing_columns}")
        return

    df_filtered = df_raw[essential_features].copy()

    df_filtered["runtime"] = df_filtered["runtime"].replace(0, 120).fillna(120)
    df_filtered["budget"] = df_filtered["budget"].fillna(0)

    df_filtered = df_filtered[df_filtered["vote_count"] > 0]

    print(f"필터링 후 학습 가능 샘플 수: 총 {len(df_filtered)}개")

    preprocessor = DataPreprocessor(df_filtered)
    preprocessor.run()

    preprocessor.save(dst_dir=RESULT_DIR, filename="rating_data")

    processed_path = os.path.join(RESULT_DIR, "rating_data.csv")
    df_ready = pd.read_csv(processed_path)

    train_features = ["watch_ratio", "popularity", "runtime", "budget"]
    target_col = "target_rating"

    dataset = RatingsDataset(df_ready, feature_cols=train_features, target_col=target_col)
    train_loader = DataLoader(dataset, batch_size=32, shuffle=True)

    for x, y in train_loader:
        print(f"[검증] 입력(X) 형태: {x.shape}")
        print(f"[검증] 타겟(Y) 형태: {y.shape}")
        break


if __name__ == "__main__":
    main()
