from __future__ import annotations

import time
from threading import Lock
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import settings
from src.constants import KOREAN_LANGUAGE_CODE


class TMDBClient:
    def __init__(self, api_key: str | None = None, language: str | None = None) -> None:
        self.api_key = api_key or settings.tmdb_api_key
        self.language = language or settings.tmdb_language
        self.base_url = "https://api.themoviedb.org/3"
        self._session = self._build_session()
        self._cache_ttl_seconds = 1200
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_lock = Lock()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=3,
            read=3,
            connect=3,
            backoff_factor=0.3,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _cache_get(self, key: str) -> Any | None:
        now = time.time()
        with self._cache_lock:
            item = self._cache.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at < now:
                self._cache.pop(key, None)
                return None
            return value

    def _cache_set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._cache_ttl_seconds
        with self._cache_lock:
            self._cache[key] = (time.time() + ttl, value)

    def _build_cache_key(self, path: str, params: dict[str, Any]) -> str:
        items = sorted((str(key), str(value)) for key, value in params.items())
        return f"{path}?{items}"

    def _get_json(self, path: str, params: dict[str, Any], ttl_seconds: int | None = None) -> dict[str, Any]:
        cache_key = self._build_cache_key(path, params)
        cached = self._cache_get(cache_key)
        if isinstance(cached, dict):
            return cached

        response = self._session.get(f"{self.base_url}{path}", params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        self._cache_set(cache_key, payload, ttl_seconds=ttl_seconds)
        return payload

    def search_movie(self, title: str) -> dict[str, Any]:
        self._ensure_api_key()
        data = self._get_json(
            "/search/movie",
            params={
                "api_key": self.api_key,
                "language": self.language,
                "query": title,
                "include_adult": "false",
            },
            ttl_seconds=300,
        )
        results = data.get("results", [])
        if not results:
            raise ValueError("영화 검색 결과가 없습니다.")

        korean_results = [item for item in results if item.get("original_language") == KOREAN_LANGUAGE_CODE]
        if not korean_results:
            raise ValueError("한국 영화 검색 결과가 없습니다.")
        return korean_results[0]

    def movie_detail(self, movie_id: int) -> dict[str, Any]:
        self._ensure_api_key()
        return self._get_json(
            f"/movie/{movie_id}",
            params={"api_key": self.api_key, "language": self.language},
        )

    def recommendations(self, movie_id: int, max_items: int = 20) -> list[dict[str, Any]]:
        self._ensure_api_key()
        data = self._get_json(
            f"/movie/{movie_id}/recommendations",
            params={"api_key": self.api_key, "language": self.language, "page": 1},
            ttl_seconds=1200,
        )
        items = data.get("results", [])
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

        data = self._get_json(
            "/discover/movie",
            params={
                "api_key": self.api_key,
                "language": self.language,
                "sort_by": "popularity.desc",
                "with_original_language": KOREAN_LANGUAGE_CODE,
                "with_genres": ",".join(str(genre_id) for genre_id in genre_ids),
                "page": 1,
            },
            ttl_seconds=1200,
        )
        items = data.get("results", [])
        filtered = [item for item in items if int(item.get("id", 0)) != exclude_movie_id]
        return filtered[:max_items]

    def _ensure_api_key(self) -> None:
        if not self.api_key:
            raise FileNotFoundError("TMDB_API_KEY가 설정되지 않아 영화 조회를 수행할 수 없습니다.")
