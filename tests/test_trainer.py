import torch
from torch.utils.data import DataLoader, TensorDataset

from src.train.model import RatingRegressor
from src.train.trainer import evaluate, train_one_epoch


def test_train_and_evaluate_runs() -> None:
    x = torch.randn(32, 4)
    y = torch.randn(32, 1)
    dataset = TensorDataset(x, y)
    loader = DataLoader(dataset, batch_size=8, shuffle=False)

    model = RatingRegressor(input_dim=4)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    train_loss = train_one_epoch(model, loader, optimizer)
    val_rmse = evaluate(model, loader)

    assert train_loss >= 0
    assert val_rmse >= 0
