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
    api_model_local_path: str = Field(default="artifacts/rating_model.pt", alias="API_MODEL_LOCAL_PATH")
    tmdb_api_key: str = Field(default="", alias="TMDB_API_KEY")
    tmdb_language: str = Field(default="ko-KR", alias="TMDB_LANGUAGE")


settings = Settings()

# Korean-only 학습/추론 파이프라인에서 사용하는 로컬 경로 및 학습 하이퍼파라미터
TOTAL_PAGES = 250
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DATA_PATH = os.path.join(BASE_DIR, "src/data/raw/movies.csv")
RESULT_DIR = os.path.join(BASE_DIR, "src/data/result")

EPOCHS = 300
LR = 0.001
BATCH_SIZE = 32
