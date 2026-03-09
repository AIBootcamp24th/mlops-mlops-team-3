import json
import time
from urllib.parse import quote_plus

import pandas as pd
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

from src.config import MAX_PAGE, SQL
from src.config import settings
from src.data.database import SessionLocal
from src.data.preprocess import filter_korean_movies


class TMDBCollector:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"

    def fetch_tmdb_data(
        self, max_pages=MAX_PAGE, korean_only: bool = True, total_page: int | None = None
    ) -> pd.DataFrame:
        all_movies = []
        page_limit = total_page if total_page is not None else max_pages

        if not self.api_key:
            print("에러: .env 파일에 TMDB_API_KEY가 존재하지 않습니다.")
            return pd.DataFrame()

        discover_url = f"{self.base_url}/discover/movie"

        for page in tqdm(range(1, page_limit + 1), desc="- TMDB 데이터 페이지 수집 중"):
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

        print(f"\n- 데이터 수집 완료: 총 {len(all_movies)}개의 영화 정보")

        df = pd.DataFrame(all_movies)

        if korean_only:
            filtered_df = filter_korean_movies(df)
            print(f"- 한국 영화 필터 적용 완료: {len(filtered_df)}개 영화\n")

            # korean_only 모드에서는 DB 저장도 한국어 원어 영화만 허용한다.
            if not filtered_df.empty and not self.save_to_db(filtered_df):
                raise RuntimeError(f"{SQL} DB 저장에 실패했습니다.")
            return filtered_df

        if not df.empty and not self.save_to_db(df):
            raise RuntimeError(f"{SQL} DB 저장에 실패했습니다.")
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

    def save_to_db(self, df: pd.DataFrame) -> bool:
        """영화 데이터를 DB에 저장하거나, 중복된 경우 최신 내용으로 갱신합니다."""
        print(f"- {len(df)}개의 데이터를 {SQL} DB에 저장 시작")
        db = SessionLocal()
        secondary_db = self._create_secondary_session()
        try:
            query = text("""
                INSERT INTO movies_raw 
                (tmdb_id, title, original_title, overview, release_date, budget, runtime, vote_average, vote_count, popularity, original_language, poster_path, genres)
                VALUES 
                (:id, :title, :original_title, :overview, :release_date, :budget, :runtime, :vote_average, :vote_count, :popularity, :original_language, :poster_path, :genres)
                ON DUPLICATE KEY UPDATE
                title = VALUES(title),
                budget = VALUES(budget),
                runtime = VALUES(runtime),
                vote_average = VALUES(vote_average),
                vote_count = VALUES(vote_count),
                popularity = VALUES(popularity),
                poster_path = VALUES(poster_path),
                overview = VALUES(overview)
            """)

            for _, row in df.iterrows():
                params = {
                    "id": row.get("id"),
                    "title": row.get("title"),
                    "original_title": row.get("original_title"),
                    "overview": row.get("overview"),
                    "release_date": None
                    if pd.isna(row.get("release_date")) or row.get("release_date") == ""
                    else row.get("release_date"),  # 날짜가 비어있거나 NaT인 경우 None으로 저장
                    "vote_average": row.get("vote_average"),
                    "vote_count": row.get("vote_count"),
                    "popularity": row.get("popularity"),
                    "original_language": row.get("original_language"),
                    "poster_path": row.get("poster_path"),
                    "genres": json.dumps(row.get("genre_ids", [])),
                    "budget": row.get("budget", 0),
                    "runtime": row.get("runtime", 0),
                }
                db.execute(query, params)
                if secondary_db is not None:
                    secondary_db.execute(query, params)

            db.commit()
            if secondary_db is not None:
                secondary_db.commit()
            print(f"- {SQL} DB 저장 완료")
            return True
        except Exception as e:
            print(f"- {SQL} DB 저장 실패 --> {e}\n")
            db.rollback()
            if secondary_db is not None:
                secondary_db.rollback()
            return False
        finally:
            db.close()
            if secondary_db is not None:
                secondary_db.close()

    def _create_secondary_session(self):
        secondary_host = settings.get_secondary_db_host()
        if not secondary_host:
            return None

        database_url = (
            f"mysql+pymysql://{quote_plus(settings.get_db_user())}:{quote_plus(settings.get_db_password())}@"
            f"{secondary_host}:{int(settings.get_secondary_db_port())}/{settings.get_db_name()}"
        )
        engine = create_engine(database_url, pool_pre_ping=True, echo=False)
        session_cls = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        return session_cls()
