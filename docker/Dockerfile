# HieraChain Docker images. Select a stage with --target:
# production (default), test, or benchmark.

FROM python:3.12-slim AS source

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md pytest.ini ./
COPY hierachain ./hierachain
COPY docker/tests ./docker/tests
COPY docker/scripts/benchmark_throughput.py ./docker/scripts/benchmark_throughput.py

RUN uv sync --frozen --no-dev && \
    uv pip install --python /app/.venv/bin/python \
      "psycopg[binary]>=3.2.0" "psycopg-pool>=3.2.0" && \
    mkdir -p /app/data /app/log

FROM source AS test

RUN uv pip install --python /app/.venv/bin/python pytest

CMD ["python", "-m", "pytest", "docker/tests", "-m", "docker", "-v"]

FROM source AS benchmark

CMD ["python", "docker/scripts/benchmark_throughput.py"]

FROM python:3.12-slim AS production

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    wireguard-tools \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /app/.venv && \
    /app/.venv/bin/pip install --no-cache-dir --upgrade pip

COPY docker/dist/hierachain-*.whl /tmp/
RUN /app/.venv/bin/pip install --no-cache-dir /tmp/hierachain-*.whl && \
    /app/.venv/bin/pip install --no-cache-dir \
      "psycopg[binary]>=3.2.0" "psycopg-pool>=3.2.0" \
      pytest pytest-html pytest-asyncio && \
    rm /tmp/hierachain-*.whl

COPY docker/.env.HRC.example /app/.env.HRC.example
COPY docker/.env.HRC.example /app/docker/.env.HRC.example
COPY docker/entrypoint.sh /app/docker/entrypoint.sh
COPY docker/scripts/ /app/docker/scripts/
COPY docker/stress/ /app/docker/stress/

RUN mkdir -p /app/data /app/log && \
    chmod +x /app/docker/entrypoint.sh /app/docker/scripts/wg-tc.sh

EXPOSE 2661 5555 26657 51820/udp

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["hrc", "node", "start", "--host", "0.0.0.0", "--port", "2661"]
