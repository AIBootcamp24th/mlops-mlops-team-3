#!/usr/bin/env bash
# EC2 인스턴스 내부에서 직접 API 블루/그린 배포를 수행한다.

set -euo pipefail

REMOTE_DIR="${REMOTE_DIR:-$(pwd)}"
API_PORT="${API_PORT:-8000}"
PRUNE_REMOTE="${PRUNE_REMOTE:-true}"
LOCAL_IMAGE_TAG="${LOCAL_IMAGE_TAG:-mlops_project-api:latest}"
NETWORK_NAME="${NETWORK_NAME:-mlops-api-net}"
PROXY_NAME="${PROXY_NAME:-mlops-api-proxy}"
BLUE_NAME="${BLUE_NAME:-mlops-api-blue}"
GREEN_NAME="${GREEN_NAME:-mlops-api-green}"
LEGACY_NAME="${LEGACY_NAME:-mlops-api}"

cd "${REMOTE_DIR}"

NGINX_TEMPLATE_PATH="${REMOTE_DIR}/nginx/default.conf"
if [[ ! -f "${NGINX_TEMPLATE_PATH}" ]]; then
  echo "ERROR: nginx 템플릿 파일이 없습니다: ${NGINX_TEMPLATE_PATH}"
  exit 1
fi

if [[ ! -f "${REMOTE_DIR}/.env" || ! -f "${REMOTE_DIR}/.env.secrets" ]]; then
  echo "ERROR: 원격 환경파일(.env/.env.secrets)이 필요합니다."
  exit 1
fi

echo "=== 인스턴스 내부 API 배포 시작 ==="
echo "remote_dir: ${REMOTE_DIR}"
echo "api_port: ${API_PORT}"
echo

echo "[1/6] 디스크 정리(선택)"
if [[ "${PRUNE_REMOTE}" == "true" ]]; then
  docker image prune -af >/dev/null || true
  docker builder prune -af >/dev/null || true
  docker container prune -f >/dev/null || true
fi

echo "[2/6] API 이미지 빌드"
docker build -f Dockerfile -t "${LOCAL_IMAGE_TAG}" .

echo "[3/6] 블루/그린 슬롯 결정"
docker network inspect "${NETWORK_NAME}" >/dev/null 2>&1 || docker network create "${NETWORK_NAME}" >/dev/null

if docker ps --format '{{.Names}}' | grep -qx "${BLUE_NAME}"; then
  ACTIVE_NAME="${BLUE_NAME}"
  NEXT_NAME="${GREEN_NAME}"
elif docker ps --format '{{.Names}}' | grep -qx "${GREEN_NAME}"; then
  ACTIVE_NAME="${GREEN_NAME}"
  NEXT_NAME="${BLUE_NAME}"
else
  ACTIVE_NAME=""
  NEXT_NAME="${BLUE_NAME}"
fi
echo "active=${ACTIVE_NAME:-none}, next=${NEXT_NAME}"

echo "[4/6] 다음 슬롯 기동 + 내부 헬스체크"
docker rm -f "${NEXT_NAME}" >/dev/null 2>&1 || true
docker run -d --name "${NEXT_NAME}" --restart unless-stopped --network "${NETWORK_NAME}" \
  --env-file "${REMOTE_DIR}/.env" \
  --env-file "${REMOTE_DIR}/.env.secrets" \
  "${LOCAL_IMAGE_TAG}" \
  uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 >/dev/null

NEXT_HEALTH_CODE=""
for i in $(seq 1 30); do
  NEXT_HEALTH_CODE="$(docker run --rm --network "${NETWORK_NAME}" curlimages/curl:8.10.1 -s -o /dev/null -w '%{http_code}' "http://${NEXT_NAME}:8000/health" || true)"
  echo "  next_container_health try=${i} code=${NEXT_HEALTH_CODE}"
  if [[ "${NEXT_HEALTH_CODE}" == "200" ]]; then
    break
  fi
  sleep 2
done

if [[ "${NEXT_HEALTH_CODE}" != "200" ]]; then
  echo "ERROR: 새 컨테이너 헬스체크 실패"
  docker logs --tail 120 "${NEXT_NAME}" || true
  exit 1
fi

echo "[5/6] Nginx 프록시 전환"
NGINX_RUNTIME_PATH="${REMOTE_DIR}/nginx/default.runtime.conf"
cp "${NGINX_TEMPLATE_PATH}" "${NGINX_RUNTIME_PATH}"
sed -i "s/REPLACE_UPSTREAM/${NEXT_NAME}/g" "${NGINX_RUNTIME_PATH}"

if docker ps -a --format '{{.Names}}' | grep -qx "${PROXY_NAME}"; then
  docker start "${PROXY_NAME}" >/dev/null 2>&1 || true
  docker cp "${NGINX_RUNTIME_PATH}" "${PROXY_NAME}:/etc/nginx/conf.d/default.conf"
  docker exec "${PROXY_NAME}" nginx -t
  docker exec "${PROXY_NAME}" nginx -s reload
else
  docker run -d --name "${PROXY_NAME}" --restart unless-stopped \
    --network "${NETWORK_NAME}" \
    -p "${API_PORT}:80" \
    -v "${NGINX_RUNTIME_PATH}:/etc/nginx/conf.d/default.conf:ro" \
    nginx:1.27-alpine >/dev/null
  docker exec "${PROXY_NAME}" nginx -t
fi

if [[ -n "${ACTIVE_NAME}" && "${ACTIVE_NAME}" != "${NEXT_NAME}" ]]; then
  docker rm -f "${ACTIVE_NAME}" >/dev/null 2>&1 || true
fi
docker rm -f "${LEGACY_NAME}" >/dev/null 2>&1 || true

echo "[6/6] 배포 후 헬스체크"
for i in $(seq 1 6); do
  CODE="$(curl -s -o /tmp/mlops_api_health.json -w "%{http_code}" "http://127.0.0.1:${API_PORT}/health" || true)"
  echo "  try=${i} code=${CODE}"
  if [[ "${CODE}" == "200" ]]; then
    break
  fi
  sleep 2
done

echo
echo "=== 배포 결과 ==="
echo "endpoint: http://127.0.0.1:${API_PORT}"
echo "health:"
cat /tmp/mlops_api_health.json || true
echo
