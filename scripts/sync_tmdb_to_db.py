from __future__ import annotations

import os
from datetime import datetime
from tempfile import TemporaryDirectory

from src.config import MAX_PAGE
from src.config import settings
from src.data.crawler import TMDBCollector
from src.data.s3_io import upload_file


def _default_train_data_s3_key() -> str:
    return f"tmdb/{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}/train.csv"


if __name__ == "__main__":
    api_key = os.getenv("TMDB_API_KEY")
    if not api_key:
        raise RuntimeError("TMDB_API_KEY 환경변수가 설정되지 않았습니다.")

    print(f"- TMDB 데이터 수집 시작 (최대 {MAX_PAGE}페이지, 한국 영화만)")
    collector = TMDBCollector(api_key)
    df_raw = collector.fetch_tmdb_data(max_pages=MAX_PAGE, korean_only=True)

    if df_raw.empty:
        print("- 경고: 수집된 데이터가 없습니다.")
    else:
        print(f"- TMDB 데이터 수집 및 DB 저장 완료: 총 {len(df_raw)}개 영화 정보")
