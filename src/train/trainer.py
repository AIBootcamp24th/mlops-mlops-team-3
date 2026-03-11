import random
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset

from src.config import (
    BATCH_SIZE,
    EPOCHS,
    FEATURE_COLS_PATH,
    LR,
    MODEL_PATH,
    PROCESSED_DATA_PATH,
    SCALER_PATH,
)


def get_feature_columns(df: pd.DataFrame):
    numeric_features = [
        "popularity",
        "runtime",
        "budget",
        "vote_count",
        "release_year",
        "release_month",
        "log_popularity",
        "log_budget",
        "log_vote_count",
        "movie_age",
        "budget_per_runtime",
        "log_budget_per_runtime",
        "popularity_per_vote",
        "log_popularity_per_vote",
        "adult",
        "genre_count",
    ]

    genre_features = []
    for col in df.columns:
        if col.startswith("genre_") and col != "genre_count":
            numeric_col = pd.to_numeric(df[col], errors="coerce")
            non_null = numeric_col.dropna()
            unique_vals = set(non_null.unique())

            if len(non_null) > 0 and unique_vals.issubset({0, 1}):
                genre_features.append(col)

    feature_cols = list(dict.fromkeys(numeric_features + genre_features))
    return feature_cols


class RatingMLP(nn.Module):
    def __init__(self, input_dim: int):
        super().__init__()
        self.model = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
        )

    def forward(self, x):
        return self.model(x)


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
) -> float:
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

    if not y_true:
        return 0.0
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)

    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def main():
    set_seed(42)

    df = pd.read_csv(PROCESSED_DATA_PATH)
    print(f"- 학습 데이터 로드 완료: {len(df)}건")

    feature_cols = get_feature_columns(df)
    target_col = "vote_average"

    X = df[feature_cols].copy()
    y = pd.to_numeric(df[target_col], errors="coerce").fillna(0)

    X_train, X_val, y_train, y_val = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)

    X_train_tensor = torch.tensor(X_train_scaled, dtype=torch.float32)
    y_train_tensor = torch.tensor(y_train.values, dtype=torch.float32).view(-1, 1)

    X_val_tensor = torch.tensor(X_val_scaled, dtype=torch.float32)
    y_val_tensor = torch.tensor(y_val.values, dtype=torch.float32).view(-1, 1)

    train_dataset = TensorDataset(X_train_tensor, y_train_tensor)

    generator = torch.Generator()
    generator.manual_seed(42)

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        generator=generator,
    )

    model = RatingMLP(input_dim=len(feature_cols))
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)

    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0.0

        for batch_X, batch_y in train_loader:
            optimizer.zero_grad()
            preds = model(batch_X)
            loss = criterion(preds, batch_y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        model.eval()
        with torch.no_grad():
            val_preds = model(X_val_tensor)
            val_loss = criterion(val_preds, y_val_tensor).item()

        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(
                f"[Epoch {epoch + 1:03d}/{EPOCHS}] "
                f"train_loss={total_loss / len(train_loader):.4f}, "
                f"val_loss={val_loss:.4f}"
            )

    Path(MODEL_PATH).parent.mkdir(parents=True, exist_ok=True)

    torch.save(model.state_dict(), MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    joblib.dump(feature_cols, FEATURE_COLS_PATH)

    print(f"- 모델 저장 완료: {MODEL_PATH}")
    print(f"- 스케일러 저장 완료: {SCALER_PATH}")
    print(f"- feature 목록 저장 완료: {FEATURE_COLS_PATH}")


if __name__ == "__main__":
    main()
