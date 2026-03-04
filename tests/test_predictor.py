from pathlib import Path

import torch

from src.config import settings
from src.constants import FEATURE_COLS
from src.infer.predictor import ModelPredictor
from src.train.model import RatingRegressor


def test_predictor_loads_checkpoint_with_scaler(tmp_path, monkeypatch) -> None:
    model_path = Path(tmp_path) / "rating_model.pt"
    model = RatingRegressor(input_dim=len(FEATURE_COLS), hidden_dims=(128, 64), dropout=0.2)
    checkpoint = {
        "model_state_dict": model.state_dict(),
        "feature_cols": FEATURE_COLS,
        "hidden_dims": [128, 64],
        "dropout": 0.2,
        "scaler_mean": [1.0, 2.0, 3.0, 4.0],
        "scaler_scale": [2.0, 2.0, 2.0, 2.0],
        "scaler_var": [4.0, 4.0, 4.0, 4.0],
    }
    torch.save(checkpoint, model_path)

    monkeypatch.setattr(settings, "api_model_local_path", str(model_path))
    predictor = ModelPredictor()
    predictor.load()

    assert predictor.model_loaded
    assert predictor.scaler.n_features_in_ == len(FEATURE_COLS)
