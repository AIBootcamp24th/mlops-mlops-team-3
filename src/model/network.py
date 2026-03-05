import torch
import torch.nn as nn
import torch.nn.functional as F


class RatingPredictor(nn.Module):
    def __init__(self, input_dim):
        super(RatingPredictor, self).__init__()
        self.fc1 = nn.Linear(input_dim, 256)
        self.bn1 = nn.BatchNorm1d(256)
        self.fc2 = nn.Linear(256, 128)
        self.bn2 = nn.BatchNorm1d(128)
        self.fc3 = nn.Linear(128, 64)

        self.fc_final = nn.Linear(64, 1)

        self.dropout = nn.Dropout(0.2)

    def forward(self, x):
        x = F.leaky_relu(self.bn1(self.fc1(x)))
        x = self.dropout(x)
        x = F.leaky_relu(self.bn2(self.fc2(x)))
        x = self.dropout(x)
        x = F.leaky_relu(self.fc3(x))

        x = torch.sigmoid(self.fc_final(x))
        return x
