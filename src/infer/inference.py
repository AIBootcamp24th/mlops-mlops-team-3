import os
import sys

import joblib
import numpy as np
import pandas as pd
import torch

from src.config import INPUT_DIM, RESULT_DIR
from src.model.network import RatingPredictor


def _generate_watch_ratio(rating):
    z = (rating - 5) / 2
    ratio = 1 / (1 + np.exp(-z))
    return np.clip(ratio, 0.05, 0.98)


def predict():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model_path = "./src/model/checkpoints/model.pth"
    scaler_path = os.path.join(RESULT_DIR, "scaler.joblib")
    csv_path = "./src/data/raw/movies.csv"

    if not all(os.path.exists(p) for p in [model_path, scaler_path, csv_path]):
        print("에러: 필요한 파일(model, scaler, movies.csv) 중 일부가 없습니다.")
        return

    input_dim = INPUT_DIM
    model = RatingPredictor(input_dim=input_dim).to(device)
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()
    scaler = joblib.load(scaler_path)
    df_db = pd.read_csv(csv_path)

    print("한국 영화 평점 예측 시스템 (종료하려면 'q' 또는 '종료' 입력)")

    while True:
        print(f"\n현재 DB 내 영화 수: {len(df_db)}개")
        search_title = input("평점을 예측할 한국 영화 제목을 입력하세요 (종료: q): ").strip()

        # 종료 조건 체크
        if search_title.lower() in ["q", "quit", "종료", "exit"]:
            print("한국 영화 평점 예측 시스템을 종료합니다.")
            break

        if not search_title:
            continue

        target_movie = df_db[df_db["title"].str.contains(search_title, case=False, na=False)]

        if target_movie.empty:
            print(f"'{search_title}'와 일치하는 영화를 찾을 수 없습니다.")
            continue

        target_movie = target_movie.sort_values(by="release_date", ascending=True)

        if len(target_movie) == 1:
            movie = target_movie.iloc[0]
            print(
                f"\n\t[검색결과]\n\t[{movie['title']}] (개봉일: {movie['release_date']})]에 대한 검색 결과는 총 1건 입니다."
            )
        else:
            print(
                f"\n\t[검색결과]\n\t[{search_title}]에 대한 검색 결과는 총 {len(target_movie)}건 입니다. (개봉일순):\n"
            )

            display_movie = target_movie.head(10)
            for i, (idx, row) in enumerate(display_movie.iterrows(), 1):
                print(f"\t[{i}] {row['title']} ({row['release_date']})")

            try:
                choice = input("\n분석할 영화의 번호를 입력하세요 (취소: c): ").strip()
                if choice.lower() == "c":
                    continue

                selected_idx = int(choice) - 1
                if not (0 <= selected_idx < len(display_movie)):
                    print("잘못된 번호입니다. 다시 시도해 주세요.")
                    continue

                movie = display_movie.iloc[selected_idx]
            except ValueError:
                print("숫자만 입력 가능합니다.")
                continue

        movie = target_movie.iloc[0]

        country_data = str(movie.get("origin_country", "")).upper()
        original_lang = str(movie.get("original_language", "")).lower()

        if not ("KR" in country_data or "ko" in original_lang):
            print(f"경고: 입력하신 영화제목 [{movie['title']}]은(는) 한국 영화가 아닙니다.")
            print(
                "경고: 본 모델은 한국 영화 데이터에 최적화되어 있어 외국 영화의 예측을 제한 합니다."
            )
            continue

        watch_ratio = _generate_watch_ratio(movie["vote_average"])

        pop_val = movie.get("popularity", 0)
        run_val = movie.get("runtime", 120)
        bud_val = movie.get("budget", 0)

        clean_popularity = float(pop_val) if not pd.isna(pop_val) else 0.0
        clean_runtime = float(run_val) if not pd.isna(run_val) and run_val > 0 else 120.0
        clean_budget = float(bud_val) if not pd.isna(bud_val) else 0.0

        clean_popularity = min(clean_popularity, 500)
        clean_budget = min(clean_budget, 300_000_000)

        raw_input = pd.DataFrame(
            [[watch_ratio, clean_popularity, clean_runtime, clean_budget]],
            columns=["watch_ratio", "popularity", "runtime", "budget"],
        )

        scaled_input = scaler.transform(raw_input)

        if np.isnan(scaled_input).any():
            print("경고: 입력 데이터에 결측치가 포함되어 있습니다. 기본값으로 대체합니다.")
            scaled_input = np.nan_to_num(scaled_input)

        input_tensor = torch.tensor(scaled_input, dtype=torch.float32).to(device)

        with torch.no_grad():
            prediction = model(input_tensor)
            result = prediction.item()

            predicted_rating = (result * 15.0) + 5.0

            if watch_ratio > 0.85:
                predicted_rating += 1.5
            elif watch_ratio < 0.75:
                predicted_rating -= 0.5

            predicted_rating = np.clip(predicted_rating, 1.0, 9.5)

        print(f"\n\t(1) 모델이 분석한 예상 평점: {predicted_rating:.2f} / 10.0 점")
        print(f"\t(2) 실제 TMDB 평점: {movie['vote_average']:.2f} / 10.0 점")


if __name__ == "__main__":
    try:
        predict()
    except KeyboardInterrupt:
        print("\n\n사용자 요청에 의해 한국 영화 예측 모델을 종료합니다.")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
