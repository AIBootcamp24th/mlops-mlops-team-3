#!/usr/bin/env bash
# AWS CLI 사전 점검 + 무중단 API 배포 래퍼
# 사용법:
#   cd mlops_project
#   bash scripts/deploy_api_aws_precheck.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# remote.env 기본 로드 (CLI/환경변수가 우선)
if [[ -f "${PROJECT_ROOT}/remote.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${PROJECT_ROOT}/remote.env"
  set +a
fi

AWS_REGION="${AWS_REGION:-ap-northeast-2}"
INSTANCE_ID="${INSTANCE_ID:?INSTANCE_ID를 remote.env 또는 환경변수로 설정하세요}"
INSTANCE_AZ="${INSTANCE_AZ:?INSTANCE_AZ를 remote.env 또는 환경변수로 설정하세요}"
REMOTE_USER="${REMOTE_USER:-ubuntu}"
REMOTE_PORT="${REMOTE_PORT:-22}"
SSH_KEY="${SSH_KEY:?SSH_KEY를 remote.env 또는 환경변수로 설정하세요}"
API_PORT="${API_PORT:-8000}"
RUN_NETWORK_DIAG_ON_SSH_FAIL="${RUN_NETWORK_DIAG_ON_SSH_FAIL:-true}"
RUN_DEEP_NETWORK_DIAG_ON_SSH_FAIL="${RUN_DEEP_NETWORK_DIAG_ON_SSH_FAIL:-true}"

if [[ ! -f "${SSH_KEY}" ]]; then
  echo "ERROR: SSH_KEY 파일을 찾을 수 없습니다: ${SSH_KEY}"
  exit 1
fi

SSH_PUBLIC_KEY="${SSH_PUBLIC_KEY:-}"
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

aws_ec2() {
  if [[ -n "${AWS_PROFILE:-}" ]]; then
    aws ec2 --profile "${AWS_PROFILE}" --region "${AWS_REGION}" "$@"
  else
    aws ec2 --region "${AWS_REGION}" "$@"
  fi
}

aws_eic() {
  if [[ -n "${AWS_PROFILE:-}" ]]; then
    aws ec2-instance-connect --profile "${AWS_PROFILE}" --region "${AWS_REGION}" "$@"
  else
    aws ec2-instance-connect --region "${AWS_REGION}" "$@"
  fi
}

echo "=== AWS CLI 사전 점검 ==="
echo "instance_id: ${INSTANCE_ID}"
echo "region: ${AWS_REGION}"

INSTANCE_STATE="$(aws_ec2 describe-instances \
  --instance-ids "${INSTANCE_ID}" \
  --query "Reservations[0].Instances[0].State.Name" \
  --output text)"

echo "instance_state: ${INSTANCE_STATE}"
if [[ "${INSTANCE_STATE}" == "stopped" || "${INSTANCE_STATE}" == "stopping" ]]; then
  echo "인스턴스가 중지 상태이므로 시작합니다."
  aws_ec2 start-instances --instance-ids "${INSTANCE_ID}" >/dev/null
  aws_ec2 wait instance-running --instance-ids "${INSTANCE_ID}"
fi

echo "EC2 상태 체크(instance-status-ok) 대기..."
aws_ec2 wait instance-status-ok --instance-ids "${INSTANCE_ID}"

REMOTE_HOST="$(aws_ec2 describe-instances \
  --instance-ids "${INSTANCE_ID}" \
  --query "Reservations[0].Instances[0].PublicIpAddress" \
  --output text)"

if [[ -z "${REMOTE_HOST}" || "${REMOTE_HOST}" == "None" ]]; then
  echo "ERROR: 퍼블릭 IP를 확인할 수 없습니다."
  exit 1
fi

SG_IDS="$(aws_ec2 describe-instances \
  --instance-ids "${INSTANCE_ID}" \
  --query "Reservations[0].Instances[0].SecurityGroups[*].GroupId" \
  --output text)"

echo "public_ip: ${REMOTE_HOST}"
echo "security_groups: ${SG_IDS}"

SSH_RULE_COUNT="$(aws_ec2 describe-security-groups \
  --group-ids ${SG_IDS} \
  --query "length(SecurityGroups[].IpPermissions[?IpProtocol=='tcp' && FromPort==\`${REMOTE_PORT}\` && ToPort==\`${REMOTE_PORT}\`][])" \
  --output text || echo 0)"

API_RULE_COUNT="$(aws_ec2 describe-security-groups \
  --group-ids ${SG_IDS} \
  --query "length(SecurityGroups[].IpPermissions[?IpProtocol=='tcp' && FromPort==\`${API_PORT}\` && ToPort==\`${API_PORT}\`][])" \
  --output text || echo 0)"

if [[ "${SSH_RULE_COUNT}" == "0" ]]; then
  echo "WARN: Security Group에 ${REMOTE_PORT}/tcp 인바운드가 보이지 않습니다."
else
  echo "ok: ${REMOTE_PORT}/tcp 인바운드 규칙 확인"
fi

if [[ "${API_RULE_COUNT}" == "0" ]]; then
  echo "WARN: Security Group에 ${API_PORT}/tcp 인바운드가 보이지 않습니다."
else
  echo "ok: ${API_PORT}/tcp 인바운드 규칙 확인"
fi

echo "EC2 Instance Connect 키 주입..."
aws_eic send-ssh-public-key \
  --instance-id "${INSTANCE_ID}" \
  --availability-zone "${INSTANCE_AZ}" \
  --instance-os-user "${REMOTE_USER}" \
  --ssh-public-key "file://${SSH_PUBLIC_KEY}" >/dev/null

echo "SSH 연결 테스트..."
if ! ssh -i "${SSH_KEY}" -p "${REMOTE_PORT}" \
  -o StrictHostKeyChecking=accept-new \
  -o ConnectTimeout=10 \
  "${REMOTE_USER}@${REMOTE_HOST}" "echo connected >/dev/null"; then
  echo "ERROR: SSH 연결 실패 (${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PORT})"
  if [[ "${RUN_NETWORK_DIAG_ON_SSH_FAIL}" == "true" ]]; then
    echo
    echo "AWS CLI 네트워크 진단 실행..."
    bash "${PROJECT_ROOT}/scripts/diagnose_ec2_ssh_network.sh" || true
  fi
  if [[ "${RUN_DEEP_NETWORK_DIAG_ON_SSH_FAIL}" == "true" ]]; then
    echo
    echo "AWS CLI 심화 진단 실행..."
    bash "${PROJECT_ROOT}/scripts/diagnose_ec2_ssh_deep.sh" || true
  fi
  echo "점검 항목:"
  echo "  1) 회사/로컬 네트워크에서 해당 IP:PORT 차단 여부"
  echo "  2) NACL/라우팅/서브넷 퍼블릭 접근 설정"
  echo "  3) 원격 호스트 SSH 데몬 상태"
  exit 1
fi

echo
echo "=== 무중단 배포 실행 ==="
echo "resolved_remote_host: ${REMOTE_HOST}"

# 최신 퍼블릭 IP를 강제로 주입해서 stale remote.env 값을 무시한다.
REMOTE_HOST="${REMOTE_HOST}" bash "${PROJECT_ROOT}/scripts/deploy_api_aws.sh"
