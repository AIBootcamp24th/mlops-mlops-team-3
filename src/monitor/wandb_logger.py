from __future__ import annotations

import os
from typing import Any

import wandb

from src.config import settings


def init_run(config: dict[str, Any]) -> wandb.sdk.wandb_run.Run:
    if settings.wandb_api_key:
        os.environ["WANDB_API_KEY"] = settings.wandb_api_key
    return wandb.init(
        project=settings.wandb_project,
        entity=settings.wandb_entity or None,
        config=config,
    )
