from __future__ import annotations

import os
from pathlib import Path

import boto3


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"필수 환경변수가 누락되었습니다: {name}")
    return value


def main() -> None:
    region = _required("AWS_REGION")
    output_path = Path(os.getenv("SECRETS_ENV_PATH", ".env.secrets"))

    ssm_paths = {
        "WANDB_API_KEY": _required("SSM_WANDB_API_KEY_PARAM"),
        "SLACK_BOT_TOKEN": _required("SSM_SLACK_BOT_TOKEN_PARAM"),
        "SLACK_SIGNING_SECRET": _required("SSM_SLACK_SIGNING_SECRET_PARAM"),
        "SLACK_APP_TOKEN": _required("SSM_SLACK_APP_TOKEN_PARAM"),
        "TMDB_API_KEY": _required("SSM_TMDB_API_KEY_PARAM"),
    }

    ssm = boto3.client("ssm", region_name=region)
    lines: list[str] = []

    for env_key, param_name in ssm_paths.items():
        response = ssm.get_parameter(Name=param_name, WithDecryption=True)
        value = response["Parameter"]["Value"]
        lines.append(f"{env_key}={value}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"생성 완료: {output_path}")


if __name__ == "__main__":
    main()
