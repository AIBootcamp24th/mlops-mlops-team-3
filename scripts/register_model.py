from __future__ import annotations

import json
import os
from pathlib import Path

import wandb

from src.config import settings


def _project_name() -> str:
    if settings.wandb_entity:
        return f"{settings.wandb_entity}/{settings.wandb_project}"
    return settings.wandb_project


def _gate_passed(run: wandb.apis.public.Run) -> tuple[bool, float, float]:
    val_rmse = float(run.summary.get("final_val_rmse", run.summary.get("val_rmse", float("inf"))))
    out_of_range = float(
        run.summary.get(
            "final_val_out_of_range_ratio",
            run.summary.get("val_out_of_range_ratio", float("inf")),
        )
    )
    passed = (
        val_rmse <= settings.quality_gate_val_rmse_max
        and out_of_range <= settings.quality_gate_out_of_range_max
    )
    return passed, val_rmse, out_of_range


def main() -> None:
    quality_gate_required = os.getenv("QUALITY_GATE_REQUIRED", "false").lower() == "true"

    if settings.wandb_api_key:
        os.environ["WANDB_API_KEY"] = settings.wandb_api_key
    elif quality_gate_required:
        raise RuntimeError("QUALITY_GATE_REQUIRED=true 인데 WANDB_API_KEY가 비어 있습니다.")
    else:
        print("WANDB_API_KEY가 없어 품질 게이트를 건너뜁니다.")
        return

    api = wandb.Api()
    project = _project_name()
    runs = api.runs(project)
    if not runs:
        if quality_gate_required:
            raise RuntimeError("W&B run 이 존재하지 않습니다.")
        print("경고: W&B run 이 없어 품질 게이트를 건너뜁니다.")
        return

    approved_run: wandb.apis.public.Run | None = None
    selected_metrics: tuple[float, float] | None = None
    for run in runs:
        if run.state != "finished":
            continue
        if str(run.summary.get("status", "")) != "success":
            continue
        passed, rmse, out_of_range = _gate_passed(run)
        if passed:
            approved_run = run
            selected_metrics = (rmse, out_of_range)
            break

    if approved_run is None or selected_metrics is None:
        message = (
            "품질 게이트를 통과한 run이 없습니다. "
            f"(rmse<={settings.quality_gate_val_rmse_max}, "
            f"out_of_range<={settings.quality_gate_out_of_range_max})"
        )
        if quality_gate_required:
            raise RuntimeError(message)
        print(f"경고: {message}")
        return

    model_uri = str(approved_run.summary.get("model_uri", ""))
    if not model_uri:
        if quality_gate_required:
            raise RuntimeError("선정된 run에 model_uri가 없습니다.")
        print("경고: 선정된 run에 model_uri가 없어 품질 게이트를 건너뜁니다.")
        return

    rmse, out_of_range = selected_metrics
    model_manifest = {
        "approved_run_id": approved_run.id,
        "project": project,
        "model_uri": model_uri,
        "val_rmse": rmse,
        "val_out_of_range_ratio": out_of_range,
        "gate": {
            "val_rmse_max": settings.quality_gate_val_rmse_max,
            "val_out_of_range_max": settings.quality_gate_out_of_range_max,
        },
    }

    manifest_path = Path("artifacts/model_registry_candidate.json")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(model_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"approved run: {approved_run.id}")
    print(f"model uri: {model_uri}")
    print(f"manifest saved: {manifest_path}")


if __name__ == "__main__":
    main()
