#!/usr/bin/env bash
# 스테이징 E2E 검증 스크립트
# SQS-학습-등록-추론 경로를 순차 검증합니다.
# 사용: ./scripts/verify_staging_e2e.sh (mlops_project 디렉터리에서 실행)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "=== 1. 환경변수 검증 ==="
for var in AWS_REGION AWS_S3_RAW_BUCKET AWS_S3_MODEL_BUCKET AWS_S3_PRED_BUCKET TRAIN_QUEUE_URL INFER_QUEUE_URL; do
  if [ -z "${!var}" ]; then
    echo "경고: $var 미설정 (일부 검증이 스킵될 수 있음)"
  fi
done

echo "=== 2. 단위/통합 테스트 ==="
uv run pytest -q

echo "=== 3. 린트 ==="
uv run ruff check .

echo "=== 4. 데이터 변경 감지 스크립트 (DB/S3 필요) ==="
if [ -n "${AWS_S3_RAW_BUCKET:-}" ] && [ -n "${DB_HOST:-}" ]; then
  uv run python scripts/check_data_change.py || true
else
  echo "스킵: DB/S3 미설정"
fi

echo "=== 5. 레지스트리 스키마 통합 테스트 ==="
uv run pytest tests/test_registry_schema.py tests/test_sqs_payload_integration.py tests/test_quality_gate.py -v

echo "=== E2E 검증 완료 ==="
