import os
import json
from sqlalchemy import text
from src.data.database import SessionLocal
from src.data.s3_io import download_file, upload_file
from src.config import settings
from tempfile import TemporaryDirectory

METADATA_S3_KEY = "metadata/last_data_count.json"

def get_current_stats() -> dict[str, int]:
    db = SessionLocal()
    try:
        query = text(
            """
            SELECT
                COUNT(*) AS count,
                COALESCE(
                    SUM(
                        CRC32(
                            CONCAT_WS(
                                '|',
                                tmdb_id,
                                COALESCE(title, ''),
                                COALESCE(original_title, ''),
                                COALESCE(vote_average, 0),
                                COALESCE(vote_count, 0),
                                COALESCE(popularity, 0),
                                COALESCE(runtime, 0),
                                COALESCE(budget, 0)
                            )
                        )
                    ),
                    0
                ) AS fingerprint
            FROM movies_raw
            """
        )
        row = db.execute(query).mappings().first()
        return {
            "count": int(row["count"] or 0),
            "fingerprint": int(row["fingerprint"] or 0),
        }
    finally:
        db.close()

def get_last_stats() -> dict[str, int]:
    with TemporaryDirectory() as tmpdir:
        local_path = os.path.join(tmpdir, "metadata.json")
        try:
            download_file(settings.aws_s3_raw_bucket, METADATA_S3_KEY, local_path)
            with open(local_path, "r") as f:
                data = json.load(f)
                return {
                    "count": int(data.get("count", 0)),
                    "fingerprint": int(data.get("fingerprint", 0)),
                }
        except Exception:
            return {"count": 0, "fingerprint": 0}

def update_last_stats(stats: dict[str, int]):
    with TemporaryDirectory() as tmpdir:
        local_path = os.path.join(tmpdir, "metadata.json")
        with open(local_path, "w") as f:
            json.dump(stats, f)
        upload_file(local_path, settings.aws_s3_raw_bucket, METADATA_S3_KEY)

def main():
    current_stats = get_current_stats()
    last_stats = get_last_stats()
    
    print(f"- 이전 데이터 개수: {last_stats['count']}")
    print(f"- 현재 데이터 개수: {current_stats['count']}")
    print(f"- 이전 지문값: {last_stats['fingerprint']}")
    print(f"- 현재 지문값: {current_stats['fingerprint']}")
    
    if (
        current_stats["count"] != last_stats["count"]
        or current_stats["fingerprint"] != last_stats["fingerprint"]
    ):
        print("- 데이터 변경 감지: 학습 진행 필요")
        update_last_stats(current_stats)
        exit(0)  # Change detected
    else:
        print("- 데이터 변화 없음: 학습 스킵")
        exit(1)  # No change

if __name__ == "__main__":
    main()
