from __future__ import annotations

import torch
from torch import nn


class RatingRegressor(nn.Module):
    def __init__(
        self,
        input_dim: int,
        hidden_dims: tuple[int, int] = (128, 64),
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        first_hidden, second_hidden = hidden_dims
        self.layers = nn.Sequential(
            nn.Linear(input_dim, first_hidden),
            nn.BatchNorm1d(first_hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(first_hidden, second_hidden),
            nn.BatchNorm1d(second_hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(second_hidden, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.layers(x)
