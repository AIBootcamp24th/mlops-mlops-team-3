FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Install dependencies first for Docker layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Trainer runtime image
FROM base AS trainer-runtime

COPY src ./src
COPY scripts ./scripts
COPY README.md ./

CMD ["uv", "run", "python", "-m", "src.train.run_train"]

# API runtime image with embedded model
FROM base AS api-runtime

COPY src ./src
COPY models ./models
COPY README.md ./

ENV API_LOCAL_MODEL_PATH=/app/models/rating_model.pt

CMD ["uv", "run", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
