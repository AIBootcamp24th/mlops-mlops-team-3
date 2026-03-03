from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from src.api.dependencies import get_feature_cols_dep, get_model_dep
from src.api.schemas.predict import (
    BatchPredictRequest,
    BatchPredictResponse,
    PredictRequest,
    PredictResponse,
)
from src.api.services.inference import predict_many, predict_one

router = APIRouter(prefix="/predict", tags=["predict"])


@router.post(
    "",
    response_model=PredictResponse,
    summary="단건 평점 예측",
    description=(
        "단일 영화 메타데이터를 입력받아 예측 평점을 반환합니다.\n\n"
        "사용 순서:\n"
        "1) `budget`, `runtime`, `popularity`, `vote_count` 값을 입력합니다.\n"
        "2) `Execute`를 누릅니다.\n"
        "3) `predicted_rating` 값을 확인합니다."
    ),
    responses={
        200: {"description": "예측 성공"},
        422: {"description": "요청 데이터 검증 실패"},
        503: {"description": "모델 로드 실패(환경변수 또는 S3 접근 설정 확인 필요)"},
    },
)
def predict(
    payload: PredictRequest = Body(
        ...,
        examples=[
            {
                "budget": 100000000,
                "runtime": 120,
                "popularity": 25.5,
                "vote_count": 5000,
            }
        ],
    ),
    model=Depends(get_model_dep),
    feature_cols: list[str] = Depends(get_feature_cols_dep),
) -> PredictResponse:
    return PredictResponse(predicted_rating=predict_one(model, feature_cols, payload))


@router.post(
    "/batch",
    response_model=BatchPredictResponse,
    summary="배치 평점 예측",
    description=(
        "여러 영화 메타데이터를 한 번에 입력받아 예측 평점 목록을 반환합니다.\n\n"
        "사용 순서:\n"
        "1) `items` 배열에 영화 정보를 추가합니다.\n"
        "2) `Execute`를 누릅니다.\n"
        "3) `predictions` 배열을 확인합니다(입력 순서와 동일)."
    ),
    responses={
        200: {"description": "배치 예측 성공"},
        422: {"description": "요청 데이터 검증 실패"},
        503: {"description": "모델 로드 실패(환경변수 또는 S3 접근 설정 확인 필요)"},
    },
)
def predict_batch(
    payload: BatchPredictRequest = Body(
        ...,
        examples=[
            {
                "items": [
                    {
                        "budget": 100000000,
                        "runtime": 120,
                        "popularity": 25.5,
                        "vote_count": 5000,
                    },
                    {
                        "budget": 50000000,
                        "runtime": 95,
                        "popularity": 12.1,
                        "vote_count": 1300,
                    },
                ]
            }
        ],
    ),
    model=Depends(get_model_dep),
    feature_cols: list[str] = Depends(get_feature_cols_dep),
) -> BatchPredictResponse:
    return BatchPredictResponse(predictions=predict_many(model, feature_cols, payload.items))
