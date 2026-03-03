from __future__ import annotations

from fastapi import FastAPI

from src.api.routers.health import router as health_router
from src.api.routers.predict import router as predict_router

openapi_tags = [
    {
        "name": "health",
        "description": "서버 상태 확인용 API입니다.",
    },
    {
        "name": "predict",
        "description": (
            "영화 메타데이터 기반 평점 예측 API입니다. "
            "`/predict`는 단건, `/predict/batch`는 배치 예측을 제공합니다."
        ),
    },
]

app = FastAPI(
    title="TMDB Rating Prediction API",
    version="0.1.0",
    description=(
        "영화 평점을 예측하는 API입니다."
    ),
    openapi_tags=openapi_tags,
)

app.include_router(health_router)
app.include_router(predict_router)
