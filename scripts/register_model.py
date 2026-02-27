from __future__ import annotations

import os

import wandb

from src.config import settings


def main() -> None:
    if settings.wandb_api_key:
        os.environ["WANDB_API_KEY"] = settings.wandb_api_key

    api = wandb.Api()
    project = f"{settings.wandb_entity}/{settings.wandb_project}" if settings.wandb_entity else settings.wandb_project
    runs = api.runs(project)
    if not runs:
        raise RuntimeError("W&B run 이 존재하지 않습니다.")

    latest_run = runs[0]
    print(f"latest run: {latest_run.id}")
    print("모델 레지스트리 승격은 팀 정책에 맞춰 추가하세요.")


if __name__ == "__main__":
    main()
