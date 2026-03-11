#!/usr/bin/env bash
# AWS CLI 기반 EC2 SSH 경로 진단
# 사용법:
#   cd mlops_project
#   bash scripts/diagnose_ec2_ssh_network.sh

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
REMOTE_PORT="${REMOTE_PORT:-22}"
API_PORT="${API_PORT:-8000}"

aws_ec2() {
  if [[ -n "${AWS_PROFILE:-}" ]]; then
    aws ec2 --profile "${AWS_PROFILE}" --region "${AWS_REGION}" "$@"
  else
    aws ec2 --region "${AWS_REGION}" "$@"
  fi
}

aws_ssm() {
  if [[ -n "${AWS_PROFILE:-}" ]]; then
    aws ssm --profile "${AWS_PROFILE}" --region "${AWS_REGION}" "$@"
  else
    aws ssm --region "${AWS_REGION}" "$@"
  fi
}

echo "=== EC2 SSH 네트워크 진단 시작 ==="
echo "instance_id: ${INSTANCE_ID}"
echo "region: ${AWS_REGION}"
echo

INSTANCE_STATE="$(aws_ec2 describe-instances --instance-ids "${INSTANCE_ID}" --query "Reservations[0].Instances[0].State.Name" --output text)"
PUBLIC_IP="$(aws_ec2 describe-instances --instance-ids "${INSTANCE_ID}" --query "Reservations[0].Instances[0].PublicIpAddress" --output text)"
PUBLIC_DNS="$(aws_ec2 describe-instances --instance-ids "${INSTANCE_ID}" --query "Reservations[0].Instances[0].PublicDnsName" --output text)"
PRIVATE_IP="$(aws_ec2 describe-instances --instance-ids "${INSTANCE_ID}" --query "Reservations[0].Instances[0].PrivateIpAddress" --output text)"
VPC_ID="$(aws_ec2 describe-instances --instance-ids "${INSTANCE_ID}" --query "Reservations[0].Instances[0].VpcId" --output text)"
SUBNET_ID="$(aws_ec2 describe-instances --instance-ids "${INSTANCE_ID}" --query "Reservations[0].Instances[0].SubnetId" --output text)"
ASSOC_PUBLIC_IP="$(aws_ec2 describe-instances --instance-ids "${INSTANCE_ID}" --query "Reservations[0].Instances[0].NetworkInterfaces[0].Association.PublicIp" --output text)"
MAP_PUBLIC_IP_ON_LAUNCH="$(aws_ec2 describe-subnets --subnet-ids "${SUBNET_ID}" --query "Subnets[0].MapPublicIpOnLaunch" --output text)"

echo "[1] 인스턴스 기본 상태"
echo "  - state: ${INSTANCE_STATE}"
echo "  - public_ip: ${PUBLIC_IP}"
echo "  - public_dns: ${PUBLIC_DNS}"
echo "  - private_ip: ${PRIVATE_IP}"
echo "  - vpc_id: ${VPC_ID}"
echo "  - subnet_id: ${SUBNET_ID}"
echo "  - eni_association_public_ip: ${ASSOC_PUBLIC_IP}"
echo "  - subnet_map_public_ip_on_launch: ${MAP_PUBLIC_IP_ON_LAUNCH}"
echo

echo "[2] Security Group 인바운드 요약 (${REMOTE_PORT}, ${API_PORT})"
SG_IDS="$(aws_ec2 describe-instances --instance-ids "${INSTANCE_ID}" --query "Reservations[0].Instances[0].SecurityGroups[*].GroupId" --output text)"
echo "  - sg_ids: ${SG_IDS}"
for sg in ${SG_IDS}; do
  echo "  - sg: ${sg}"
  aws_ec2 describe-security-groups --group-ids "${sg}" \
    --query "SecurityGroups[0].IpPermissions[?IpProtocol=='tcp' && (FromPort==\`${REMOTE_PORT}\` || FromPort==\`${API_PORT}\`)]" \
    --output json
done
echo

echo "[3] 라우팅(0.0.0.0/0) 및 IGW 연결 확인"
MAIN_RT_ID="$(aws_ec2 describe-route-tables \
  --filters "Name=association.subnet-id,Values=${SUBNET_ID}" \
  --query "RouteTables[0].RouteTableId" \
  --output text)"

if [[ -z "${MAIN_RT_ID}" || "${MAIN_RT_ID}" == "None" ]]; then
  MAIN_RT_ID="$(aws_ec2 describe-route-tables \
    --filters "Name=vpc-id,Values=${VPC_ID}" "Name=association.main,Values=true" \
    --query "RouteTables[0].RouteTableId" \
    --output text)"
fi

echo "  - route_table_id: ${MAIN_RT_ID}"
aws_ec2 describe-route-tables --route-table-ids "${MAIN_RT_ID}" \
  --query "RouteTables[0].Routes[?DestinationCidrBlock=='0.0.0.0/0' || DestinationIpv6CidrBlock=='::/0']" \
  --output json

IGW_IDS="$(aws_ec2 describe-internet-gateways \
  --filters "Name=attachment.vpc-id,Values=${VPC_ID}" \
  --query "InternetGateways[].InternetGatewayId" \
  --output text)"
echo "  - internet_gateways: ${IGW_IDS:-None}"
echo

echo "[4] NACL 규칙 확인 (서브넷 연결 ACL)"
NACL_IDS="$(aws_ec2 describe-network-acls \
  --filters "Name=association.subnet-id,Values=${SUBNET_ID}" \
  --query "NetworkAcls[].NetworkAclId" \
  --output text)"
echo "  - nacl_ids: ${NACL_IDS:-None}"
for nacl in ${NACL_IDS}; do
  echo "  - nacl: ${nacl}"
  aws_ec2 describe-network-acls --network-acl-ids "${nacl}" \
    --query "NetworkAcls[0].Entries[?RuleAction=='deny' || (PortRange.From!=null && (PortRange.From==\`${REMOTE_PORT}\` || PortRange.To==\`${REMOTE_PORT}\` || PortRange.From==\`1024\` || PortRange.To==\`65535\`))]" \
    --output json
done
echo

echo "[5] EC2 상태 점검(System/Instance)"
aws_ec2 describe-instance-status --instance-ids "${INSTANCE_ID}" --include-all-instances \
  --query "InstanceStatuses[0].{InstanceState:InstanceState.Name,SystemStatus:SystemStatus.Status,InstanceStatus:InstanceStatus.Status,Events:Events}" \
  --output json
echo

echo "[6] SSM 관리 여부(원격 SSHD 확인 가능성)"
SSM_COUNT="$(aws_ssm describe-instance-information \
  --query "length(InstanceInformationList[?InstanceId=='${INSTANCE_ID}'])" \
  --output text)"
if [[ "${SSM_COUNT}" == "0" ]]; then
  echo "  - SSM 미연결: SSHD 상태를 AWS CLI로 직접 조회할 수 없음"
  echo "    (SSM Agent/Role 설정 후에는 send-command로 sshd 상태 점검 가능)"
else
  echo "  - SSM 연결됨:"
  aws_ssm describe-instance-information \
    --query "InstanceInformationList[?InstanceId=='${INSTANCE_ID}']" \
    --output json
fi
echo

echo "=== 진단 완료 ==="
