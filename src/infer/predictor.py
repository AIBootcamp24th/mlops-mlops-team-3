from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch import nn
from sklearn.preprocessing import StandardScaler

from src.config import settings
from src.constants import FEATURE_COLS
from src.data.s3_io import download_file
from src.train.model import RatingRegressor


class LegacyRatingRegressor(nn.Module):
    def __init__(self, input_dim: int, hidden1: int, hidden2: int) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(input_dim, hidden1),
            nn.ReLU(),
            nn.Linear(hidden1, hidden2),
            nn.ReLU(),
            nn.Linear(hidden2, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.layers(x)


class ModelPredictor:
    def __init__(self, feature_cols: list[str] | None = None) -> None:
        self.feature_cols = feature_cols or FEATURE_COLS
        self.model = RatingRegressor(input_dim=len(self.feature_cols))
        self.scaler = StandardScaler()
        self.model_loaded = False
        self.loaded_model_run_id = ""

    def load(self) -> None:
        model_path = Path(settings.api_model_local_path)
        if model_path.exists():
            self._load_from_local(model_path)
            return

        if not settings.api_model_s3_key:
            raise FileNotFoundError(
                "모델 파일을 찾을 수 없습니다. API_MODEL_LOCAL_PATH를 준비하거나 "
                "API_MODEL_S3_KEY를 설정하세요."
            )

        model_path.parent.mkdir(parents=True, exist_ok=True)
        download_file(settings.aws_s3_model_bucket, settings.api_model_s3_key, str(model_path))
        self._load_from_local(model_path)
        # Update run_id if loading from S3 key directly
        if "models/" in settings.api_model_s3_key:
            self.loaded_model_run_id = settings.api_model_s3_key.split("/")[1]

    def check_and_reload(self) -> bool:
        """Checks champion.json from S3 and reloads if a new model is available."""
        import json
        from tempfile import TemporaryDirectory
        
        with TemporaryDirectory() as tmpdir:
            local_registry = Path(tmpdir) / "champion.json"
            try:
                download_file(
                    settings.aws_s3_model_bucket, 
                    settings.api_model_registry_key, 
                    str(local_registry)
                )
                with open(local_registry, "r") as f:
                    registry = json.load(f)
                
                new_run_id = registry.get("run_id")
                new_s3_key = registry.get("s3_key")
                
                if new_run_id and new_run_id != self.loaded_model_run_id:
                    print(f"- 새로운 Champion 모델 감지: {new_run_id}. 로딩 시작...")
                    local_model_path = Path(settings.api_model_local_path)
                    download_file(settings.aws_s3_model_bucket, new_s3_key, str(local_model_path))
                    self._load_from_local(local_model_path)
                    self.loaded_model_run_id = new_run_id
                    print(f"- 새로운 모델 로드 완료: {new_run_id}")
                    return True
            except Exception as e:
                print(f"- 모델 체크 중 에러 (무시됨): {e}")
        return False

    def predict_one(self, features: list[float]) -> float:
        self._ensure_loaded()
        if len(features) != len(self.feature_cols):
            raise ValueError(f"피처 개수가 일치하지 않습니다. expected={len(self.feature_cols)}")
        scaled = self.scaler.transform([features])
        x = torch.tensor(scaled, dtype=torch.float32)
        with torch.no_grad():
            raw = float(self.model(x).view(-1).item())
            return float(min(10.0, max(0.0, raw)))

    def predict_many(self, rows: list[list[float]]) -> list[float]:
        self._ensure_loaded()
        invalid_rows = [idx for idx, row in enumerate(rows) if len(row) != len(self.feature_cols)]
        if invalid_rows:
            raise ValueError(
                f"피처 개수가 일치하지 않는 row index가 있습니다: {invalid_rows[:5]}"
            )
        scaled = self.scaler.transform(rows)
        x = torch.tensor(scaled, dtype=torch.float32)
        with torch.no_grad():
            return [float(min(10.0, max(0.0, value))) for value in self.model(x).view(-1).tolist()]

    def _load_from_local(self, model_path: Path) -> None:
        checkpoint = torch.load(model_path, map_location="cpu")

        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
            feature_cols = checkpoint.get("feature_cols", self.feature_cols)
            hidden_dims = tuple(checkpoint.get("hidden_dims", [128, 64]))
            dropout = float(checkpoint.get("dropout", 0.2))
            self.feature_cols = feature_cols
            self.model = RatingRegressor(
                input_dim=len(self.feature_cols), hidden_dims=hidden_dims, dropout=dropout
            )
            self.model.load_state_dict(checkpoint["model_state_dict"])
            self._set_scaler_from_checkpoint(checkpoint)
        else:
            # 이전 버전 단일 state_dict와 호환
            self.model = self._build_legacy_model(checkpoint)
            self.model.load_state_dict(checkpoint)
            self._set_identity_scaler(len(self.feature_cols))

        self.model.eval()
        self.model_loaded = True

    def _ensure_loaded(self) -> None:
        if self.model_loaded:
            return
        self.load()

    def _set_scaler_from_checkpoint(self, checkpoint: dict) -> None:
        mean = np.array(checkpoint.get("scaler_mean", [0.0] * len(self.feature_cols)), dtype=float)
        scale = np.array(checkpoint.get("scaler_scale", [1.0] * len(self.feature_cols)), dtype=float)
        var = np.array(checkpoint.get("scaler_var", [1.0] * len(self.feature_cols)), dtype=float)
        self.scaler.mean_ = mean
        self.scaler.scale_ = np.where(scale == 0.0, 1.0, scale)
        self.scaler.var_ = np.where(var < 1e-12, 1.0, var)
        self.scaler.n_features_in_ = len(self.feature_cols)

    def _set_identity_scaler(self, feature_count: int) -> None:
        self.scaler.mean_ = np.zeros(feature_count, dtype=float)
        self.scaler.scale_ = np.ones(feature_count, dtype=float)
        self.scaler.var_ = np.ones(feature_count, dtype=float)
        self.scaler.n_features_in_ = feature_count

    def _build_legacy_model(self, state_dict: dict[str, torch.Tensor]) -> nn.Module:
        first_weight = state_dict.get("layers.0.weight")
        second_weight = state_dict.get("layers.2.weight")
        if first_weight is None or second_weight is None:
            return RatingRegressor(input_dim=len(self.feature_cols))

        hidden1 = int(first_weight.shape[0])
        hidden2 = int(second_weight.shape[0])
        return LegacyRatingRegressor(len(self.feature_cols), hidden1, hidden2)
