import os

import numpy as np
import pandas as pd
import torch
import torch.optim as optim
from sklearn.metrics import mean_squared_error
from torch import nn
from torch.utils.data import DataLoader

from src.config import BATCH_SIZE, EPOCHS, LR, RESULT_DIR
from src.data.dataset import RatingsDataset
from src.model.network import RatingPredictor


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


def train():

    processed_path = os.path.join(RESULT_DIR, "rating_data.csv")

    if not os.path.exists(processed_path):
        print(f"에러: 학습 데이터({processed_path})가 없습니다. main.py를 먼저 실행하세요.")
        return

    df = pd.read_csv(processed_path)

    train_features = ["watch_ratio", "popularity", "runtime", "budget"]

    dataset = RatingsDataset(df, feature_cols=train_features, target_col="target_rating")

    train_loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = RatingPredictor(input_dim=len(train_features)).to(device)

    optimizer = optim.Adam(model.parameters(), lr=LR)

    model.train()
    print(f"학습 시작 (Device: {device})")

    for epoch in range(EPOCHS):
        running_loss = 0.0
        for inputs, targets in train_loader:
            inputs, targets = inputs.to(device), targets.to(device)

            optimizer.zero_grad()
            outputs = model(inputs)

            diff = outputs - targets

            weights = torch.where(targets > 0.7, 10.0, 1.0)

            loss = (weights * (diff**2)).mean()

            loss.backward()
            optimizer.step()

            running_loss += loss.item()

        if (epoch + 1) % 10 == 0:
            print(f"Epoch [{epoch + 1}/{EPOCHS}], Loss: {running_loss / len(train_loader):.4f}")

    model_dir = "./src/model/checkpoints"
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, "model.pth")
    torch.save(model.state_dict(), model_path)
    print(f"모델 저장 완료: {model_path}")


if __name__ == "__main__":
    train()
