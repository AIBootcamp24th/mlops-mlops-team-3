import os
import pandas as pd
from datetime import datetime
from tempfile import TemporaryDirectory
from sqlalchemy import text

from src.data.database import SessionLocal
from src.data.s3_io import upload_file
from src.config import settings

def export_movies_to_s3(s3_key: str = None) -> str:
    """Queries all movies from RDS and uploads to S3 as CSV."""
    if s3_key is None:
        s3_key = f"tmdb/{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}/train.csv"
        
    print("- DB 데이터(movies_raw) S3 내보내기 시작")
    db = SessionLocal()
    try:
        query = text("SELECT * FROM movies_raw")
        result = db.execute(query)
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
        
        if df.empty:
            print("- 경고: DB에 데이터가 없습니다.")
            return ""
            
        print(f"- DB 데이터 로드 완료: {len(df)}건")
        
        with TemporaryDirectory() as tmpdir:
            local_csv = os.path.join(tmpdir, "train.csv")
            df.to_csv(local_csv, index=False)
            s3_uri = upload_file(local_csv, settings.aws_s3_raw_bucket, s3_key)
            print(f"- S3 업로드 완료: {s3_uri}")
            return s3_uri
            
    except Exception as e:
        print(f"- 데이터 내보내기 실패: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    s3_custom_key = os.getenv("TRAIN_DATA_S3_KEY")
    export_movies_to_s3(s3_custom_key)
