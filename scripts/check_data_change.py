import os
import json
from sqlalchemy import text
from src.data.database import SessionLocal
from src.data.s3_io import download_file, upload_file
from src.config import settings
from tempfile import TemporaryDirectory

METADATA_S3_KEY = "metadata/last_data_count.json"

def get_current_count() -> int:
    db = SessionLocal()
    try:
        query = text("SELECT COUNT(*) FROM movies_raw")
        count = db.execute(query).scalar()
        return count
    finally:
        db.close()

def get_last_count() -> int:
    with TemporaryDirectory() as tmpdir:
        local_path = os.path.join(tmpdir, "metadata.json")
        try:
            download_file(settings.aws_s3_raw_bucket, METADATA_S3_KEY, local_path)
            with open(local_path, "r") as f:
                data = json.load(f)
                return data.get("count", 0)
        except Exception:
            return 0

def update_last_count(count: int):
    with TemporaryDirectory() as tmpdir:
        local_path = os.path.join(tmpdir, "metadata.json")
        with open(local_path, "w") as f:
            json.dump({"count": count}, f)
        upload_file(local_path, settings.aws_s3_raw_bucket, METADATA_S3_KEY)

def main():
    current_count = get_current_count()
    last_count = get_last_count()
    
    print(f"- 이전 데이터 개수: {last_count}")
    print(f"- 현재 데이터 개수: {current_count}")
    
    if current_count > last_count:
        print("- 데이터 증가 감지: 학습 진행 필요")
        update_last_count(current_count)
        exit(0)  # Change detected
    else:
        print("- 데이터 변화 없음: 학습 스킵")
        exit(1)  # No change

if __name__ == "__main__":
    main()
