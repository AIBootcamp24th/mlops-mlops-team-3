from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
from sklearn.metrics import mean_squared_error
from torch import nn
from torch.utils.data import DataLoader


@dataclass
class TrainResult:
    train_loss: float
    val_rmse: float


def train_one_epoch(model: nn.Module, loader: DataLoader, optimizer: torch.optim.Optimizer) -> float:
    model.train()
    criterion = nn.MSELoss()
    losses: list[float] = []
    for x_batch, y_batch in loader:
        optimizer.zero_grad()
        pred = model(x_batch)
        loss = criterion(pred, y_batch)
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach().cpu().item()))
    return float(np.mean(losses)) if losses else 0.0


@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader) -> float:
    model.eval()
    y_true: list[float] = []
    y_pred: list[float] = []
    for x_batch, y_batch in loader:
        pred = model(x_batch)
        y_true.extend(y_batch.view(-1).tolist())
        y_pred.extend(pred.view(-1).tolist())
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))
