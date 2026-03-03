# Example Code for TMDB Rating Prediction Project - MLOps Team 3

import wandb


def main():
    print("TMDB Rating Prediction Project - MLOps Team 3")


def train():
    wandb.init(
        entity="mlops-team3",
        project="TMDB-rating-prediction",
        name="initial-test-run",
        config={"epochs": 10, "learning_rate": 0.01, "batch_size": 32},
    )

    for epoch in range(wandb.config.epochs):
        loss = 1.0 / (epoch + 1)
        accuracy = epoch * 10

        wandb.log({"epoch": epoch, "loss": loss, "accuracy": accuracy})
        print(f"Epoch {epoch}: loss={loss:.4f}, accuracy={accuracy}%")

    wandb.finish()


if __name__ == "__main__":
    main()
    train()
