import pandas as pd
import requests

from src.data.preprocess import filter_korean_movies


class TMDBCollector:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"

    def fetch_tmdb_data(self, max_pages=5, korean_only: bool = True) -> pd.DataFrame:
        all_movies = []

        if not self.api_key:
            print("에러: .env 파일에서 TMDB_API_KEY를 찾을 수 없습니다.")
            return pd.DataFrame()

        for page in range(1, max_pages + 1):
            url = f"https://api.themoviedb.org/3/movie/popular?api_key={self.api_key}&language=ko-KR&page={page}"
            try:
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()
                movies = data.get("results", [])
                all_movies.extend(movies)

                if page % 5 == 0:
                    print(f"{page} 페이지까지 데이터 수집 완료.")

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
