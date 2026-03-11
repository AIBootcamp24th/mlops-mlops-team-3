#!/usr/bin/env bash
# AWS CLI 심화 진단: SSH 타임아웃 원인 좁히기
# - NACL 상세 규칙
# - Reachability Analyzer(IGW -> ENI, tcp/22)
# - SSM 관리 준비 상태(IAM Role/Policy/Managed 여부)
#
# 사용법:
#   cd mlops_project
#   bash scripts/diagnose_ec2_ssh_deep.sh

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

aws_iam() {
  if [[ -n "${AWS_PROFILE:-}" ]]; then
    aws iam --profile "${AWS_PROFILE}" "$@"
  else
    aws iam "$@"
  fi
}

INSTANCE_STATE="$(aws_ec2 describe-instances --instance-ids "${INSTANCE_ID}" --query "Reservations[0].Instances[0].State.Name" --output text)"
VPC_ID="$(aws_ec2 describe-instances --instance-ids "${INSTANCE_ID}" --query "Reservations[0].Instances[0].VpcId" --output text)"
SUBNET_ID="$(aws_ec2 describe-instances --instance-ids "${INSTANCE_ID}" --query "Reservations[0].Instances[0].SubnetId" --output text)"
ENI_ID="$(aws_ec2 describe-instances --instance-ids "${INSTANCE_ID}" --query "Reservations[0].Instances[0].NetworkInterfaces[0].NetworkInterfaceId" --output text)"
PUBLIC_IP="$(aws_ec2 describe-instances --instance-ids "${INSTANCE_ID}" --query "Reservations[0].Instances[0].PublicIpAddress" --output text)"

echo "=== EC2 SSH 심화 진단 시작 ==="
echo "instance_id: ${INSTANCE_ID}"
echo "region: ${AWS_REGION}"
echo "instance_state: ${INSTANCE_STATE}"
echo "vpc_id: ${VPC_ID}"
echo "subnet_id: ${SUBNET_ID}"
echo "eni_id: ${ENI_ID}"
echo "public_ip: ${PUBLIC_IP}"
echo

echo "[1] NACL 상세 규칙 (우선순위 포함)"
NACL_IDS="$(aws_ec2 describe-network-acls \
  --filters "Name=association.subnet-id,Values=${SUBNET_ID}" \
  --query "NetworkAcls[].NetworkAclId" \
  --output text)"

if [[ -z "${NACL_IDS}" || "${NACL_IDS}" == "None" ]]; then
  echo "  - 서브넷에 연결된 NACL을 찾지 못했습니다."
else
  for nacl in ${NACL_IDS}; do
    echo "  - nacl_id: ${nacl}"
    aws_ec2 describe-network-acls --network-acl-ids "${nacl}" \
      --query "NetworkAcls[0].Entries[*].{Rule:RuleNumber,Egress:Egress,Action:RuleAction,Protocol:Protocol,Cidr:CidrBlock,From:PortRange.From,To:PortRange.To}" \
      --output table

    IN_ALLOW_22="$(aws_ec2 describe-network-acls --network-acl-ids "${nacl}" \
      --query "length(NetworkAcls[0].Entries[?Egress==\`false\` && RuleAction=='allow' && (Protocol=='6' || Protocol=='-1') && (Protocol=='-1' || (PortRange.From!=null && PortRange.From<=\`${REMOTE_PORT}\` && PortRange.To>=\`${REMOTE_PORT}\`))])" \
      --output text)"

    OUT_ALLOW_EPHEMERAL="$(aws_ec2 describe-network-acls --network-acl-ids "${nacl}" \
      --query "length(NetworkAcls[0].Entries[?Egress==\`true\` && RuleAction=='allow' && (Protocol=='6' || Protocol=='-1') && (Protocol=='-1' || (PortRange.From!=null && PortRange.From<=\`1024\` && PortRange.To>=\`65535\`))])" \
      --output text)"

    if [[ "${IN_ALLOW_22}" == "0" ]]; then
      echo "    WARN: inbound tcp/${REMOTE_PORT} 허용 규칙이 보이지 않습니다."
    else
      echo "    ok: inbound tcp/${REMOTE_PORT} 허용 규칙 존재"
    fi

    if [[ "${OUT_ALLOW_EPHEMERAL}" == "0" ]]; then
      echo "    WARN: outbound ephemeral(1024-65535) 허용 규칙이 보이지 않습니다."
    else
      echo "    ok: outbound ephemeral(1024-65535) 허용 규칙 존재"
    fi
  done
fi
echo

echo "[2] Reachability Analyzer (IGW -> ENI, tcp/${REMOTE_PORT})"
IGW_ID="$(aws_ec2 describe-internet-gateways \
  --filters "Name=attachment.vpc-id,Values=${VPC_ID}" \
  --query "InternetGateways[0].InternetGatewayId" \
  --output text)"

if [[ -z "${IGW_ID}" || "${IGW_ID}" == "None" || -z "${ENI_ID}" || "${ENI_ID}" == "None" ]]; then
  echo "  - IGW 또는 ENI 식별 실패로 Reachability Analyzer를 건너뜁니다."
else
  PATH_ID="$(aws_ec2 create-network-insights-path \
    --source "${IGW_ID}" \
    --destination "${ENI_ID}" \
    --protocol tcp \
    --destination-port "${REMOTE_PORT}" \
    --query "NetworkInsightsPath.NetworkInsightsPathId" \
    --output text 2>/tmp/reachability_create.err || true)"

  if [[ -z "${PATH_ID}" || "${PATH_ID}" == "None" ]]; then
    echo "  - 네트워크 인사이트 경로 생성 실패(권한/지원 리소스 제한 가능)"
    if [[ -f /tmp/reachability_create.err ]]; then
      sed 's/^/    /' /tmp/reachability_create.err || true
    fi
  else
    echo "  - path_id: ${PATH_ID}"
    ANALYSIS_ID="$(aws_ec2 start-network-insights-analysis \
      --network-insights-path-id "${PATH_ID}" \
      --query "NetworkInsightsAnalysis.NetworkInsightsAnalysisId" \
      --output text)"
    echo "  - analysis_id: ${ANALYSIS_ID}"

    STATUS="running"
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      STATUS="$(aws_ec2 describe-network-insights-analyses \
        --network-insights-analysis-ids "${ANALYSIS_ID}" \
        --query "NetworkInsightsAnalyses[0].Status" \
        --output text)"
      [[ "${STATUS}" == "succeeded" || "${STATUS}" == "failed" ]] && break
      sleep 2
    done
    echo "  - status: ${STATUS}"

    aws_ec2 describe-network-insights-analyses \
      --network-insights-analysis-ids "${ANALYSIS_ID}" \
      --query "NetworkInsightsAnalyses[0].{NetworkPathFound:NetworkPathFound,Status:Status,Explanations:Explanations[*].{Acl:Acl,SecurityGroup:SecurityGroup,Subnet:Subnet,Vpc:Vpc,Direction:Direction,Protocol:Protocol,PortRange:PortRange,ExplanationCode:ExplanationCode,AdditionalDetails:AdditionalDetails}}" \
      --output json
  fi
fi
echo

echo "[3] SSM 준비 상태 (IAM/관리 연결)"
INSTANCE_PROFILE_ARN="$(aws_ec2 describe-instances --instance-ids "${INSTANCE_ID}" --query "Reservations[0].Instances[0].IamInstanceProfile.Arn" --output text)"
if [[ -z "${INSTANCE_PROFILE_ARN}" || "${INSTANCE_PROFILE_ARN}" == "None" ]]; then
  echo "  - IAM Instance Profile 미연결"
  echo "    -> SSM 사용하려면 Instance Profile + AmazonSSMManagedInstanceCore 필요"
else
  echo "  - instance_profile_arn: ${INSTANCE_PROFILE_ARN}"
  PROFILE_NAME="${INSTANCE_PROFILE_ARN##*/}"
  ROLE_NAME="$(aws_iam get-instance-profile --instance-profile-name "${PROFILE_NAME}" --query "InstanceProfile.Roles[0].RoleName" --output text)"
  echo "  - role_name: ${ROLE_NAME}"

  HAS_SSM_POLICY="$(aws_iam list-attached-role-policies --role-name "${ROLE_NAME}" \
    --query "length(AttachedPolicies[?PolicyName=='AmazonSSMManagedInstanceCore'])" \
    --output text)"
  if [[ "${HAS_SSM_POLICY}" == "0" ]]; then
    echo "    WARN: AmazonSSMManagedInstanceCore 정책이 연결되어 있지 않습니다."
  else
    echo "    ok: AmazonSSMManagedInstanceCore 정책 연결됨"
  fi
fi

SSM_COUNT="$(aws_ssm describe-instance-information \
  --query "length(InstanceInformationList[?InstanceId=='${INSTANCE_ID}'])" \
  --output text)"
if [[ "${SSM_COUNT}" == "0" ]]; then
  echo "  - SSM 미관리 인스턴스(Agent/네트워크/Role 점검 필요)"
else
  echo "  - SSM 관리 인스턴스 확인됨"
fi
echo

echo "=== 심화 진단 완료 ==="
