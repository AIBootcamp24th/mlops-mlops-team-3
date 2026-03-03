from __future__ import annotations

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    budget: float = Field(
        ge=0, description="영화 제작비(USD)", examples=[100000000, 50000000]
    )
    runtime: float = Field(gt=0, description="러닝타임(분)", examples=[120, 95])
    popularity: float = Field(ge=0, description="TMDB 인기도 점수", examples=[25.5, 12.1])
    vote_count: float = Field(ge=0, description="TMDB 투표 수", examples=[5000, 1300])


class PredictResponse(BaseModel):
    predicted_rating: float = Field(
        description="예측된 영화 평점(0~10 범위로 보정)", examples=[7.42]
    )


class BatchPredictRequest(BaseModel):
    items: list[PredictRequest] = Field(
        min_length=1, description="배치 예측 대상 목록(최소 1개)"
    )


class BatchPredictResponse(BaseModel):
    predictions: list[float] = Field(
        description="입력 순서와 동일한 예측 평점 목록(각 값은 0~10 범위로 보정)"
    )
