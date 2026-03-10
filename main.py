import os

import pandas as pd
from dotenv import load_dotenv

from src.config import RAW_DATA_PATH
from src.data import preprocessor
from src.data.database import engine

load_dotenv()


def get_data_from_db() -> pd.DataFrame:
    query = "SELECT * FROM movies_raw"
    try:
        return pd.read_sql(query, con=engine)
    except Exception as e:
        print(f"DB 로드 실패 --> {e}")
        return pd.DataFrame()


def sync_db_to_raw_csv() -> pd.DataFrame:
    df_raw = get_data_from_db()

    if df_raw.empty:
        raise RuntimeError(
            "movies_raw 테이블이 비어 있습니다. 먼저 `uv run python -m scripts.sync_tmdb_to_db`를 실행하세요."
        )

    print(f"- DB 데이터 로드 완료: {len(df_raw)}건")

    os.makedirs(os.path.dirname(RAW_DATA_PATH), exist_ok=True)
    df_raw.to_csv(RAW_DATA_PATH, index=False, encoding="utf-8-sig")
    print(f"- DB 데이터 로컬 raw 파일 동기화 완료: {RAW_DATA_PATH}")

    return df_raw


def main() -> None:
    sync_db_to_raw_csv()

    print("\n- [전처리 시작]")
    preprocessor.main()

    print("\n- [완료]")
    print("- 데이터 수집은 scripts.sync_tmdb_to_db")
    print("- 학습은 src.train.run_train")
    print("- 추론은 src.infer.run_infer_worker")


if __name__ == "__main__":
    main()
