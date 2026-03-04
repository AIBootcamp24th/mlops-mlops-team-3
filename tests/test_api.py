from fastapi.testclient import TestClient

from src.api.main import app, predictor, tmdb_client


client = TestClient(app)


def _movie_detail(movie_id: int, title: str) -> dict:
    return {
        "id": movie_id,
        "title": title,
        "original_language": "ko",
        "budget": 10000000,
        "runtime": 120,
        "popularity": 10.0,
        "vote_count": 1000,
        "vote_average": 7.5,
    }


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
    assert len(body["recommendations"]) == 2
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
