import time

import pandas as pd
import requests
from tqdm import tqdm


class TMDBCollector:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"

    def fetch_tmdb_data(self, max_pages=50) -> pd.DataFrame:
        all_movies = []

        if not self.api_key:
            print("에러: .env 파일에 TMDB_API_KEY가 존재하지 않습니다.")
            return pd.DataFrame()

        for page in tqdm(range(1, max_pages + 1), desc="TMDB 데이터 페이지 수집 시작"):
            url = f"{self.base_url}/movie/popular?api_key={self.api_key}&language=ko-KR&page={page}"
            try:
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()
                movies = data.get("results", [])

                for movie in movies:
                    detail = self._get_movie_details(movie["id"])
                    movie.update(detail)
                    all_movies.append(movie)
                time.sleep(0.5)

            except requests.RequestException as e:
                print(f"요청 실패: {page} --> {e}")
                break

        print(f"데이터 수집 완료 : 총 {len(all_movies)}개의 영화 정보.")
        return pd.DataFrame(all_movies)

    def _get_movie_details(self, movie_id):
        url = f"{self.base_url}/movie/{movie_id}?api_key={self.api_key}&language=ko-KR"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                return {"budget": data.get("budget", 0), "runtime": data.get("runtime", 0)}
        except Exception:
            pass
        return {"budget": 0, "runtime": 0}
