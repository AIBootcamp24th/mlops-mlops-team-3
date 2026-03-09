import os

import numpy as np
import pandas as pd
import torch
import torch.optim as optim
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
from torch import nn
from torch.utils.data import DataLoader

from src.config import BASE_DIR, BATCH_SIZE, EPOCHS, LR, RESULT_DIR
from src.data.dataset import RatingsDataset
from src.model.network import RatingPredictor


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
) -> float:
    model.train()
    losses = []

    for x_batch, y_batch in loader:
        x_batch = x_batch.to(device)
        y_batch = y_batch.to(device)

        optimizer.zero_grad()
        pred = model(x_batch)

        diff = pred - y_batch
        weights = torch.where(y_batch > 0.7, 10.0, 1.0)
        loss = (weights * (diff**2)).mean()

        loss.backward()
        optimizer.step()

        losses.append(float(loss.detach().cpu().item()))

    return float(np.mean(losses)) if losses else 0.0


@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> float:
    model.eval()
    y_true = []
    y_pred = []

    for x_batch, y_batch in loader:
        x_batch = x_batch.to(device)
        y_batch = y_batch.to(device)

        pred = model(x_batch)

        y_true.extend(y_batch.view(-1).cpu().tolist())
        y_pred.extend(pred.view(-1).cpu().tolist())

    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def train():
    processed_path = os.path.join(RESULT_DIR, "rating_data.csv")

    if not os.path.exists(processed_path):
        print(f"에러: 학습 데이터({processed_path})가 없습니다. main.py를 먼저 실행하세요.")
        return

    df = pd.read_csv(processed_path)

    train_features = ["watch_ratio", "popularity", "runtime", "budget"]
    target_col = "target_rating"

    train_df, val_df = train_test_split(df, test_size=0.2, random_state=42)

    train_dataset = RatingsDataset(train_df, feature_cols=train_features, target_col=target_col)
    val_dataset = RatingsDataset(val_df, feature_cols=train_features, target_col=target_col)

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = RatingPredictor(input_dim=len(train_features)).to(device)
    optimizer = optim.Adam(model.parameters(), lr=LR)

    print(f"학습 시작 (Device: {device})")

    best_val_rmse = float("inf")

    model_dir = os.path.join(BASE_DIR, "artifacts")
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, "rating_model.pt")

    for epoch in range(EPOCHS):
        train_loss = train_one_epoch(model, train_loader, optimizer, device)
        val_rmse = evaluate(model, val_loader, device)

        if val_rmse < best_val_rmse:
            best_val_rmse = val_rmse
            torch.save(model.state_dict(), model_path)

        if (epoch + 1) % 10 == 0:
            print(
                f"Epoch [{epoch + 1}/{EPOCHS}] "
                f"Train Loss: {train_loss:.4f} | Val RMSE: {val_rmse:.4f}"
            )

    print(f"최종 best model 저장 완료: {model_path}")
    print(f"Best Val RMSE: {best_val_rmse:.4f}")


if __name__ == "__main__":
    train()
