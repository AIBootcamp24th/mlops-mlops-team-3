from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import asyncio

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.api.mysql_logger import mysql_analyze_by_id_logger
from src.api.schemas import (
    AnalyzeByIdRequest,
    AnalyzeByTitleResponse,
    AnalyzeRequest,
    HealthResponse,
    MovieScore,
    RecommendationItem,
    UserHistoryItem,
)
from src.api.tmdb_client import TMDBClient
from src.constants import FEATURE_COLS
from src.config import settings
from src.data.database import engine
from src.infer.predictor import ModelPredictor
from src.reco.personalized import (
    CandidateMovie,
    RatedMovie,
    build_preference_vector,
    compute_final_score,
    personalization_score,
)

logger = logging.getLogger(__name__)
predictor = ModelPredictor(feature_cols=FEATURE_COLS)
tmdb_client = TMDBClient()


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        predictor.load()
    except (FileNotFoundError, Exception) as exc:
        # 모델이 아직 준비되지 않았거나 AWS 자격증명이 없는 환경에서도 API 자체는 기동 가능하게 둔다.
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"모델 로딩 실패 (API는 계속 실행됩니다): {type(exc).__name__}: {exc}")
    
    # Background task for CD (Hot-reloading)
    async def model_reloader():
        while True:
            await asyncio.sleep(600)  # 10분마다 체크
            try:
                if predictor.check_and_reload():
                    import logging
                    logging.getLogger(__name__).info("Model reloaded via Hot-reloading")
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error in model reloader: {e}")

    reloader_task = asyncio.create_task(model_reloader())
    
    yield
    reloader_task.cancel()


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


def _parse_cors_origins(raw: str) -> list[str]:
    if not raw.strip():
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(settings.api_cors_allow_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
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


def _resolve_movie_by_id(movie_id: int) -> dict:
    return tmdb_client.movie_detail(movie_id)


def _resolve_db_movie_by_title(title: str) -> dict | None:
    sql = text(
        """
        SELECT
            tmdb_id, title, original_title, overview, release_date,
            budget, runtime, vote_average, vote_count, popularity, original_language, poster_path
        FROM movies_raw
        WHERE (title = :title OR original_title = :title) AND original_language = 'ko'
        ORDER BY popularity DESC, vote_count DESC
        LIMIT 1
        """
    )
    try:
        with engine.connect() as conn:
            row = conn.execute(sql, {"title": title}).mappings().first()
    except Exception as exc:
        logger.warning(
            "DB 조회 실패 (제목: %s), TMDB fallback으로 전환: %s",
            title,
            exc,
            exc_info=True,
        )
        return None

    if not row:
        return None

    return {
        "id": int(row["tmdb_id"]),
        "title": row["title"] or "",
        "original_title": row["original_title"] or row["title"] or "",
        "overview": row["overview"] or "",
        "release_date": str(row["release_date"]) if row["release_date"] else "",
        "budget": float(row["budget"] or 0.0),
        "runtime": float(row["runtime"] or 0.0),
        "vote_average": float(row["vote_average"] or 0.0),
        "vote_count": float(row["vote_count"] or 0.0),
        "popularity": float(row["popularity"] or 0.0),
        "original_language": row["original_language"] or "ko",
        "poster_path": row["poster_path"],
        "genres": [],
    }


def _resolve_db_movie_by_id(movie_id: int) -> dict | None:
    sql = text(
        """
        SELECT
            tmdb_id, title, original_title, overview, release_date,
            budget, runtime, vote_average, vote_count, popularity, original_language, poster_path
        FROM movies_raw
        WHERE tmdb_id = :movie_id AND original_language = 'ko'
        LIMIT 1
        """
    )
    try:
        with engine.connect() as conn:
            row = conn.execute(sql, {"movie_id": movie_id}).mappings().first()
    except Exception as exc:
        logger.warning(
            "DB 조회 실패 (movie_id: %s), TMDB fallback으로 전환: %s",
            movie_id,
            exc,
            exc_info=True,
        )
        return None

    if not row:
        return None

    return {
        "id": int(row["tmdb_id"]),
        "title": row["title"] or "",
        "original_title": row["original_title"] or row["title"] or "",
        "overview": row["overview"] or "",
        "release_date": str(row["release_date"]) if row["release_date"] else "",
        "budget": float(row["budget"] or 0.0),
        "runtime": float(row["runtime"] or 0.0),
        "vote_average": float(row["vote_average"] or 0.0),
        "vote_count": float(row["vote_count"] or 0.0),
        "popularity": float(row["popularity"] or 0.0),
        "original_language": row["original_language"] or "ko",
        "poster_path": row["poster_path"],
        "genres": [],
    }


def _recommendations_from_db(base_movie_id: int, limit: int) -> list[dict]:
    sql = text(
        """
        SELECT
            tmdb_id, title, original_title, budget, runtime,
            vote_average, vote_count, popularity, original_language, poster_path
        FROM movies_raw
        WHERE tmdb_id != :base_movie_id AND original_language = 'ko'
        ORDER BY popularity DESC, vote_count DESC
        LIMIT :limit
        """
    )
    try:
        with engine.connect() as conn:
            rows = conn.execute(sql, {"base_movie_id": base_movie_id, "limit": limit}).mappings().all()
    except Exception as exc:
        logger.warning(
            "DB 추천 조회 실패 (base_movie_id: %s, limit: %s), 빈 리스트 반환 및 TMDB fallback: %s",
            base_movie_id,
            limit,
            exc,
            exc_info=True,
        )
        return []

    return [
        {
            "id": int(row["tmdb_id"]),
            "title": row["title"] or "",
            "original_title": row["original_title"] or row["title"] or "",
            "budget": float(row["budget"] or 0.0),
            "runtime": float(row["runtime"] or 0.0),
            "vote_average": float(row["vote_average"] or 0.0),
            "vote_count": float(row["vote_count"] or 0.0),
            "popularity": float(row["popularity"] or 0.0),
            "original_language": row["original_language"] or "ko",
            "poster_path": row["poster_path"],
        }
        for row in rows
    ]


def _build_user_history(items: list[UserHistoryItem]) -> list[RatedMovie]:
    history: list[RatedMovie] = []
    resolved_by_title: dict[str, dict] = {}
    for item in items:
        movie = resolved_by_title.get(item.title)
        if movie is None:
            movie = _resolve_movie_by_title(item.title)
            resolved_by_title[item.title] = movie
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


@app.get("/health", response_model=HealthResponse, summary="헬스체크", tags=["헬스체크"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", model_loaded=predictor.model_loaded)


@app.post(
    "/analyze",
    response_model=AnalyzeByTitleResponse,
    summary="영화 제목으로 평점 예측 + 추천 통합",
    tags=["Movie"],
)
def analyze_by_title(payload: AnalyzeRequest) -> AnalyzeByTitleResponse:
    base_movie = _resolve_db_movie_by_title(payload.title)
    if base_movie is None:
        try:
            base_movie = _resolve_movie_by_title(payload.title)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"TMDB 요청 실패: {exc}") from exc

    result = _analyze_with_base_movie(
        base_movie=base_movie,
        query_value=payload.title,
        top_k=payload.top_k,
        user_history_items=payload.user_history,
    )
    mysql_analyze_by_id_logger.log(
        query_movie_id=int(base_movie["id"]),
        top_k=payload.top_k,
        user_history_count=len(payload.user_history),
        movie=result.movie,
        recommendations=result.recommendations,
    )
    return result


@app.post(
    "/analyze/id",
    response_model=AnalyzeByTitleResponse,
    summary="영화 ID로 평점 예측 + 추천 통합",
    tags=["Movie"],
)
def analyze_by_id(payload: AnalyzeByIdRequest) -> AnalyzeByTitleResponse:
    base_movie = _resolve_db_movie_by_id(payload.movie_id)
    if base_movie is None:
        try:
            base_movie = _resolve_movie_by_id(payload.movie_id)
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else 502
            if status_code == 404:
                raise HTTPException(status_code=404, detail="해당 movie_id를 찾을 수 없습니다.") from exc
            raise HTTPException(status_code=502, detail=f"TMDB 요청 실패: {exc}") from exc
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"TMDB 요청 실패: {exc}") from exc

    result = _analyze_with_base_movie(
        base_movie=base_movie,
        query_value=str(payload.movie_id),
        top_k=payload.top_k,
        user_history_items=payload.user_history,
    )
    mysql_analyze_by_id_logger.log(
        query_movie_id=payload.movie_id,
        top_k=payload.top_k,
        user_history_count=len(payload.user_history),
        movie=result.movie,
        recommendations=result.recommendations,
    )
    return result


def _analyze_with_base_movie(
    *,
    base_movie: dict,
    query_value: str,
    top_k: int,
    user_history_items: list[UserHistoryItem],
) -> AnalyzeByTitleResponse:
    db_candidates = _recommendations_from_db(int(base_movie["id"]), max(10, top_k * 3))
    try:
        recommended = db_candidates
        if not recommended:
            recommended = tmdb_client.recommendations(int(base_movie["id"]), max_items=max(10, top_k * 3))
        if not recommended:
            genre_ids = [int(genre["id"]) for genre in base_movie.get("genres", []) if "id" in genre]
            recommended = tmdb_client.discover_korean_by_genres(
                genre_ids=genre_ids,
                exclude_movie_id=int(base_movie["id"]),
                max_items=max(10, top_k * 3),
            )
        user_history = _build_user_history(user_history_items)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"TMDB 요청 실패: {exc}") from exc

    preference = build_preference_vector(user_history) if user_history else None
    scored_candidates: list[RecommendationItem] = []
    recommended_ids = [int(item["id"]) for item in recommended]
    detail_by_id: dict[int, dict] = {}
    if db_candidates:
        detail_by_id = {int(item["id"]): item for item in recommended}
    else:
        with ThreadPoolExecutor(max_workers=min(6, max(1, len(recommended_ids)))) as executor:
            details = executor.map(tmdb_client.movie_detail, recommended_ids)
            for detail in details:
                detail_by_id[int(detail["id"])] = detail

    for movie_id in recommended_ids:
        detail = detail_by_id[movie_id]
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

    ranked = sorted(scored_candidates, key=lambda item: item.final_score, reverse=True)[:top_k]
    return AnalyzeByTitleResponse(
        query_title=query_value,
        movie=_to_movie_score(base_movie),
        recommendations=ranked,
    )


@app.exception_handler(FileNotFoundError)
def model_not_found_handler(_, exc: FileNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})
