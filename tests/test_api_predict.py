from __future__ import annotations

import torch
from fastapi.testclient import TestClient

from src.api.dependencies import get_feature_cols_dep, get_model_dep
from src.api.main import app


class DummyModel(torch.nn.Module):
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x.sum(dim=1, keepdim=True)


def _override_model():
    return DummyModel()


def _override_feature_cols() -> list[str]:
    return ["budget", "runtime", "popularity", "vote_count"]


def test_health_and_predict() -> None:
    app.dependency_overrides[get_model_dep] = _override_model
    app.dependency_overrides[get_feature_cols_dep] = _override_feature_cols

    client = TestClient(app)

    health_res = client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "ok"

    predict_res = client.post(
        "/predict",
        json={"budget": 100.0, "runtime": 120.0, "popularity": 25.5, "vote_count": 10.0},
    )
    assert predict_res.status_code == 200
    predicted_rating = predict_res.json()["predicted_rating"]
    assert 0.0 <= predicted_rating <= 10.0

    batch_res = client.post(
        "/predict/batch",
        json={
            "items": [
                {"budget": 100.0, "runtime": 120.0, "popularity": 25.5, "vote_count": 10.0},
                {"budget": 90.0, "runtime": 110.0, "popularity": 20.0, "vote_count": 8.0},
            ]
        },
    )
    assert batch_res.status_code == 200
    predictions = batch_res.json()["predictions"]
    assert len(predictions) == 2
    assert all(0.0 <= value <= 10.0 for value in predictions)

    app.dependency_overrides.clear()
