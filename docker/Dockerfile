# HieraChain Docker Image
# For testing and deployment

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt requirements_dev.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt -r requirements_dev.txt

# Copy source code and project files
COPY hierachain/ ./hierachain/
COPY tests/ ./tests/
COPY scripts/ ./scripts/
COPY config/ ./config/
COPY pyproject.toml setup.py README.md ./

# Install package
RUN pip install --no-cache-dir .

# Create data directories
RUN mkdir -p /app/data /app/log

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LOG_LEVEL=INFO

# Expose ports
EXPOSE 5000 8000

# Default command
CMD ["python", "-m", "hierachain"]

