import os
import random

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

from src.config import RESULT_DIR


class DataPreprocessor:
    def __init__(self, movies_df, user_count=200, max_selected_count=20):
        random.seed(42)
        np.random.seed(42)
        self._movies = movies_df.copy()
        self._users = list(range(1, user_count + 1))
        self._max_selected_movies = max_selected_count
        self._max_runtime_seconds = 120 * 60
        self._features = pd.DataFrame()
        self.scaler = MinMaxScaler()
        self.target_cols = ["watch_ratio", "popularity", "runtime", "budget"]

    def _generate_watch_ratio(self, rating):
        z = (rating - 5) / 2
        ratio = 1 / (1 + np.exp(-z))

        noise = np.random.normal(0, 0.05)
        return np.clip(ratio + noise, 0.05, 0.98)

    def run(self):
        all_logs = []
        movie_records = self._movies.to_dict(orient="records")

        for user_id in self._users:
            select_count = random.randint(1, self._max_selected_movies)
            selected_movies = random.sample(movie_records, k=min(select_count, len(self._movies)))

            for movie in selected_movies:
                watch_ratio = self._generate_watch_ratio(movie["vote_average"])

                target_rating = movie["vote_average"] / 10.0

                all_logs.append(
                    {
                        "user_id": str(user_id),
                        "movie_id": str(movie["id"]),
                        "watch_ratio": watch_ratio,
                        "rating": movie["vote_average"],
                        "popularity": movie["popularity"],
                        "runtime": movie.get("runtime", 120),
                        "budget": movie.get("budget", 0),
                        "target_rating": target_rating,
                    }
                )
        self._features = pd.DataFrame(all_logs)

        high_quality = self._features[self._features["rating"] >= 7.5]
        if not high_quality.empty:
            self._features = pd.concat(
                [self._features, pd.concat([high_quality] * 20)], ignore_index=True
            )

        self._features = self._features.sample(frac=1).reset_index(drop=True)
        self._features[self.target_cols] = self.scaler.fit_transform(
            self._features[self.target_cols]
        )

    def save(self, dst_dir=RESULT_DIR, filename="rating_prediction_log"):
        os.makedirs(dst_dir, exist_ok=True)

        csv_path = os.path.join(dst_dir, f"{filename}.csv")
        self._features.to_csv(csv_path, index=False, encoding="utf-8-sig")

        scaler_path = os.path.join(dst_dir, "scaler.joblib")
        joblib.dump(self.scaler, scaler_path)

        print(f"- 스케일러 적용된 데이터 저장 완료: {dst_dir}")
