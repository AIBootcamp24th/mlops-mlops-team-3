from __future__ import annotations

from pydantic import BaseModel, Field


class MovieTitleRequest(BaseModel):
    title: str = Field(..., min_length=1, examples=["기생충"])


class UserHistoryItem(BaseModel):
    title: str = Field(..., min_length=1, examples=["살인의 추억"])
    rating: float = Field(..., ge=0.0, le=10.0, examples=[9.0])


class AnalyzeRequest(MovieTitleRequest):
    top_k: int = Field(default=5, ge=1, le=10)
    user_history: list[UserHistoryItem] = Field(default_factory=list)


class MovieScore(BaseModel):
    movie_id: int
    title: str
    original_language: str
    budget: float
    runtime: float
    popularity: float
    vote_count: float
    tmdb_vote_average: float
    predicted_rating: float


class PredictByTitleResponse(BaseModel):
    query_title: str
    movie: MovieScore


class RecommendationItem(BaseModel):
    movie_id: int
    title: str
    tmdb_vote_average: float
    predicted_rating: float
    personalization_score: float
    final_score: float


class AnalyzeByTitleResponse(BaseModel):
    query_title: str
    movie: MovieScore
    recommendations: list[RecommendationItem]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
