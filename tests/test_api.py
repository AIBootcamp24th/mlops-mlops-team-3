import pytest
from fastapi.testclient import TestClient

import src.api.main as api_main
from src.api.main import app, predictor, tmdb_client


client = TestClient(app)


def _movie_detail(movie_id: int, title: str) -> dict:
    return {
        "id": movie_id,
        "title": title,
        "original_language": "ko",
        "poster_path": "/sample-poster.jpg",
        "budget": 10000000,
        "runtime": 120,
        "popularity": 10.0,
        "vote_count": 1000,
        "vote_average": 7.5,
    }


@pytest.fixture(autouse=True)
def _mock_db_paths_and_async_logger(monkeypatch) -> None:
    """테스트가 로컬 DB 상태에 영향받지 않도록 DB 조회 경로를 기본 비활성화한다."""
    monkeypatch.setattr(api_main, "_resolve_db_movie_by_title", lambda _title: None)
    monkeypatch.setattr(api_main, "_resolve_db_movie_by_id", lambda _movie_id: None)
    monkeypatch.setattr(api_main, "_recommendations_from_db", lambda _base_movie_id, _limit: [])
    monkeypatch.setattr(api_main.mysql_analyze_by_id_logger, "log", lambda **_kwargs: None)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "model_loaded" in body


def test_analyze_by_title(monkeypatch) -> None:
    monkeypatch.setattr(tmdb_client, "search_movie", lambda _: {"id": 1})
    monkeypatch.setattr(
        tmdb_client,
        "movie_detail",
        lambda movie_id: _movie_detail(
            movie_id,
            "기생충" if movie_id == 1 else ("추천영화A" if movie_id == 2 else "추천영화B"),
        ),
    )
    monkeypatch.setattr(
        tmdb_client, "recommendations", lambda _movie_id, max_items: [{"id": 2}, {"id": 3}]
    )
    monkeypatch.setattr(
        predictor,
        "predict_one",
        lambda features: 8.8 if features[2] > 9 else 6.2,
    )

    response = client.post(
        "/analyze",
        json={"title": "기생충", "top_k": 2, "user_history": [{"title": "살인의 추억", "rating": 9.3}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["movie"]["title"] == "기생충"
    assert body["movie"]["poster_url"] == "https://image.tmdb.org/t/p/w500/sample-poster.jpg"
    assert len(body["recommendations"]) == 2
    assert body["recommendations"][0]["poster_url"] == "https://image.tmdb.org/t/p/w500/sample-poster.jpg"
    assert "personalization_score" in body["recommendations"][0]
    assert "final_score" in body["recommendations"][0]


def test_analyze_without_history(monkeypatch) -> None:
    monkeypatch.setattr(tmdb_client, "search_movie", lambda _: {"id": 1})
    monkeypatch.setattr(
        tmdb_client,
        "movie_detail",
        lambda movie_id: _movie_detail(movie_id, "기생충" if movie_id == 1 else "추천영화"),
    )
    monkeypatch.setattr(tmdb_client, "recommendations", lambda _movie_id, max_items: [{"id": 2}])
    monkeypatch.setattr(predictor, "predict_one", lambda _: 7.3)

    response = client.post("/analyze", json={"title": "기생충", "top_k": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["recommendations"][0]["personalization_score"] == 0.0


def test_analyze_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        tmdb_client,
        "search_movie",
        lambda _: (_ for _ in ()).throw(ValueError("영화 검색 결과가 없습니다.")),
    )
    response = client.post("/analyze", json={"title": "없는영화", "top_k": 1})
    assert response.status_code == 404


def test_analyze_model_not_loaded(monkeypatch) -> None:
    monkeypatch.setattr(tmdb_client, "search_movie", lambda _: {"id": 1})
    monkeypatch.setattr(tmdb_client, "movie_detail", lambda _: _movie_detail(1, "기생충"))
    monkeypatch.setattr(tmdb_client, "recommendations", lambda _movie_id, max_items: [])
    monkeypatch.setattr(
        predictor,
        "predict_one",
        lambda _features: (_ for _ in ()).throw(FileNotFoundError("모델 파일 없음")),
    )

    response = client.post("/analyze", json={"title": "기생충", "top_k": 1})
    assert response.status_code == 503


def test_analyze_by_id(monkeypatch) -> None:
    monkeypatch.setattr(tmdb_client, "search_movie", lambda _: {"id": 4})
    monkeypatch.setattr(
        tmdb_client,
        "movie_detail",
        lambda movie_id: _movie_detail(
            movie_id,
            (
                "기생충"
                if movie_id == 1
                else ("추천영화A" if movie_id == 2 else ("추천영화B" if movie_id == 3 else "살인의 추억"))
            ),
        ),
    )
    monkeypatch.setattr(
        tmdb_client, "recommendations", lambda _movie_id, max_items: [{"id": 2}, {"id": 3}]
    )
    monkeypatch.setattr(
        predictor,
        "predict_one",
        lambda features: 8.8 if features[2] > 9 else 6.2,
    )

    response = client.post(
        "/analyze/id",
        json={"movie_id": 1, "top_k": 2, "user_history": [{"title": "살인의 추억", "rating": 9.3}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["query_title"] == "1"
    assert body["movie"]["movie_id"] == 1
    assert len(body["recommendations"]) == 2


def test_analyze_by_id_not_found(monkeypatch) -> None:
    import requests

    def _raise_not_found(_movie_id: int):
        response = requests.Response()
        response.status_code = 404
        raise requests.HTTPError("Not Found", response=response)

    monkeypatch.setattr(tmdb_client, "movie_detail", _raise_not_found)

    response = client.post("/analyze/id", json={"movie_id": 999999, "top_k": 1})
    assert response.status_code == 404
