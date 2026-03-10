import os
import socket

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    aws_region: str = Field(default="ap-northeast-2", alias="AWS_REGION")
    aws_access_key_id: str = Field(default="", alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="", alias="AWS_SECRET_ACCESS_KEY")
    aws_s3_raw_bucket: str = Field(default="", alias="AWS_S3_RAW_BUCKET")
    aws_s3_model_bucket: str = Field(default="", alias="AWS_S3_MODEL_BUCKET")
    aws_s3_pred_bucket: str = Field(default="", alias="AWS_S3_PRED_BUCKET")
    train_queue_url: str = Field(default="", alias="TRAIN_QUEUE_URL")
    infer_queue_url: str = Field(default="", alias="INFER_QUEUE_URL")
    train_seed: int = Field(default=42, alias="TRAIN_SEED")

    wandb_api_key: str = Field(default="", alias="WANDB_API_KEY")
    wandb_project: str = Field(default="tmdb-rating-mlops", alias="WANDB_PROJECT")
    wandb_entity: str = Field(default="", alias="WANDB_ENTITY")
    quality_gate_val_rmse_max: float = Field(default=1.2, alias="QUALITY_GATE_VAL_RMSE_MAX")
    quality_gate_out_of_range_max: float = Field(
        default=0.05, alias="QUALITY_GATE_OUT_OF_RANGE_MAX"
    )

    slack_bot_token: str = Field(default="", alias="SLACK_BOT_TOKEN")
    slack_channel_id: str = Field(default="", alias="SLACK_CHANNEL_ID")

    api_model_s3_key: str = Field(default="", alias="API_MODEL_S3_KEY")
    api_model_registry_key: str = Field(
        default="models/registry/champion.json", alias="API_MODEL_REGISTRY_KEY"
    )
    api_model_local_path: str = Field(
        default="artifacts/rating_model.pt", alias="API_MODEL_LOCAL_PATH"
    )
    tmdb_api_key: str = Field(default="", alias="TMDB_API_KEY")
    tmdb_language: str = Field(default="ko-KR", alias="TMDB_LANGUAGE")
    api_cors_allow_origins: str = Field(default="*", alias="API_CORS_ALLOW_ORIGINS")

    # Database connection variables (RDS/Aurora 우선 전략)
    # 우선순위: DB_* (RDS/Aurora 엔드포인트) > MYSQL_* (레거시/로컬 MySQL) > 기본값
    # 운영 환경에서는 Terraform output의 DB_HOST(예: RDS/Aurora 엔드포인트)를 사용
    db_user: str = Field(default="", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")
    db_host: str = Field(default="", alias="DB_HOST")
    db_port: int = Field(default=3306, alias="DB_PORT")
    db_name: str = Field(default="", alias="DB_NAME")
    db_auto_failover: bool = Field(default=True, alias="DB_AUTO_FAILOVER")
    db_fallback_hosts: str = Field(
        default="db,localhost,127.0.0.1,host.docker.internal",
        alias="DB_FALLBACK_HOSTS",
    )
    db_probe_timeout_seconds: float = Field(default=0.6, alias="DB_PROBE_TIMEOUT_SECONDS")
    secondary_db_host: str = Field(default="", alias="SECONDARY_DB_HOST")
    secondary_db_port: int = Field(default=3306, alias="SECONDARY_DB_PORT")

    # MySQL 호환 변수 (레거시 지원 및 로컬 개발용 fallback)
    # 운영 환경에서는 DB_* 변수를 우선 사용하고, 개발/테스트 환경에서만 MYSQL_* 사용
    mysql_host: str = Field(default="", alias="MYSQL_HOST")
    mysql_port: int = Field(default=3306, alias="MYSQL_PORT")
    mysql_user: str = Field(default="", alias="MYSQL_USER")
    mysql_password: str = Field(default="", alias="MYSQL_PASSWORD")
    mysql_database: str = Field(default="", alias="MYSQL_DATABASE")
    mysql_analyze_id_table: str = Field(
        default="analyze_id_prediction_logs",
        alias="MYSQL_ANALYZE_ID_TABLE",
    )
    mysql_connect_timeout_seconds: int = Field(default=2, alias="MYSQL_CONNECT_TIMEOUT_SECONDS")

    def get_db_host(self) -> str:
        """Get reachable DB host with priority and failover support."""
        primary_host = self.db_host or self.mysql_host
        if not self.db_auto_failover:
            return primary_host or "localhost"

        port = self.get_db_port()
        candidates: list[str] = []
        if primary_host:
            candidates.append(primary_host)

        for host in self.db_fallback_hosts.split(","):
            normalized = host.strip()
            if normalized and normalized not in candidates:
                candidates.append(normalized)

        if not candidates:
            return "localhost"

        for host in candidates:
            if self._is_host_reachable(host, port):
                return host

        return candidates[0]

    def get_db_port(self) -> int:
        """Get database port with priority: DB_PORT (RDS/Aurora) > MYSQL_PORT (로컬/레거시) > 3306."""
        return self.db_port if self.db_port != 3306 or not self.mysql_port else self.mysql_port

    def get_db_user(self) -> str:
        """Get database user with priority: DB_USER (RDS/Aurora) > MYSQL_USER (로컬/레거시).
        
        운영 환경에서는 반드시 환경변수로 설정해야 합니다.
        """
        user = self.db_user or self.mysql_user
        if not user:
            import warnings
            warnings.warn(
                "DB_USER 또는 MYSQL_USER 환경변수가 설정되지 않았습니다. "
                "운영 환경에서는 반드시 설정해야 합니다.",
                UserWarning,
                stacklevel=2,
            )
            # 개발 환경 호환성을 위해 임시 기본값 사용 (운영 환경에서는 설정 필수)
            return "mlops"
        return user

    def get_db_password(self) -> str:
        """Get database password with priority: DB_PASSWORD (RDS/Aurora) > MYSQL_PASSWORD (로컬/레거시).
        
        운영 환경에서는 반드시 환경변수로 설정해야 합니다.
        """
        password = self.db_password or self.mysql_password
        if not password:
            import warnings
            warnings.warn(
                "DB_PASSWORD 또는 MYSQL_PASSWORD 환경변수가 설정되지 않았습니다. "
                "운영 환경에서는 반드시 설정해야 합니다.",
                UserWarning,
                stacklevel=2,
            )
            # 개발 환경 호환성을 위해 임시 기본값 사용 (운영 환경에서는 설정 필수)
            return "mlops1234"
        return password

    def get_db_name(self) -> str:
        """Get database name with priority: DB_NAME (RDS/Aurora) > MYSQL_DATABASE (로컬/레거시).
        
        운영 환경에서는 반드시 환경변수로 설정해야 합니다.
        """
        db_name = self.db_name or self.mysql_database
        if not db_name:
            import warnings
            warnings.warn(
                "DB_NAME 또는 MYSQL_DATABASE 환경변수가 설정되지 않았습니다. "
                "운영 환경에서는 반드시 설정해야 합니다.",
                UserWarning,
                stacklevel=2,
            )
            # 개발 환경 호환성을 위해 임시 기본값 사용 (운영 환경에서는 설정 필수)
            return "mlops"
        return db_name

    def get_secondary_db_host(self) -> str:
        return self.secondary_db_host.strip()

    def get_secondary_db_port(self) -> int:
        return self.secondary_db_port or 3306

    def _is_host_reachable(self, host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, int(port)), timeout=self.db_probe_timeout_seconds):
                return True
        except OSError:
            return False


settings = Settings()

# Korean-only 학습/추론 파이프라인에서 사용하는 로컬 경로 및 학습 하이퍼파라미터
MAX_PAGE = 10
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DATA_PATH = os.path.join(BASE_DIR, "src/data/raw/movies.csv")
RESULT_DIR = os.path.join(BASE_DIR, "src/data/result")

EPOCHS = 300
LR = 0.001
BATCH_SIZE = 32
SQL = "MySQL"  # RDS/Aurora MySQL 호환 엔진 사용
