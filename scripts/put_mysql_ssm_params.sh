#!/usr/bin/env bash
set -euo pipefail

# 사용법:
#   AWS_PROFILE=your-profile \
#   MYSQL_HOST="your-rds-endpoint" \
#   MYSQL_USER="admin" \
#   MYSQL_PASSWORD="..." \
#   bash scripts/put_mysql_ssm_params.sh
#
# 선택 환경변수:
#   AWS_REGION (기본값: ap-northeast-2)
#   MYSQL_PORT (기본값: 3306)
#   MYSQL_DATABASE (기본값: mlops)
#   MYSQL_ANALYZE_ID_TABLE (기본값: analyze_id_prediction_logs)

AWS_REGION="${AWS_REGION:-ap-northeast-2}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_DATABASE="${MYSQL_DATABASE:-mlops}"
MYSQL_ANALYZE_ID_TABLE="${MYSQL_ANALYZE_ID_TABLE:-analyze_id_prediction_logs}"

if [[ -z "${MYSQL_HOST:-}" ]]; then
  echo "오류: MYSQL_HOST 값을 먼저 설정하세요."
  exit 1
fi

if [[ -z "${MYSQL_USER:-}" ]]; then
  echo "오류: MYSQL_USER 값을 먼저 설정하세요."
  exit 1
fi

if [[ -z "${MYSQL_PASSWORD:-}" ]]; then
  echo "오류: MYSQL_PASSWORD 값을 먼저 설정하세요."
  exit 1
fi

PARAM_PREFIX="/team-prj-group3/dev/mlops"

echo "[1/6] MYSQL_HOST 저장"
aws ssm put-parameter \
  --region "$AWS_REGION" \
  --name "${PARAM_PREFIX}/MYSQL_HOST" \
  --type "String" \
  --value "$MYSQL_HOST" \
  --overwrite

echo "[2/6] MYSQL_PORT 저장"
aws ssm put-parameter \
  --region "$AWS_REGION" \
  --name "${PARAM_PREFIX}/MYSQL_PORT" \
  --type "String" \
  --value "$MYSQL_PORT" \
  --overwrite

echo "[3/6] MYSQL_USER 저장"
aws ssm put-parameter \
  --region "$AWS_REGION" \
  --name "${PARAM_PREFIX}/MYSQL_USER" \
  --type "String" \
  --value "$MYSQL_USER" \
  --overwrite

echo "[4/6] MYSQL_PASSWORD 저장"
aws ssm put-parameter \
  --region "$AWS_REGION" \
  --name "${PARAM_PREFIX}/MYSQL_PASSWORD" \
  --type "SecureString" \
  --value "$MYSQL_PASSWORD" \
  --overwrite

echo "[5/6] MYSQL_DATABASE 저장"
aws ssm put-parameter \
  --region "$AWS_REGION" \
  --name "${PARAM_PREFIX}/MYSQL_DATABASE" \
  --type "String" \
  --value "$MYSQL_DATABASE" \
  --overwrite

echo "[6/6] MYSQL_ANALYZE_ID_TABLE 저장"
aws ssm put-parameter \
  --region "$AWS_REGION" \
  --name "${PARAM_PREFIX}/MYSQL_ANALYZE_ID_TABLE" \
  --type "String" \
  --value "$MYSQL_ANALYZE_ID_TABLE" \
  --overwrite

cat <<'EOF'
완료:
- /team-prj-group3/dev/mlops/MYSQL_HOST
- /team-prj-group3/dev/mlops/MYSQL_PORT
- /team-prj-group3/dev/mlops/MYSQL_USER
- /team-prj-group3/dev/mlops/MYSQL_PASSWORD
- /team-prj-group3/dev/mlops/MYSQL_DATABASE
- /team-prj-group3/dev/mlops/MYSQL_ANALYZE_ID_TABLE
EOF
