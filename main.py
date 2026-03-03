# Example Code for TMDB Rating Prediction Project - MLOps Team 3
import os

import pandas as pd
import requests
from dotenv import load_dotenv
from torch.utils.data import DataLoader

from src.data.dataset import RatingsDataset

load_dotenv()
API_KEY = os.getenv("TMDB_API_KEY")
URL = os.getenv("TMDB_BASE_URL")


def fetch_tmdb_data(page=1):
    all_movies = []

    if not API_KEY:
        print("에러: .env 파일에서 TMDB_API_KEY를 찾을 수 없습니다.")
        return pd.DataFrame()

    for page in range(1, page + 1):
        url = f"https://api.themoviedb.org/3/movie/popular?api_key={API_KEY}&language=ko-KR&page={page}"
        response = requests.get(url)
        if response.status_code == 200:
            all_movies.extend(response.json()["results"])
        else:
            print(f"에러 {response.status_code} : {response.text}")
            return pd.DataFrame()

    return pd.DataFrame(all_movies)


def main():
    df_raw = fetch_tmdb_data(page=2)
    features = ["popularity", "vote_count"]
    target = "vote_average"

    df = df_raw[features + [target]].dropna()

    print(f"수집된 데이터 샘플:\n{df.head()}")

    dataset = RatingsDataset(df, feature_cols=features, target_col=target)
    train_loader = DataLoader(dataset, batch_size=8, shuffle=True)

    for x, y in train_loader:
        print(f"입력 데이터 형태: {x.shape}")  # [8, 2] 형태여야 함
        print(f"타겟 데이터 형태: {y.shape}")  # [8, 1] 형태여야 함
        break


if __name__ == "__main__":
    main()
