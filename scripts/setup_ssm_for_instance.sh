#!/usr/bin/env bash
# SSM 관리 연결을 위한 IAM Role/Instance Profile 준비 스크립트
# 기본은 dry-run이며, 실제 반영은 APPLY=true로 실행
#
# 사용법:
#   cd mlops_project
#   bash scripts/setup_ssm_for_instance.sh
#   APPLY=true bash scripts/setup_ssm_for_instance.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -f "${PROJECT_ROOT}/remote.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${PROJECT_ROOT}/remote.env"
  set +a
fi

AWS_REGION="${AWS_REGION:-ap-northeast-2}"
INSTANCE_ID="${INSTANCE_ID:?INSTANCE_ID를 remote.env 또는 환경변수로 설정하세요}"
APPLY="${APPLY:-false}"
ROLE_NAME="${ROLE_NAME:-ec2-ssm-managed-role}"
INSTANCE_PROFILE_NAME="${INSTANCE_PROFILE_NAME:-ec2-ssm-instance-profile}"

aws_ec2() {
  if [[ -n "${AWS_PROFILE:-}" ]]; then
    aws ec2 --profile "${AWS_PROFILE}" --region "${AWS_REGION}" "$@"
  else
    aws ec2 --region "${AWS_REGION}" "$@"
  fi
}

aws_iam() {
  if [[ -n "${AWS_PROFILE:-}" ]]; then
    aws iam --profile "${AWS_PROFILE}" "$@"
  else
    aws iam "$@"
  fi
}

echo "=== SSM 설정 점검 ==="
echo "instance_id: ${INSTANCE_ID}"
echo "apply: ${APPLY}"
echo "role_name: ${ROLE_NAME}"
echo "instance_profile_name: ${INSTANCE_PROFILE_NAME}"
echo

CURRENT_PROFILE_ARN="$(aws_ec2 describe-instances --instance-ids "${INSTANCE_ID}" --query "Reservations[0].Instances[0].IamInstanceProfile.Arn" --output text)"
if [[ -n "${CURRENT_PROFILE_ARN}" && "${CURRENT_PROFILE_ARN}" != "None" ]]; then
  echo "현재 인스턴스에 프로파일이 연결되어 있습니다: ${CURRENT_PROFILE_ARN}"
else
  echo "현재 인스턴스에 연결된 IAM Instance Profile이 없습니다."
fi
echo

ROLE_EXISTS="false"
if aws_iam get-role --role-name "${ROLE_NAME}" >/dev/null 2>&1; then
  ROLE_EXISTS="true"
fi
echo "role_exists: ${ROLE_EXISTS}"

PROFILE_EXISTS="false"
if aws_iam get-instance-profile --instance-profile-name "${INSTANCE_PROFILE_NAME}" >/dev/null 2>&1; then
  PROFILE_EXISTS="true"
fi
echo "instance_profile_exists: ${PROFILE_EXISTS}"
echo

if [[ "${APPLY}" != "true" ]]; then
  echo "[DRY-RUN] 아래 작업이 수행됩니다."
  if [[ "${ROLE_EXISTS}" != "true" ]]; then
    echo "  1) IAM Role 생성 (${ROLE_NAME})"
  fi
  echo "  2) Role에 AmazonSSMManagedInstanceCore 정책 연결"
  if [[ "${PROFILE_EXISTS}" != "true" ]]; then
    echo "  3) Instance Profile 생성 (${INSTANCE_PROFILE_NAME})"
  fi
  echo "  4) Instance Profile에 Role 연결"
  echo "  5) EC2 인스턴스(${INSTANCE_ID})에 Instance Profile 연결"
  echo
  echo "실행하려면:"
  echo "  APPLY=true bash scripts/setup_ssm_for_instance.sh"
  exit 0
fi

if [[ "${ROLE_EXISTS}" != "true" ]]; then
  TRUST_FILE="$(mktemp)"
  cat > "${TRUST_FILE}" <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "ec2.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
  aws_iam create-role --role-name "${ROLE_NAME}" --assume-role-policy-document "file://${TRUST_FILE}" >/dev/null
  rm -f "${TRUST_FILE}"
  echo "생성: IAM Role ${ROLE_NAME}"
fi

aws_iam attach-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-arn "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore" >/dev/null || true
echo "적용: AmazonSSMManagedInstanceCore 정책 연결"

if [[ "${PROFILE_EXISTS}" != "true" ]]; then
  aws_iam create-instance-profile --instance-profile-name "${INSTANCE_PROFILE_NAME}" >/dev/null
  echo "생성: Instance Profile ${INSTANCE_PROFILE_NAME}"
fi

aws_iam add-role-to-instance-profile \
  --instance-profile-name "${INSTANCE_PROFILE_NAME}" \
  --role-name "${ROLE_NAME}" >/dev/null 2>&1 || true
echo "적용: Instance Profile에 Role 연결"

# IAM 전파 지연으로 associate 호출이 즉시 실패할 수 있어 잠시 대기
sleep 8

ASSOCIATION_ID="$(aws_ec2 describe-iam-instance-profile-associations \
  --filters "Name=instance-id,Values=${INSTANCE_ID}" \
  --query "IamInstanceProfileAssociations[0].AssociationId" \
  --output text)"

PROFILE_ARN="$(aws_iam get-instance-profile --instance-profile-name "${INSTANCE_PROFILE_NAME}" \
  --query "InstanceProfile.Arn" --output text)"

if [[ -z "${ASSOCIATION_ID}" || "${ASSOCIATION_ID}" == "None" ]]; then
  if ! aws_ec2 associate-iam-instance-profile \
    --instance-id "${INSTANCE_ID}" \
    --iam-instance-profile "Name=${INSTANCE_PROFILE_NAME}" >/dev/null 2>&1; then
    aws_ec2 associate-iam-instance-profile \
      --instance-id "${INSTANCE_ID}" \
      --iam-instance-profile "Arn=${PROFILE_ARN}" >/dev/null
  fi
  echo "적용: 인스턴스에 Instance Profile 연결"
else
  aws_ec2 replace-iam-instance-profile-association \
    --association-id "${ASSOCIATION_ID}" \
    --iam-instance-profile "Arn=${PROFILE_ARN}" >/dev/null
  echo "적용: 기존 Instance Profile 교체"
fi

echo
echo "완료: SSM 연결은 수 분 내 반영될 수 있습니다."
echo "확인 명령:"
echo "  aws ssm describe-instance-information --region ${AWS_REGION}"
