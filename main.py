import os

import pandas as pd
import requests
from dotenv import load_dotenv
from torch.utils.data import DataLoader

from src.data.crawler import TMDBCollector
from src.data.dataset import RatingsDataset
from src.data.preprocessor import DataPreprocessor

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
    api_key = os.getenv("TMDB_API_KEY")
    raw_data_path = "./src/data/raw/movies.csv"
    os.makedirs("./src/data/raw", exist_ok=True)

    force_update = True

    if not os.path.exists(raw_data_path) or force_update:
        collector = TMDBCollector(api_key)
        df_raw = collector.fetch_tmdb_data(max_pages=50)
        if not df_raw.empty:
            df_raw.to_csv(raw_data_path, index=False)
            print(f"신규 데이터 저장 완료: {raw_data_path}")
    else:
        df_raw = pd.read_csv(raw_data_path)
        print(f"기존 데이터 로드 완료: {raw_data_path}")

    features = ["budget", "runtime", "popularity", "vote_count"]
    target = "vote_average"

    df_filtered = df_raw[features + [target, "id"]].dropna()
    df_filtered = df_filtered[(df_filtered["budget"] > 0) & (df_filtered["runtime"] > 0)]

    print(f"학습용 영화 샘플 = 총 {len(df_filtered)}개")

    preprocessor = DataPreprocessor(df_filtered, user_count=100, max_selected_count=20)
    preprocessor.run()

    preprocessor.save(dst_dir="./src/data/result", filename="watch_log")

    dataset = RatingsDataset(df_filtered, feature_cols=features, target_col=target)
    train_loader = DataLoader(dataset, batch_size=8, shuffle=True)

    for x, y in train_loader:
        print(f"입력 데이터(X) 형태: {x.shape}")
        print(f"타겟 데이터(Y) 형태: {y.shape}")
        break


if __name__ == "__main__":
    main()
