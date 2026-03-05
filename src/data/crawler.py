import time

import pandas as pd
import requests
from tqdm import tqdm

from src.data.preprocess import filter_korean_movies


class TMDBCollector:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"

    def fetch_tmdb_data(
        self, max_pages=5, korean_only: bool = True, total_page: int | None = None
    ) -> pd.DataFrame:
        all_movies = []
        page_limit = total_page if total_page is not None else max_pages

        if not self.api_key:
            print("에러: .env 파일에 TMDB_API_KEY가 존재하지 않습니다.")
            return pd.DataFrame()

        discover_url = f"{self.base_url}/discover/movie"

        for page in tqdm(range(1, page_limit + 1), desc="TMDB 데이터 페이지 수집 시작"):
            params = {
                "api_key": self.api_key,
                "language": "ko-KR",
                "sort_by": "popularity.desc",
                "with_original_language": "ko",
                "region": "KR",
                "page": page,
            }

            try:
                response = requests.get(discover_url, params=params)
                response.raise_for_status()
                data = response.json()
                movies = data.get("results", [])

                if not movies:
                    break

                for movie in movies:
                    detail = self._get_movie_details(movie["id"])
                    movie.update(detail)
                    all_movies.append(movie)
                time.sleep(0.4)

            except requests.RequestException as e:
                print(f"요청 실패: {page} --> {e}")
                break

        print(f"데이터 수집 완료 : 총 {len(all_movies)}개의 영화 정보.")
        df = pd.DataFrame(all_movies)
        if korean_only:
            filtered_df = filter_korean_movies(df)
            print(f"한국 영화 필터 적용 완료 : {len(filtered_df)}개 영화.")
            return filtered_df
        return df

    def _get_movie_details(self, movie_id):
        url = f"{self.base_url}/movie/{movie_id}"
        params = {"api_key": self.api_key, "language": "ko-KR"}

        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return {"budget": data.get("budget", 0), "runtime": data.get("runtime", 0)}
        except Exception:
            pass
        return {"budget": 0, "runtime": 0}
