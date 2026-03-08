from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.api.main import app, predictor, tmdb_client


def _movie_detail(movie_id: int, title: str) -> dict:
    return {
        "id": movie_id,
        "title": title,
        "original_title": title,
        "original_language": "ko",
        "overview": f"{title} overview",
        "release_date": "2019-05-30",
        "genres": [{"id": 18, "name": "Drama"}],
        "tagline": f"{title} tagline",
        "status": "Released",
        "homepage": "https://example.com",
        "poster_path": "/sample-poster.jpg",
        "budget": 10000000,
        "runtime": 120,
        "popularity": 10.0,
        "vote_count": 1000,
        "vote_average": 7.5,
    }


def _setup_mock_dependencies() -> None:
    tmdb_client.search_movie = lambda _: {"id": 1}
    tmdb_client.movie_detail = lambda movie_id: _movie_detail(
        movie_id, "기생충" if movie_id == 1 else ("추천영화A" if movie_id == 2 else "추천영화B")
    )
    tmdb_client.recommendations = lambda _movie_id, max_items: [{"id": 2}, {"id": 3}]
    predictor.predict_one = lambda _features: 8.8


def main() -> None:
    _setup_mock_dependencies()
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200, f"/health 실패: {health.status_code}"

    analyze_by_title = client.post(
        "/analyze",
        json={"title": "기생충", "top_k": 2, "user_history": [{"title": "살인의 추억", "rating": 9.0}]},
    )
    assert analyze_by_title.status_code == 200, f"/analyze 실패: {analyze_by_title.status_code}"

    analyze_by_id = client.post(
        "/analyze/id",
        json={"movie_id": 1, "top_k": 2, "user_history": [{"title": "살인의 추억", "rating": 9.0}]},
    )
    assert analyze_by_id.status_code == 200, f"/analyze/id 실패: {analyze_by_id.status_code}"

    payload = analyze_by_id.json()
    required_keys = {"query_movie_id", "movie", "recommendations"}
    missing = required_keys - set(payload.keys())
    assert not missing, f"/analyze/id 응답 키 누락: {missing}"

    print("로컬 API 스모크 테스트 성공")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
