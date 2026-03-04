from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RatedMovie:
    title: str
    budget: float
    runtime: float
    popularity: float
    vote_count: float
    rating: float


@dataclass
class CandidateMovie:
    movie_id: int
    title: str
    budget: float
    runtime: float
    popularity: float
    vote_count: float
    predicted_rating: float


def build_preference_vector(user_history: list[RatedMovie]) -> list[float]:
    total_weight = sum(max(entry.rating, 0.0) for entry in user_history)
    if total_weight == 0:
        total_weight = float(len(user_history))

    feature_sum = [0.0, 0.0, 0.0, 0.0]
    for entry in user_history:
        weight = max(entry.rating, 0.0) or 1.0
        feature_sum[0] += entry.budget * weight
        feature_sum[1] += entry.runtime * weight
        feature_sum[2] += entry.popularity * weight
        feature_sum[3] += entry.vote_count * weight

    return [value / total_weight for value in feature_sum]


def personalization_score(movie: CandidateMovie, pref_vector: list[float]) -> float:
    return cosine_similarity(
        [movie.budget, movie.runtime, movie.popularity, movie.vote_count], pref_vector
    )


def compute_final_score(
    predicted_rating: float,
    personalization: float,
    personalization_weight: float = 2.0,
) -> float:
    # 예측 평점을 기본으로 하고 개인화 유사도를 가산한다.
    return predicted_rating + personalization * personalization_weight


def cosine_similarity(left: list[float], right: list[float]) -> float:
    left_norm = sum(v * v for v in left) ** 0.5
    right_norm = sum(v * v for v in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0

    dot = sum(left_value * right_value for left_value, right_value in zip(left, right))
    return dot / (left_norm * right_norm)
