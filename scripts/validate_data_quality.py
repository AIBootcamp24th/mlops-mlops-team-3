import sys
import pandas as pd
from sqlalchemy import text
from src.data.database import SessionLocal
from src.utils.slack_notifier import send_slack_message

# Quality Thresholds
MAX_NULL_RATIO = 0.1  # 10%
MIN_DATA_COUNT = 100
VALID_VOTE_RANGE = (0, 10)

def validate_quality():
    print("- 데이터 품질 검증 시작")
    db = SessionLocal()
    try:
        query = text("SELECT * FROM movies_raw")
        result = db.execute(query)
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
        
        if len(df) < MIN_DATA_COUNT:
            msg = f":warning: [Data Quality] 데이터 건수가 너무 적습니다. (현재: {len(df)}, 최소: {MIN_DATA_COUNT})"
            print(msg)
            send_slack_message(msg)
            sys.exit(1)

        # 1. Null Ratio Check
        null_counts = df[["budget", "runtime", "popularity", "vote_count", "vote_average"]].isnull().mean()
        high_null_cols = null_counts[null_counts > MAX_NULL_RATIO]
        if not high_null_cols.empty:
            msg = f":x: [Data Quality] 결측치 비율이 너무 높습니다.\n{high_null_cols.to_string()}"
            print(msg)
            send_slack_message(msg)
            sys.exit(1)

        # 2. Value Range Check
        invalid_votes = df[(df["vote_average"] < VALID_VOTE_RANGE[0]) | (df["vote_average"] > VALID_VOTE_RANGE[1])]
        if not invalid_votes.empty:
            msg = f":x: [Data Quality] 범위를 벗어난 평점 데이터가 발견되었습니다. (건수: {len(invalid_votes)})"
            print(msg)
            send_slack_message(msg)
            sys.exit(1)

        # 3. Numeric Check
        for col in ["budget", "runtime", "popularity"]:
            if (df[col] < 0).any():
                msg = f":x: [Data Quality] 음수 값이 포함된 필드가 있습니다: {col}"
                print(msg)
                send_slack_message(msg)
                sys.exit(1)

        print("- 데이터 품질 검증 통과!")
        sys.exit(0)

    except Exception as e:
        msg = f":red_circle: [Data Quality] 검증 중 에러 발생: {e}"
        print(msg)
        send_slack_message(msg)
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    validate_quality()
