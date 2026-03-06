#!/usr/bin/env bash
set -euo pipefail

# 사용법:
#   AWS_PROFILE=your-profile \
#   SUPABASE_SERVICE_ROLE_KEY="..." \
#   bash scripts/put_supabase_ssm_params.sh
#
# 선택 환경변수:
#   AWS_REGION (기본값: ap-northeast-2)
#   SUPABASE_URL (기본값: 현재 생성된 프로젝트 URL)
#   SUPABASE_PUBLISHABLE_KEY (기본값: 현재 생성된 publishable key)
#   SUPABASE_PREDICTION_TABLE (기본값: prediction_logs)

AWS_REGION="${AWS_REGION:-ap-northeast-2}"
SUPABASE_URL="${SUPABASE_URL:-https://wdafjmwwbxkroenvvbjz.supabase.co}"
SUPABASE_PUBLISHABLE_KEY="${SUPABASE_PUBLISHABLE_KEY:-sb_publishable_XutZiqqZ73r_wvF64yBsFg_rctZDcWP}"
SUPABASE_PREDICTION_TABLE="${SUPABASE_PREDICTION_TABLE:-prediction_logs}"

if [[ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]]; then
  echo "오류: SUPABASE_SERVICE_ROLE_KEY 값을 먼저 설정하세요."
  exit 1
fi

PARAM_PREFIX="/team-prj-group3/dev/mlops"

echo "[1/4] SUPABASE_SERVICE_ROLE_KEY 저장"
aws ssm put-parameter \
  --region "$AWS_REGION" \
  --name "${PARAM_PREFIX}/SUPABASE_SERVICE_ROLE_KEY" \
  --type "SecureString" \
  --value "$SUPABASE_SERVICE_ROLE_KEY" \
  --overwrite

echo "[2/4] SUPABASE_URL 저장"
aws ssm put-parameter \
  --region "$AWS_REGION" \
  --name "${PARAM_PREFIX}/SUPABASE_URL" \
  --type "String" \
  --value "$SUPABASE_URL" \
  --overwrite

echo "[3/4] SUPABASE_PUBLISHABLE_KEY 저장"
aws ssm put-parameter \
  --region "$AWS_REGION" \
  --name "${PARAM_PREFIX}/SUPABASE_PUBLISHABLE_KEY" \
  --type "String" \
  --value "$SUPABASE_PUBLISHABLE_KEY" \
  --overwrite

echo "[4/4] SUPABASE_PREDICTION_TABLE 저장"
aws ssm put-parameter \
  --region "$AWS_REGION" \
  --name "${PARAM_PREFIX}/SUPABASE_PREDICTION_TABLE" \
  --type "String" \
  --value "$SUPABASE_PREDICTION_TABLE" \
  --overwrite

cat <<'EOF'
완료:
- /team-prj-group3/dev/mlops/SUPABASE_SERVICE_ROLE_KEY
- /team-prj-group3/dev/mlops/SUPABASE_URL
- /team-prj-group3/dev/mlops/SUPABASE_PUBLISHABLE_KEY
- /team-prj-group3/dev/mlops/SUPABASE_PREDICTION_TABLE

다음으로 mlops_project/.env 에 아래 파라미터 경로를 설정하세요.
SSM_SUPABASE_SERVICE_ROLE_KEY_PARAM=/team-prj-group3/dev/mlops/SUPABASE_SERVICE_ROLE_KEY
EOF
