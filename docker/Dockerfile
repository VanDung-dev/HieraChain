# HieraChain Docker Image
# For testing and deployment

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    iputils-ping \
    iproute2 \
    curl \
    && curl -fsSL https://get.docker.com | sh \
    && rm -rf /var/lib/apt/lists/*

# Copy source code and project files
COPY hierachain/ ./hierachain/
COPY .env.HRC.example ./.env
COPY pyproject.toml uv.lock ./
COPY tests/ ./tests/
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY README.md ./

# Provide version for setuptools-scm since .git is not copied
ARG VERSION=0.0.2
ENV SETUPTOOLS_SCM_PRETEND_VERSION=$VERSION

# Install ALL dependencies (production + development) in one optimized step
RUN pip install uv
RUN uv sync

# Install the project itself (editable mode for docker)
RUN uv pip install -e ".[dev]"

# Create data directories
RUN mkdir -p /app/data /app/log

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LOG_LEVEL=INFO

# Expose ports
EXPOSE 2661 5555 26657

# Install bash shell since slim image only has sh
RUN apt-get update && apt-get install -y --no-install-recommends bash && rm -rf /var/lib/apt/lists/*

# Default command - activate venv then run node service using sh (available on all images)
CMD ["sh", "-c", ". .venv/bin/activate && uv run hrc start --host 0.0.0.0 --port 2661"]
