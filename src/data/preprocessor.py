import os
import random

import numpy as np
import pandas as pd


class DataPreprocessor:
    def __init__(self, movies_df, user_count=100, max_selected_count=20):
        random.seed(42)
        np.random.seed(42)
        self._movies = movies_df.to_dict("records")
        self._users = list(range(1, user_count + 1))
        self._max_selected_movies = max_selected_count
        self._max_runtime_seconds = 120 * 60
        self._features = pd.DataFrame()

    def _generate_watch_second(self, rating):
        base = 1.1
        base_time = (
            self._max_runtime_seconds * (base ** (rating - 5) - base**-5) / (base**5 - base**-5)
        )
        noise = np.random.normal(0, 0.1 * base_time)
        return int(np.clip(base_time + noise, 0, self._max_runtime_seconds))

    def run(self):
        all_logs = []
        for user_id in self._users:
            select_count = random.randint(1, self._max_selected_movies)
            selected_movies = random.sample(self._movies, k=min(select_count, len(self._movies)))
            for movie in selected_movies:
                all_logs.append(
                    {
                        "user_id": str(user_id),
                        "movie_id": str(movie["id"]),
                        "watch_second": self._generate_watch_second(movie["vote_average"]),
                        "rating": movie["vote_average"],
                        "popularity": movie["popularity"],
                    }
                )
        self._features = pd.DataFrame(all_logs)

    def save(self, dst_dir="./src/data/processed", filename="watch_log.csv"):
        os.makedirs(dst_dir, exist_ok=True)
        path = os.path.join(dst_dir, f"{filename}.csv")
        self._features.to_csv(path, index=False)
        print(f"시청 로그 저장: [저장 경로 '{path}']")
