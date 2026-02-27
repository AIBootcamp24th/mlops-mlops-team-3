FROM continuumio/miniconda3:24.11.1-0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first for Docker layer caching
COPY environment.yml ./
RUN conda env create -f environment.yml && conda clean -afy

# Copy project files
COPY src ./src
COPY scripts ./scripts
COPY README.md ./

# Default: run SQS-driven training worker
CMD ["conda", "run", "--no-capture-output", "-n", "mlops", "python", "-m", "src.train.run_train"]
