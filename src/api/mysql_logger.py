from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

try:
    import pymysql
except ImportError:  # pragma: no cover - dependency missing at runtime
    pymysql = None

from src.api.schemas import MovieScore, RecommendationItem
from src.config import settings

logger = logging.getLogger(__name__)


class MySQLAnalyzeByIdLogger:
    """/analyze/id 응답을 MySQL(RDS)에 비차단으로 저장한다."""

    def __init__(self) -> None:
        self.host = settings.get_db_host().strip()
        self.port = settings.get_db_port()
        self.user = settings.get_db_user().strip()
        self.password = settings.get_db_password().strip()
        self.database = settings.get_db_name().strip()
        self.table_name = settings.mysql_analyze_id_table.strip()
        self.connect_timeout_seconds = settings.mysql_connect_timeout_seconds
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mysql-log")
        self._valid_table = self._sanitize_table_name(self.table_name)
        self.enabled = bool(
            pymysql is not None
            and self.host
            and self.user
            and self.password
            and self.database
            and self._valid_table
        )

        if pymysql is None:
            logger.warning("pymysql 미설치로 인해 MySQL 로깅이 비활성화됩니다.")
        if self.table_name and not self._valid_table:
            logger.warning("MySQL 테이블명 형식이 올바르지 않아 로깅이 비활성화됩니다: %s", self.table_name)

    @staticmethod
    def _sanitize_table_name(table_name: str) -> str:
        return table_name if re.fullmatch(r"[A-Za-z0-9_]+", table_name) else ""

    def log(
        self,
        *,
        query_movie_id: int,
        top_k: int,
        user_history_count: int,
        movie: MovieScore,
        recommendations: list[RecommendationItem],
    ) -> None:
        if not self.enabled:
            return

        payload = {
            "logged_at": datetime.now(timezone.utc),
            "query_movie_id": query_movie_id,
            "top_k": top_k,
            "user_history_count": user_history_count,
            "movie": movie.model_dump(mode="json"),
            "recommendations": [item.model_dump(mode="json") for item in recommendations],
        }
        self._executor.submit(self._insert_row, payload)

    def _insert_row(self, payload: dict) -> None:
        if pymysql is None or not self._valid_table:
            return

        query = (
            f"INSERT INTO `{self._valid_table}` "
            "(logged_at, query_movie_id, top_k, user_history_count, movie, recommendations) "
            "VALUES (%s, %s, %s, %s, %s, %s)"
        )
        try:
            connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset="utf8mb4",
                autocommit=True,
                connect_timeout=self.connect_timeout_seconds,
                read_timeout=self.connect_timeout_seconds,
                write_timeout=self.connect_timeout_seconds,
            )
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        query,
                        (
                            payload["logged_at"],
                            payload["query_movie_id"],
                            payload["top_k"],
                            payload["user_history_count"],
                            json.dumps(payload["movie"], ensure_ascii=False),
                            json.dumps(payload["recommendations"], ensure_ascii=False),
                        ),
                    )
        except Exception as exc:  # noqa: BLE001 - 로깅 실패는 서비스 흐름을 막지 않는다.
            logger.warning("MySQL analyze/id 로깅 실패: %s", exc)


mysql_analyze_by_id_logger = MySQLAnalyzeByIdLogger()
