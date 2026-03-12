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

proxy_check_once() {
  local path="$1"
  local tmp_file="$2"
  curl -s -o "${tmp_file}" -w "%{http_code}" "http://127.0.0.1:${API_PORT}${path}" || true
}

verify_proxy_endpoints() {
  local health_code=""
  local docs_code=""
  for i in $(seq 1 10); do
    health_code="$(proxy_check_once "/health" "/tmp/mlops_api_health.json")"
    docs_code="$(proxy_check_once "/docs" "/tmp/mlops_api_docs.html")"
    echo "  proxy_verify try=${i} health=${health_code} docs=${docs_code}"
    if [[ "${health_code}" == "200" && "${docs_code}" == "200" ]]; then
      return 0
    fi
    sleep 2
  done
  return 1
}

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
# 템플릿에 플레이스홀더가 이미 치환된 상태여도 현재 대상 슬롯으로 강제 정렬한다.
sed -i -E "s/mlops-api-(blue|green)/${NEXT_NAME}/g" "${NGINX_RUNTIME_PATH}"

if docker ps -a --format '{{.Names}}' | grep -qx "${PROXY_NAME}"; then
  CURRENT_PROXY_CONF_SRC="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/etc/nginx/conf.d/default.conf"}}{{.Source}}{{end}}{{end}}' "${PROXY_NAME}")"
  if [[ -z "${CURRENT_PROXY_CONF_SRC}" ]]; then
    echo "ERROR: 기존 프록시 컨테이너의 Nginx conf 마운트 경로를 찾지 못했습니다."
    exit 1
  fi
  BACKUP_PROXY_CONF="${CURRENT_PROXY_CONF_SRC}.bak.$(date +%s)"
  cp "${CURRENT_PROXY_CONF_SRC}" "${BACKUP_PROXY_CONF}"
  # bind mount된 파일은 inode를 유지한 채 덮어써야 컨테이너에서 즉시 반영된다.
  cat "${NGINX_RUNTIME_PATH}" > "${CURRENT_PROXY_CONF_SRC}"
  docker start "${PROXY_NAME}" >/dev/null 2>&1 || true
  if ! docker exec "${PROXY_NAME}" nginx -t; then
    echo "ERROR: 새 프록시 설정 검증 실패. 기존 설정으로 롤백합니다."
    cat "${BACKUP_PROXY_CONF}" > "${CURRENT_PROXY_CONF_SRC}"
    exit 1
  fi
  if ! docker exec "${PROXY_NAME}" nginx -s reload; then
    echo "ERROR: nginx reload 실패. 기존 설정으로 롤백합니다."
    cat "${BACKUP_PROXY_CONF}" > "${CURRENT_PROXY_CONF_SRC}"
    docker exec "${PROXY_NAME}" nginx -s reload || true
    exit 1
  fi
  if ! verify_proxy_endpoints; then
    echo "ERROR: 프록시 전환 후 검증 실패. 기존 업스트림으로 롤백합니다."
    cat "${BACKUP_PROXY_CONF}" > "${CURRENT_PROXY_CONF_SRC}"
    docker exec "${PROXY_NAME}" nginx -s reload || true
    exit 1
  fi
  rm -f "${BACKUP_PROXY_CONF}" >/dev/null 2>&1 || true
else
  docker run -d --name "${PROXY_NAME}" --restart unless-stopped \
    --network "${NETWORK_NAME}" \
    -p "${API_PORT}:80" \
    -v "${NGINX_RUNTIME_PATH}:/etc/nginx/conf.d/default.conf:ro" \
    nginx:1.27-alpine >/dev/null
  docker exec "${PROXY_NAME}" nginx -t
  if ! verify_proxy_endpoints; then
    echo "ERROR: 신규 프록시 기동 후 검증 실패"
    docker logs --tail 120 "${PROXY_NAME}" || true
    exit 1
  fi
fi

echo "[6/6] 배포 후 헬스체크"
CODE=""
for i in $(seq 1 6); do
  HEALTH_CODE="$(proxy_check_once "/health" "/tmp/mlops_api_health.json")"
  DOCS_CODE="$(proxy_check_once "/docs" "/tmp/mlops_api_docs.html")"
  CODE="${HEALTH_CODE}"
  echo "  try=${i} health=${HEALTH_CODE} docs=${DOCS_CODE}"
  if [[ "${HEALTH_CODE}" == "200" && "${DOCS_CODE}" == "200" ]]; then
    break
  fi
  sleep 2
done

if [[ "${HEALTH_CODE}" != "200" || "${DOCS_CODE}" != "200" ]]; then
  echo "ERROR: 프록시 엔드포인트 헬스체크 실패 (127.0.0.1:${API_PORT})"
  echo "proxy_logs_tail:"
  docker logs --tail 120 "${PROXY_NAME}" || true
  echo "next_container_logs_tail:"
  docker logs --tail 120 "${NEXT_NAME}" || true
  exit 1
fi

if [[ -n "${ACTIVE_NAME}" && "${ACTIVE_NAME}" != "${NEXT_NAME}" ]]; then
  docker rm -f "${ACTIVE_NAME}" >/dev/null 2>&1 || true
fi
docker rm -f "${LEGACY_NAME}" >/dev/null 2>&1 || true

echo
echo "=== 배포 결과 ==="
echo "endpoint: http://127.0.0.1:${API_PORT}"
echo "health:"
cat /tmp/mlops_api_health.json || true
echo
