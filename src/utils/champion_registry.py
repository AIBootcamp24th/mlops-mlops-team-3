"""
champion.json 기반 approved_run_id 및 model_key 해석 공용 유틸리티.

S3 models/registry/champion.json에서 champion 메타데이터를 읽어
tmdb/{approved_run_id}/*.csv 경로 및 모델 키를 결정합니다.
"""
from __future__ import annotations

import json
from typing import NamedTuple

from src.config import settings
from src.utils.aws_session import get_boto3_session


class ChampionRegistry(NamedTuple):
    """champion.json에서 읽은 메타데이터."""

    approved_run_id: str
    model_key: str
    model_bucket: str
    model_uri: str


def _fetch_champion_json() -> dict | None:
    """S3에서 champion.json을 읽어 파싱된 dict를 반환. 없거나 실패 시 None."""
    if not settings.api_model_registry_key or not settings.aws_s3_model_bucket:
        return None
    try:
        s3 = get_boto3_session().client("s3")
        obj = s3.get_object(
            Bucket=settings.aws_s3_model_bucket,
            Key=settings.api_model_registry_key,
        )
        raw = obj["Body"].read().decode("utf-8")
        return json.loads(raw)
    except Exception:
        return None


def resolve_approved_run_id() -> str | None:
    """
    champion.json에서 approved_run_id를 반환.
    레지스트리가 없거나 키가 비어 있으면 None.
    """
    data = _fetch_champion_json()
    if not data:
        return None
    run_id = data.get("approved_run_id") or data.get("run_id")
    return str(run_id).strip() if run_id else None


def resolve_champion_registry() -> ChampionRegistry | None:
    """
    champion.json 전체 메타를 반환.
    없거나 필수 필드가 비어 있으면 None.
    """
    data = _fetch_champion_json()
    if not data:
        return None
    run_id = data.get("approved_run_id") or data.get("run_id")
    model_key = data.get("model_key") or data.get("s3_key")
    model_bucket = data.get("model_bucket") or settings.aws_s3_model_bucket
    model_uri = data.get("model_uri", "")
    if not run_id or not model_key:
        return None
    return ChampionRegistry(
        approved_run_id=str(run_id).strip(),
        model_key=str(model_key).strip(),
        model_bucket=str(model_bucket).strip(),
        model_uri=str(model_uri).strip(),
    )


def resolve_champion_model_key() -> str:
    """
    champion 모델 S3 키를 반환.
    API_MODEL_S3_KEY가 설정되어 있으면 우선 사용.
    champion.json이 없거나 model_key가 없으면 RuntimeError.
    """
    if settings.api_model_s3_key:
        return settings.api_model_s3_key
    reg = resolve_champion_registry()
    if not reg:
        raise RuntimeError(
            "champion registry를 읽을 수 없거나 model_key가 비어 있습니다. "
            "API_MODEL_S3_KEY를 설정하거나 champion.json을 확인하세요."
        )
    return reg.model_key


def champion_s3_prefix(run_id: str) -> str:
    """tmdb/{run_id} 형식의 S3 prefix 반환."""
    return f"tmdb/{run_id}"


def champion_train_key(run_id: str) -> str:
    """tmdb/{run_id}/train.csv 경로 반환."""
    return f"{champion_s3_prefix(run_id)}/train.csv"


def champion_infer_key(run_id: str) -> str:
    """tmdb/{run_id}/infer.csv 경로 반환."""
    return f"{champion_s3_prefix(run_id)}/infer.csv"


def champion_predictions_key(run_id: str, ds: str = "", ts: str = "") -> str:
    """tmdb/{run_id}/predictions_{ds}_{ts}.csv 경로 반환."""
    suffix = f"{ds}_{ts}".strip("_") if (ds or ts) else "batch"
    return f"{champion_s3_prefix(run_id)}/predictions_{suffix}.csv"
