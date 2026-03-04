from __future__ import annotations

from typing import Any

import requests

from src.config import settings
from src.constants import KOREAN_LANGUAGE_CODE


class TMDBClient:
    def __init__(self, api_key: str | None = None, language: str | None = None) -> None:
        self.api_key = api_key or settings.tmdb_api_key
        self.language = language or settings.tmdb_language
        self.base_url = "https://api.themoviedb.org/3"

    def search_movie(self, title: str) -> dict[str, Any]:
        self._ensure_api_key()
        response = requests.get(
            f"{self.base_url}/search/movie",
            params={
                "api_key": self.api_key,
                "language": self.language,
                "query": title,
                "include_adult": "false",
            },
            timeout=20,
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results:
            raise ValueError("영화 검색 결과가 없습니다.")

        korean_results = [item for item in results if item.get("original_language") == KOREAN_LANGUAGE_CODE]
        return korean_results[0] if korean_results else results[0]

    def movie_detail(self, movie_id: int) -> dict[str, Any]:
        self._ensure_api_key()
        response = requests.get(
            f"{self.base_url}/movie/{movie_id}",
            params={"api_key": self.api_key, "language": self.language},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def recommendations(self, movie_id: int, max_items: int = 20) -> list[dict[str, Any]]:
        self._ensure_api_key()
        response = requests.get(
            f"{self.base_url}/movie/{movie_id}/recommendations",
            params={"api_key": self.api_key, "language": self.language, "page": 1},
            timeout=20,
        )
        response.raise_for_status()
        items = response.json().get("results", [])
        korean_items = [item for item in items if item.get("original_language") == KOREAN_LANGUAGE_CODE]
        return korean_items[:max_items]

    def discover_korean_by_genres(
        self,
        genre_ids: list[int],
        exclude_movie_id: int,
        max_items: int = 20,
    ) -> list[dict[str, Any]]:
        self._ensure_api_key()
        if not genre_ids:
            return []

        response = requests.get(
            f"{self.base_url}/discover/movie",
            params={
                "api_key": self.api_key,
                "language": self.language,
                "sort_by": "popularity.desc",
                "with_original_language": KOREAN_LANGUAGE_CODE,
                "with_genres": ",".join(str(genre_id) for genre_id in genre_ids),
                "page": 1,
            },
            timeout=20,
        )
        response.raise_for_status()
        items = response.json().get("results", [])
        filtered = [item for item in items if int(item.get("id", 0)) != exclude_movie_id]
        return filtered[:max_items]

    def _ensure_api_key(self) -> None:
        if not self.api_key:
            raise FileNotFoundError("TMDB_API_KEY가 설정되지 않아 영화 조회를 수행할 수 없습니다.")
