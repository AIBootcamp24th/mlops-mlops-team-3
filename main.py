import os

import pandas as pd
from dotenv import load_dotenv
from torch.utils.data import DataLoader

from src.data.crawler import TMDBCollector
from src.data.dataset import RatingsDataset

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
            print(f"신규 데이터 수집 및 저장 완료: {raw_data_path}")
        else:
            print("데이터 수집 실패.")
            return
    else:
        df_raw = pd.read_csv(raw_data_path)
        print(f"기존 데이터를 로드했습니다: {raw_data_path}")

    features = ["popularity", "vote_count"]
    target = "vote_average"

    df = df_raw[features + [target]].dropna()

    dataset = RatingsDataset(df, feature_cols=features, target_col=target)
    train_loader = DataLoader(dataset, batch_size=8, shuffle=True)

    for x, y in train_loader:
        print(f"입력 데이터(X) 형태: {x.shape}")
        print(f"타겟 데이터(Y) 형태: {y.shape}")
        break


if __name__ == "__main__":
    main()
