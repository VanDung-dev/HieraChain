# HieraChain Docker Image — Production build (wheel-based)

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO \
    PATH="/app/.venv/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wireguard-tools \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

# Create venv and install wheel
RUN python3 -m venv /app/.venv && \
    /app/.venv/bin/pip install --no-cache-dir --upgrade pip
COPY docker/dist/hierachain-*.whl /tmp/
RUN /app/.venv/bin/pip install --no-cache-dir /tmp/hierachain-*.whl && \
    rm /tmp/hierachain-*.whl

# Copy runtime files
COPY docker/entrypoint.sh /app/docker/entrypoint.sh
COPY docker/scripts/ /app/docker/scripts/

RUN mkdir -p /app/data /app/log && \
    chmod +x /app/docker/entrypoint.sh /app/docker/scripts/wg-tc.sh

EXPOSE 2661 5555 26657 51820/udp

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["hrc", "node", "start", "--host", "0.0.0.0", "--port", "2661"]
