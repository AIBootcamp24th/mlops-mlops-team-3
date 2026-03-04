import os

import pandas as pd
from dotenv import load_dotenv
from torch.utils.data import DataLoader

from src.constants import FEATURE_COLS, TARGET_COL
from src.data.crawler import TMDBCollector
from src.data.dataset import RatingsDataset
from src.data.preprocess import filter_korean_movies

load_dotenv()


def main():
    api_key = os.getenv("TMDB_API_KEY")

    raw_data_path = "./src/data/raw/movies.csv"
    os.makedirs("./src/data/raw", exist_ok=True)

    if not os.path.exists(raw_data_path):
        collector = TMDBCollector(api_key)
        df_raw = collector.fetch_tmdb_data(max_pages=5)

        if not df_raw.empty:
            df_raw.to_csv(raw_data_path, index=False)
            print(f"신규 데이터 수집 및 저장 완료: [저장 경로 '{raw_data_path}']")
        else:
            print("데이터 수집에 실패.")
            return
    else:
        df_raw = pd.read_csv(raw_data_path)
        print(f"기존 데이터 로드: {raw_data_path}")

    df_raw = filter_korean_movies(df_raw, require_language_col=True)
    features = [col for col in FEATURE_COLS if col in df_raw.columns]
    target = TARGET_COL

    df = df_raw[features + [target]].dropna()

    dataset = RatingsDataset(df, feature_cols=features, target_col=target)
    train_loader = DataLoader(dataset, batch_size=8, shuffle=True)

    for x, y in train_loader:
        print(f"입력 데이터(X) 형태: {x.shape}")
        print(f"타겟 데이터(Y) 형태: {y.shape}")
        break


if __name__ == "__main__":
    main()
