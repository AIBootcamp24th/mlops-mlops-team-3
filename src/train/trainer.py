import numpy as np
import torch
import torch.nn as nn

criterion = nn.MSELoss()


def train_one_epoch(model, dataloader, optimizer, device="cpu"):
    model.train()

    total_loss = 0.0

    for batch in dataloader:
        if isinstance(batch, dict):
            x = batch["features"].to(device)
            y = batch["target"].to(device)

        else:
            x, y = batch
            x = x.to(device)
            y = y.to(device)

        optimizer.zero_grad()

        preds = model(x)

        loss = criterion(preds.view(-1), y.view(-1))

        loss.backward()

        optimizer.step()

        total_loss += loss.item()

    return total_loss / len(dataloader)


def evaluate(model, dataloader, device="cpu"):

    model.eval()

    preds = []
    targets = []

    with torch.no_grad():
        for batch in dataloader:
            if isinstance(batch, dict):
                x = batch["features"].to(device)
                y = batch["target"].to(device)

            else:
                x, y = batch
                x = x.to(device)
                y = y.to(device)

            output = model(x)

            preds.extend(output.view(-1).cpu().numpy())
            targets.extend(y.view(-1).cpu().numpy())

    preds = np.array(preds)
    targets = np.array(targets)

    rmse = np.sqrt(((preds - targets) ** 2).mean())

    return float(rmse)
