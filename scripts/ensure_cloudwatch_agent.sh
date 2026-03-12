#!/usr/bin/env bash
# 배포 대상 EC2에 CloudWatch Agent를 설치/기동하여 CWAgent 지표를 보장한다.

set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-northeast-2}"
INSTANCE_ID="${INSTANCE_ID:?INSTANCE_ID를 설정하세요}"
INSTANCE_AZ="${INSTANCE_AZ:?INSTANCE_AZ를 설정하세요}"
REMOTE_HOST="${REMOTE_HOST:?REMOTE_HOST를 설정하세요}"
REMOTE_USER="${REMOTE_USER:?REMOTE_USER를 설정하세요}"
REMOTE_PORT="${REMOTE_PORT:-22}"
SSH_KEY="${SSH_KEY:?SSH_KEY를 설정하세요}"
SSH_PUBLIC_KEY="${SSH_PUBLIC_KEY:-${SSH_KEY}.pub}"

if [[ ! -f "${SSH_KEY}" ]]; then
  echo "ERROR: SSH 키 파일이 없습니다: ${SSH_KEY}"
  exit 1
fi

if [[ ! -f "${SSH_PUBLIC_KEY}" ]]; then
  echo "ERROR: SSH 공개키 파일이 없습니다: ${SSH_PUBLIC_KEY}"
  exit 1
fi

echo "=== CloudWatch Agent 보장 시작 ==="
echo "instance_id: ${INSTANCE_ID}"
echo "remote: ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PORT}"

aws ec2-instance-connect send-ssh-public-key \
  --region "${AWS_REGION}" \
  --instance-id "${INSTANCE_ID}" \
  --availability-zone "${INSTANCE_AZ}" \
  --instance-os-user "${REMOTE_USER}" \
  --ssh-public-key "file://${SSH_PUBLIC_KEY}" >/dev/null

ssh -i "${SSH_KEY}" -p "${REMOTE_PORT}" -o StrictHostKeyChecking=accept-new \
  "${REMOTE_USER}@${REMOTE_HOST}" "bash -s" <<'REMOTE_SCRIPT'
set -euo pipefail

if command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y amazon-cloudwatch-agent >/dev/null
elif command -v yum >/dev/null 2>&1; then
  sudo yum install -y amazon-cloudwatch-agent >/dev/null
elif command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -y >/dev/null
  sudo apt-get install -y amazon-cloudwatch-agent >/dev/null
else
  echo "ERROR: 지원하지 않는 패키지 매니저입니다."
  exit 1
fi

sudo mkdir -p /opt/aws/amazon-cloudwatch-agent/etc
sudo tee /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json >/dev/null <<'EOF'
{
  "agent": {
    "metrics_collection_interval": 60,
    "run_as_user": "root"
  },
  "metrics": {
    "namespace": "CWAgent",
    "append_dimensions": {
      "InstanceId": "${aws:InstanceId}"
    },
    "aggregation_dimensions": [["InstanceId"]],
    "metrics_collected": {
      "disk": {
        "measurement": ["used_percent"],
        "resources": ["/"],
        "ignore_file_system_types": ["sysfs", "devtmpfs", "tmpfs", "overlay", "squashfs"]
      }
    }
  }
}
EOF

sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config \
  -m ec2 \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json \
  -s >/dev/null

sudo systemctl enable amazon-cloudwatch-agent >/dev/null
sudo systemctl restart amazon-cloudwatch-agent
sudo systemctl is-active --quiet amazon-cloudwatch-agent
REMOTE_SCRIPT

echo "CloudWatch Agent 실행 확인 완료"
