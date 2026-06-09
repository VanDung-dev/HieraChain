# HieraChain Docker Image — Production build
# Powered by uv (https://astral.sh/uv)

FROM python:3.12-slim

# Copy uv binary from the official image for maximum performance
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Configuration for uv
# - UV_COMPILE_BYTECODE: Compile Python files to bytecode for faster startup
# - UV_LINK_MODE: Use 'copy' instead of hardlinks (safer for Docker layers)
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO \
    PATH="/app/.venv/bin:$PATH"

# Install system dependencies: WireGuard tools for multi-region P2P mesh,
# iproute2 for tc (WAN simulation) and ip command
RUN apt-get update && apt-get install -y --no-install-recommends \
    wireguard-tools \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

# Copy project definition files first to leverage Docker layer caching
COPY pyproject.toml uv.lock ./

# Step 1: Install dependencies only (no source code yet)
# This layer is cached as long as pyproject.toml and uv.lock remain unchanged.
# Using --no-install-project to prepare the environment without the app itself.
# Including 'dev' extra to provide a complete development-ready environment.
RUN uv sync --frozen --no-install-project --extra dev

# Step 2: Copy the rest of the application
COPY . .

# Handle versioning for setuptools-scm (since .git is missing in container)
# This is typically passed as a --build-arg by the setup script
ARG VERSION=0.0.1-dev
ENV SETUPTOOLS_SCM_PRETEND_VERSION=$VERSION

# Step 3: Final sync to install the project in the virtual environment
# This installs HieraChain in editable mode as defined in pyproject.toml
RUN uv sync --frozen --extra dev && uv cache clean

# Create necessary runtime directories
RUN mkdir -p /app/data /app/log && \
    chmod +x /app/docker/entrypoint.sh /app/docker/scripts/wg-tc.sh

# Expose HieraChain standard ports
# 2661: API | 5555: ZMQ | 26657: BFT/P2P | 51820/udp: WireGuard
EXPOSE 2661 5555 26657 51820/udp

# Multi-region entrypoint: initializes WireGuard + tc, then starts HieraChain
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["uv", "run", "hrc", "node", "start", "--host", "0.0.0.0", "--port", "2661"]
