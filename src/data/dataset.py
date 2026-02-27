from __future__ import annotations

import pandas as pd
import torch
from torch.utils.data import Dataset


class RatingsDataset(Dataset):
    def __init__(self, dataframe: pd.DataFrame, feature_cols: list[str], target_col: str) -> None:
        self.x = torch.tensor(dataframe[feature_cols].values, dtype=torch.float32)
        self.y = torch.tensor(dataframe[target_col].values, dtype=torch.float32).view(-1, 1)

    def __len__(self) -> int:
        return len(self.x)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        return self.x[index], self.y[index]
