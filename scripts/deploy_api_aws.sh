#!/usr/bin/env bash
# AWS EC2에 API(amd64) 배포 + 헬스체크
# 사용법:
#   cp remote.env.example remote.env
#   # remote.env에 AWS_PROFILE, INSTANCE_ID, INSTANCE_AZ, SSH_KEY 등 입력
#   bash scripts/deploy_api_aws.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 커맨드라인/환경변수로 넘긴 값을 remote.env보다 우선 적용하기 위해 백업
CLI_AWS_PROFILE="${AWS_PROFILE-}"
CLI_AWS_REGION="${AWS_REGION-}"
CLI_INSTANCE_ID="${INSTANCE_ID-}"
CLI_INSTANCE_AZ="${INSTANCE_AZ-}"
CLI_REMOTE_HOST="${REMOTE_HOST-}"
CLI_REMOTE_USER="${REMOTE_USER-}"
CLI_REMOTE_PORT="${REMOTE_PORT-}"
CLI_SSH_KEY="${SSH_KEY-}"
CLI_SSH_PUBLIC_KEY="${SSH_PUBLIC_KEY-}"
CLI_REMOTE_DIR="${REMOTE_DIR-}"
CLI_API_PORT="${API_PORT-}"
CLI_PRUNE_REMOTE="${PRUNE_REMOTE-}"
CLI_LOCAL_IMAGE_TAG="${LOCAL_IMAGE_TAG-}"
CLI_REMOTE_IMAGE_TAG="${REMOTE_IMAGE_TAG-}"
CLI_SKIP_BUILD="${SKIP_BUILD-}"
CLI_DEPLOY_MODE="${DEPLOY_MODE-}"

if [[ -f "${PROJECT_ROOT}/remote.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${PROJECT_ROOT}/remote.env"
  set +a
fi

# AWS_PROFILE은 환경변수로 설정된 경우에만 사용 (GitHub Actions CI 환경에서는 보통 미설정)
# 로컬 개발 환경에서만 프로파일을 사용하고, CI 환경에서는 aws-actions/configure-aws-credentials로 설정된 자격증명을 사용
AWS_REGION="${AWS_REGION:-ap-northeast-2}"
INSTANCE_ID="${INSTANCE_ID:?INSTANCE_ID를 remote.env 또는 환경변수로 설정하세요}"
INSTANCE_AZ="${INSTANCE_AZ:?INSTANCE_AZ를 remote.env 또는 환경변수로 설정하세요}"
REMOTE_USER="${REMOTE_USER:-ubuntu}"
REMOTE_PORT="${REMOTE_PORT:-22}"
SSH_KEY="${SSH_KEY:?SSH_KEY를 remote.env 또는 환경변수로 설정하세요}"
SSH_PUBLIC_KEY="${SSH_PUBLIC_KEY:-}"
REMOTE_DIR="${REMOTE_DIR:-/home/${REMOTE_USER}/team_mlops/mlops_project}"
API_PORT="${API_PORT:-8000}"
PRUNE_REMOTE="${PRUNE_REMOTE:-true}"
LOCAL_IMAGE_TAG="${LOCAL_IMAGE_TAG:-mlops_project-api:amd64}"
REMOTE_IMAGE_TAG="${REMOTE_IMAGE_TAG:-mlops_project-api:latest}"
SKIP_BUILD="${SKIP_BUILD:-false}"
DEPLOY_MODE="${DEPLOY_MODE:-auto}"

# remote.env 로딩 후에도 CLI/환경변수 입력값이 있으면 우선 적용
[[ -n "${CLI_AWS_PROFILE}" ]] && AWS_PROFILE="${CLI_AWS_PROFILE}"
[[ -n "${CLI_AWS_REGION}" ]] && AWS_REGION="${CLI_AWS_REGION}"
[[ -n "${CLI_INSTANCE_ID}" ]] && INSTANCE_ID="${CLI_INSTANCE_ID}"
[[ -n "${CLI_INSTANCE_AZ}" ]] && INSTANCE_AZ="${CLI_INSTANCE_AZ}"
[[ -n "${CLI_REMOTE_HOST}" ]] && REMOTE_HOST="${CLI_REMOTE_HOST}"
[[ -n "${CLI_REMOTE_USER}" ]] && REMOTE_USER="${CLI_REMOTE_USER}"
[[ -n "${CLI_REMOTE_PORT}" ]] && REMOTE_PORT="${CLI_REMOTE_PORT}"
[[ -n "${CLI_SSH_KEY}" ]] && SSH_KEY="${CLI_SSH_KEY}"
[[ -n "${CLI_SSH_PUBLIC_KEY}" ]] && SSH_PUBLIC_KEY="${CLI_SSH_PUBLIC_KEY}"
[[ -n "${CLI_REMOTE_DIR}" ]] && REMOTE_DIR="${CLI_REMOTE_DIR}"
[[ -n "${CLI_API_PORT}" ]] && API_PORT="${CLI_API_PORT}"
[[ -n "${CLI_PRUNE_REMOTE}" ]] && PRUNE_REMOTE="${CLI_PRUNE_REMOTE}"
[[ -n "${CLI_LOCAL_IMAGE_TAG}" ]] && LOCAL_IMAGE_TAG="${CLI_LOCAL_IMAGE_TAG}"
[[ -n "${CLI_REMOTE_IMAGE_TAG}" ]] && REMOTE_IMAGE_TAG="${CLI_REMOTE_IMAGE_TAG}"
[[ -n "${CLI_SKIP_BUILD}" ]] && SKIP_BUILD="${CLI_SKIP_BUILD}"
[[ -n "${CLI_DEPLOY_MODE}" ]] && DEPLOY_MODE="${CLI_DEPLOY_MODE}"

if [[ -z "${REMOTE_HOST:-}" ]]; then
  # AWS_PROFILE이 설정된 경우에만 --profile 옵션 사용
  if [[ -n "${AWS_PROFILE:-}" ]]; then
    REMOTE_HOST="$(aws ec2 describe-instances \
      --profile "${AWS_PROFILE}" \
      --region "${AWS_REGION}" \
      --instance-ids "${INSTANCE_ID}" \
      --query "Reservations[0].Instances[0].PublicIpAddress" \
      --output text)"
  else
    REMOTE_HOST="$(aws ec2 describe-instances \
      --region "${AWS_REGION}" \
      --instance-ids "${INSTANCE_ID}" \
      --query "Reservations[0].Instances[0].PublicIpAddress" \
      --output text)"
  fi
fi
REMOTE_HOST="${REMOTE_HOST:?REMOTE_HOST를 확인할 수 없습니다}"

# REMOTE_DIR 안전 보정:
# - remote.env의 "~" 또는 로컬 HOME(/Users/...) 확장값이 들어오면
#   원격 홈(/home/<user>) 기반 경로로 보정한다.
if [[ "${REMOTE_DIR}" == "~" ]]; then
  REMOTE_DIR="/home/${REMOTE_USER}"
elif [[ "${REMOTE_DIR}" == "~/"* ]]; then
  REMOTE_DIR="/home/${REMOTE_USER}/${REMOTE_DIR#~/}"
elif [[ "${REMOTE_DIR}" == "${HOME}"* || "${REMOTE_DIR}" == /Users/* ]]; then
  REMOTE_DIR="/home/${REMOTE_USER}/team_mlops/mlops_project"
fi

if [[ -z "${SSH_PUBLIC_KEY}" ]]; then
  if [[ -f "${SSH_KEY}.pub" ]]; then
    SSH_PUBLIC_KEY="${SSH_KEY}.pub"
  else
    SSH_PUBLIC_KEY="${HOME}/.ssh/id_rsa.pub"
  fi
fi

if [[ ! -f "${SSH_PUBLIC_KEY}" ]]; then
  echo "ERROR: SSH_PUBLIC_KEY 파일을 찾을 수 없습니다: ${SSH_PUBLIC_KEY}"
  exit 1
fi

echo "=== AWS API 배포 시작 ==="
echo "instance_id: ${INSTANCE_ID}"
echo "remote: ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PORT}"
echo "remote_dir: ${REMOTE_DIR}"
echo "deploy_mode(requested): ${DEPLOY_MODE}"
echo

if [[ "${SKIP_BUILD}" == "true" ]]; then
  echo "[1/7] 로컬 이미지 빌드 건너뜀 (SKIP_BUILD=true)"
else
  echo "[1/7] 로컬에서 amd64 API 이미지 빌드"
  docker buildx build --platform linux/amd64 -f Dockerfile -t "${LOCAL_IMAGE_TAG}" --load .
fi

echo "[2/7] EC2 Instance Connect 임시 키 주입"
# AWS_PROFILE이 설정된 경우에만 --profile 옵션 사용
if [[ -n "${AWS_PROFILE:-}" ]]; then
  aws ec2-instance-connect send-ssh-public-key \
    --profile "${AWS_PROFILE}" \
    --region "${AWS_REGION}" \
    --instance-id "${INSTANCE_ID}" \
    --availability-zone "${INSTANCE_AZ}" \
    --instance-os-user "${REMOTE_USER}" \
    --ssh-public-key "file://${SSH_PUBLIC_KEY}" >/dev/null
else
  aws ec2-instance-connect send-ssh-public-key \
    --region "${AWS_REGION}" \
    --instance-id "${INSTANCE_ID}" \
    --availability-zone "${INSTANCE_AZ}" \
    --instance-os-user "${REMOTE_USER}" \
    --ssh-public-key "file://${SSH_PUBLIC_KEY}" >/dev/null
fi

EFFECTIVE_DEPLOY_MODE="${DEPLOY_MODE}"
if [[ "${DEPLOY_MODE}" == "auto" ]]; then
  if ssh -i "${SSH_KEY}" -p "${REMOTE_PORT}" -o StrictHostKeyChecking=accept-new \
    "${REMOTE_USER}@${REMOTE_HOST}" "docker ps -a --format '{{.Names}}' | grep -qx 'mlops-api'" >/dev/null 2>&1; then
    EFFECTIVE_DEPLOY_MODE="image-only"
  else
    EFFECTIVE_DEPLOY_MODE="full"
  fi
fi

if [[ "${EFFECTIVE_DEPLOY_MODE}" != "full" && "${EFFECTIVE_DEPLOY_MODE}" != "image-only" ]]; then
  echo "ERROR: DEPLOY_MODE는 auto|full|image-only 중 하나여야 합니다. 현재값=${DEPLOY_MODE}"
  exit 1
fi

echo "deploy_mode(effective): ${EFFECTIVE_DEPLOY_MODE}"

echo "[3/7] 원격 디렉터리 준비"
if [[ "${EFFECTIVE_DEPLOY_MODE}" == "full" ]]; then
  ssh -i "${SSH_KEY}" -p "${REMOTE_PORT}" -o StrictHostKeyChecking=accept-new \
    "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p ${REMOTE_DIR}"
else
  echo "  - image-only 모드: 원격 디렉터리 준비 생략"
fi

echo "[4/7] 프로젝트 파일 동기화"
if [[ "${EFFECTIVE_DEPLOY_MODE}" == "full" ]]; then
  rsync -az --delete \
    --exclude '.git' --exclude '.venv' --exclude '.pytest_cache' --exclude '.ruff_cache' \
    --exclude 'wandb' --exclude 'tmp' --exclude '__pycache__' \
    -e "ssh -i ${SSH_KEY} -p ${REMOTE_PORT} -o StrictHostKeyChecking=accept-new" \
    "${PROJECT_ROOT}/" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"
else
  echo "  - image-only 모드: 프로젝트 동기화 생략"
fi

echo "[5/7] 원격 디스크 정리(선택)"
if [[ "${PRUNE_REMOTE}" == "true" && "${EFFECTIVE_DEPLOY_MODE}" == "full" ]]; then
  ssh -i "${SSH_KEY}" -p "${REMOTE_PORT}" -o StrictHostKeyChecking=accept-new \
    "${REMOTE_USER}@${REMOTE_HOST}" "docker system prune -af >/dev/null || true; docker builder prune -af >/dev/null || true"
elif [[ "${PRUNE_REMOTE}" == "true" ]]; then
  echo "  - image-only 모드: 디스크 정리 생략"
fi

echo "[6/7] 이미지 전송 및 API 컨테이너 재기동"
docker save "${LOCAL_IMAGE_TAG}" | ssh -i "${SSH_KEY}" -p "${REMOTE_PORT}" -o StrictHostKeyChecking=accept-new \
  "${REMOTE_USER}@${REMOTE_HOST}" "
    docker rm -f mlops-api >/dev/null 2>&1 || true &&
    docker image rm -f ${REMOTE_IMAGE_TAG} >/dev/null 2>&1 || true &&
    docker load &&
    docker tag ${LOCAL_IMAGE_TAG} ${REMOTE_IMAGE_TAG} &&
    docker run -d --name mlops-api --restart unless-stopped -p ${API_PORT}:8000 \
      --env-file ${REMOTE_DIR}/.env \
      --env-file ${REMOTE_DIR}/.env.secrets \
      ${REMOTE_IMAGE_TAG} \
      uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000
  "

echo "[7/7] 배포 후 헬스체크"
for i in 1 2 3 4 5 6; do
  code="$(curl -s -o /tmp/mlops_api_health.json -w "%{http_code}" "http://${REMOTE_HOST}:${API_PORT}/health" || true)"
  echo "  try=${i} code=${code}"
  if [[ "${code}" == "200" ]]; then
    break
  fi
  sleep 2
done

echo
echo "=== 배포 결과 ==="
echo "endpoint: http://${REMOTE_HOST}:${API_PORT}"
echo "health:"
cat /tmp/mlops_api_health.json || true
echo
