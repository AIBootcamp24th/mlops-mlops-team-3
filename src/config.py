import os

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

    # Database connection variables (unified priority: DB_* > MYSQL_* > defaults)
    db_user: str = Field(default="", alias="DB_USER")
    db_password: str = Field(default="", alias="DB_PASSWORD")
    db_host: str = Field(default="", alias="DB_HOST")
    db_port: int = Field(default=3306, alias="DB_PORT")
    db_name: str = Field(default="", alias="DB_NAME")

    # MySQL logging variables used by /analyze/id async logger (legacy support)
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
        """Get database host with priority: DB_HOST > MYSQL_HOST > localhost."""
        return self.db_host or self.mysql_host or "localhost"

    def get_db_port(self) -> int:
        """Get database port with priority: DB_PORT > MYSQL_PORT > 3306."""
        return self.db_port if self.db_port != 3306 or not self.mysql_port else self.mysql_port

    def get_db_user(self) -> str:
        """Get database user with priority: DB_USER > MYSQL_USER > mlops."""
        return self.db_user or self.mysql_user or "mlops"

    def get_db_password(self) -> str:
        """Get database password with priority: DB_PASSWORD > MYSQL_PASSWORD > mlops1234."""
        return self.db_password or self.mysql_password or "mlops1234"

    def get_db_name(self) -> str:
        """Get database name with priority: DB_NAME > MYSQL_DATABASE > mlops."""
        return self.db_name or self.mysql_database or "mlops"


settings = Settings()

# Korean-only 학습/추론 파이프라인에서 사용하는 로컬 경로 및 학습 하이퍼파라미터
MAX_PAGE = 50
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DATA_PATH = os.path.join(BASE_DIR, "src/data/raw/movies.csv")
RESULT_DIR = os.path.join(BASE_DIR, "src/data/result")
MODEL_DIR = os.path.join(BASE_DIR, "src/model")
MODEL_PATH = os.path.join(MODEL_DIR, "rating_model.pt")
SCALER_PATH = os.path.join(MODEL_DIR, "scaler.pkl")
FEATURE_COLS_PATH = os.path.join(MODEL_DIR, "feature_cols.pkl")
PROCESSED_DATA_PATH = os.path.join(BASE_DIR, "src/data/processed/rating_data.csv")
INFERENCE_RESULT_PATH = os.path.join(RESULT_DIR, "inference_check.csv")

EPOCHS = 300
LR = 0.001
BATCH_SIZE = 32
SQL = "MySQL"
