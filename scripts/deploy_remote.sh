#!/usr/bin/env bash
# 원격 서버에 GPU 학습 환경 배포
# 사용법: remote.env 설정 후 ./scripts/deploy_remote.sh
#   cp remote.env.example remote.env  # 실제 값으로 수정

set -e

# remote.env에서 연결 정보 로드 (GitHub에 업로드되지 않음)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
if [[ -f "${PROJECT_ROOT}/remote.env" ]]; then
  set -a
  source "${PROJECT_ROOT}/remote.env"
  set +a
fi

REMOTE_HOST="${REMOTE_HOST:?REMOTE_HOST를 remote.env 또는 환경변수로 설정하세요}"
REMOTE_USER="${REMOTE_USER:-root}"
REMOTE_PORT="${REMOTE_PORT:-22}"
SSH_KEY="${SSH_KEY:?SSH_KEY를 remote.env 또는 환경변수로 설정하세요}"

echo "=== 원격 서버 GPU 학습 환경 배포 ==="
echo "호스트: ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PORT}"
echo ""

# 1) 로컬에서 GPU 이미지 빌드
echo "[1/4] GPU Docker 이미지 빌드 중..."
docker build -f Dockerfile.gpu -t mlops-trainer-gpu:latest .

# 2) 이미지를 tar로 저장
echo "[2/4] 이미지 아카이브 생성..."
docker save mlops-trainer-gpu:latest | gzip > /tmp/mlops-trainer-gpu.tar.gz

# 3) 원격 서버로 전송
echo "[3/4] 원격 서버로 전송 중..."
scp -i "${SSH_KEY}" -P "${REMOTE_PORT}" /tmp/mlops-trainer-gpu.tar.gz "${REMOTE_USER}@${REMOTE_HOST}:/tmp/"

# 4) 원격 서버에서 이미지 로드 및 .env 설정 안내
echo "[4/4] 원격 서버에서 이미지 로드..."
ssh -i "${SSH_KEY}" -p "${REMOTE_PORT}" "${REMOTE_USER}@${REMOTE_HOST}" << 'REMOTE_SCRIPT'
set -e
gunzip -c /tmp/mlops-trainer-gpu.tar.gz | docker load
rm -f /tmp/mlops-trainer-gpu.tar.gz
echo ""
echo "=== 배포 완료 ==="
echo "원격 서버에서 학습 워커 실행:"
echo "  docker run --gpus all --rm --env-file .env mlops-trainer-gpu:latest"
echo ""
echo ".env 파일은 mlops_project/.env 내용을 원격 서버에 복사해야 합니다."
echo ".env 복사: scp -i ${SSH_KEY} -P ${REMOTE_PORT} .env ${REMOTE_USER}@${REMOTE_HOST}:/root/"
REMOTE_SCRIPT

rm -f /tmp/mlops-trainer-gpu.tar.gz
echo ""
echo "배포가 완료되었습니다."
