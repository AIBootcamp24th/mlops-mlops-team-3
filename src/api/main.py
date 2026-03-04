from __future__ import annotations

from contextlib import asynccontextmanager

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from src.api.schemas import (
    AnalyzeByTitleResponse,
    AnalyzeRequest,
    HealthResponse,
    MovieScore,
    RecommendationItem,
    UserHistoryItem,
)
from src.api.tmdb_client import TMDBClient
from src.constants import FEATURE_COLS
from src.infer.predictor import ModelPredictor
from src.reco.personalized import (
    CandidateMovie,
    RatedMovie,
    build_preference_vector,
    compute_final_score,
    personalization_score,
)

predictor = ModelPredictor(feature_cols=FEATURE_COLS)
tmdb_client = TMDBClient()


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        predictor.load()
    except FileNotFoundError:
        # 모델이 아직 준비되지 않은 환경에서도 API 자체는 기동 가능하게 둔다.
        pass
    yield


app = FastAPI(
    title="TMDB /analyze 통합 API",
    description=(
        "영화 제목을 입력하면 메타데이터를 조회해 평점을 예측하고, "
        "해당 영화와 유사한 한국 영화 추천 목록을 함께 반환합니다."
    ),
    version="3.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "헬스체크"
        },
        {
            "name": "Movie"
        },
    ],
)


def _extract_features(movie: dict) -> list[float]:
    return [
        float(movie.get("budget") or 0.0),
        float(movie.get("runtime") or 0.0),
        float(movie.get("popularity") or 0.0),
        float(movie.get("vote_count") or 0.0),
    ]


def _predict_rating(movie: dict) -> float:
    return round(predictor.predict_one(_extract_features(movie)), 4)


def _poster_url(poster_path: str | None) -> str | None:
    if not poster_path:
        return None
    return f"https://image.tmdb.org/t/p/w500{poster_path}"


def _to_movie_score(movie: dict) -> MovieScore:
    poster_path = movie.get("poster_path")
    return MovieScore(
        movie_id=int(movie["id"]),
        title=str(movie.get("title") or ""),
        original_language=str(movie.get("original_language") or ""),
        poster_path=str(poster_path) if poster_path else None,
        poster_url=_poster_url(str(poster_path)) if poster_path else None,
        budget=float(movie.get("budget") or 0.0),
        runtime=float(movie.get("runtime") or 0.0),
        popularity=float(movie.get("popularity") or 0.0),
        vote_count=float(movie.get("vote_count") or 0.0),
        tmdb_vote_average=float(movie.get("vote_average") or 0.0),
        predicted_rating=_predict_rating(movie),
    )


def _resolve_movie_by_title(title: str) -> dict:
    searched = tmdb_client.search_movie(title)
    return tmdb_client.movie_detail(int(searched["id"]))


def _build_user_history(items: list[UserHistoryItem]) -> list[RatedMovie]:
    history: list[RatedMovie] = []
    for item in items:
        movie = _resolve_movie_by_title(item.title)
        history.append(
            RatedMovie(
                title=str(movie.get("title") or item.title),
                budget=float(movie.get("budget") or 0.0),
                runtime=float(movie.get("runtime") or 0.0),
                popularity=float(movie.get("popularity") or 0.0),
                vote_count=float(movie.get("vote_count") or 0.0),
                rating=float(item.rating),
            )
        )
    return history


@app.get("/health", response_model=HealthResponse, summary="헬스체크", tags=["System"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", model_loaded=predictor.model_loaded)


@app.post(
    "/analyze",
    response_model=AnalyzeByTitleResponse,
    summary="영화 제목으로 평점 예측 + 추천 통합",
    tags=["Movie Analysis"],
)
def analyze_by_title(payload: AnalyzeRequest) -> AnalyzeByTitleResponse:
    try:
        base_movie = _resolve_movie_by_title(payload.title)
        recommended = tmdb_client.recommendations(int(base_movie["id"]), max_items=max(10, payload.top_k * 3))
        if not recommended:
            genre_ids = [int(genre["id"]) for genre in base_movie.get("genres", []) if "id" in genre]
            recommended = tmdb_client.discover_korean_by_genres(
                genre_ids=genre_ids,
                exclude_movie_id=int(base_movie["id"]),
                max_items=max(10, payload.top_k * 3),
            )
        user_history = _build_user_history(payload.user_history)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"TMDB 요청 실패: {exc}") from exc

    preference = build_preference_vector(user_history) if user_history else None
    scored_candidates: list[RecommendationItem] = []
    for item in recommended:
        detail = tmdb_client.movie_detail(int(item["id"]))
        candidate = CandidateMovie(
            movie_id=int(detail["id"]),
            title=str(detail.get("title") or ""),
            budget=float(detail.get("budget") or 0.0),
            runtime=float(detail.get("runtime") or 0.0),
            popularity=float(detail.get("popularity") or 0.0),
            vote_count=float(detail.get("vote_count") or 0.0),
            predicted_rating=_predict_rating(detail),
        )
        personalization = personalization_score(candidate, preference) if preference else 0.0
        final_score = compute_final_score(candidate.predicted_rating, personalization)
        scored_candidates.append(
            RecommendationItem(
                movie_id=candidate.movie_id,
                title=candidate.title,
                poster_path=str(detail.get("poster_path")) if detail.get("poster_path") else None,
                poster_url=_poster_url(str(detail.get("poster_path")))
                if detail.get("poster_path")
                else None,
                tmdb_vote_average=float(detail.get("vote_average") or 0.0),
                predicted_rating=round(candidate.predicted_rating, 4),
                personalization_score=round(personalization, 4),
                final_score=round(final_score, 4),
            )
        )

    ranked = sorted(scored_candidates, key=lambda item: item.final_score, reverse=True)[: payload.top_k]
    return AnalyzeByTitleResponse(
        query_title=payload.title,
        movie=_to_movie_score(base_movie),
        recommendations=ranked,
    )


@app.exception_handler(FileNotFoundError)
def model_not_found_handler(_, exc: FileNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})
