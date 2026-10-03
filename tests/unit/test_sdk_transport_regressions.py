"""Focused SDK URL and redirect regressions."""

import asyncio
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterator

import pytest

from hierachain.sdk.async_client import HieraChainAsyncClient
from hierachain.sdk.client import HieraChainClient
from hierachain.sdk.exceptions import HieraChainAPIError
from hierachain.sdk.types import HieraChainClientConfig


def test_sync_health_check_uses_supported_ledger_route(monkeypatch: pytest.MonkeyPatch) -> None:
    client = HieraChainClient(HieraChainClientConfig())
    requested: list[tuple[str, str]] = []

    def request(method: str, endpoint: str, **_kwargs: object) -> dict[str, str]:
        requested.append((method, endpoint))
        return {"status": "healthy"}

    monkeypatch.setattr(client, "_request", request)

    assert client.health_check() is True
    assert requested == [("GET", "/api/ledger/health")]


def test_async_health_check_uses_supported_ledger_route(monkeypatch: pytest.MonkeyPatch) -> None:
    client = HieraChainAsyncClient(HieraChainClientConfig())
    requested: list[tuple[str, str]] = []

    async def request(method: str, endpoint: str, **_kwargs: object) -> dict[str, str]:
        requested.append((method, endpoint))
        return {"status": "healthy"}

    monkeypatch.setattr(client, "_request", request)

    assert asyncio.run(client.health_check()) is True
    assert requested == [("GET", "/api/ledger/health")]


def test_sync_trace_escapes_entity_as_one_path_segment(monkeypatch: pytest.MonkeyPatch) -> None:
    client = HieraChainClient(HieraChainClientConfig())
    requested: list[str] = []

    def request(_method: str, endpoint: str, **_kwargs: object) -> dict[str, object]:
        requested.append(endpoint)
        return {"entity_id": "part?two#three", "chains": [], "events": []}

    monkeypatch.setattr(client, "_request", request)

    client.trace_entity("part?two#three")

    assert requested == ["/api/ledger/entities/part%3Ftwo%23three/trace"]


def test_async_trace_escapes_entity_as_one_path_segment(monkeypatch: pytest.MonkeyPatch) -> None:
    client = HieraChainAsyncClient(HieraChainClientConfig())
    requested: list[str] = []

    async def request(_method: str, endpoint: str, **_kwargs: object) -> dict[str, object]:
        requested.append(endpoint)
        return {"entity_id": "part?two#three", "chains": [], "events": []}

    monkeypatch.setattr(client, "_request", request)

    asyncio.run(client.trace_entity("part?two#three"))

    assert requested == ["/api/ledger/entities/part%3Ftwo%23three/trace"]


class _LocalHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _recording_handler(
    received_headers: list[dict[str, str]], redirect_to: str | None = None
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            received_headers.append(dict(self.headers.items()))
            if redirect_to is not None:
                self.send_response(302)
                self.send_header("Location", redirect_to)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return

            body = b'{"status":"healthy"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return Handler


@contextmanager
def _two_local_origins() -> Iterator[
    tuple[str, list[dict[str, str]], list[dict[str, str]]]
]:
    source_headers: list[dict[str, str]] = []
    destination_headers: list[dict[str, str]] = []
    destination = _LocalHTTPServer(
        ("127.0.0.1", 0), _recording_handler(destination_headers)
    )
    destination_url = f"http://127.0.0.1:{destination.server_port}/received"
    source = _LocalHTTPServer(
        ("127.0.0.1", 0), _recording_handler(source_headers, destination_url)
    )
    servers = (source, destination)
    threads = [
        threading.Thread(target=server.serve_forever, daemon=True) for server in servers
    ]
    for thread in threads:
        thread.start()
    try:
        yield (
            f"http://127.0.0.1:{source.server_port}",
            source_headers,
            destination_headers,
        )
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=2)


def test_api_key_clients_do_not_forward_key_across_origins() -> None:
    synthetic_key = "synthetic-sdk-regression-key"
    with _two_local_origins() as (source_url, source_headers, destination_headers):
        config = HieraChainClientConfig(base_url=source_url, api_key=synthetic_key)

        with HieraChainClient(config) as client:
            with pytest.raises(HieraChainAPIError) as sync_error:
                client._request("GET", "/resource")
        assert sync_error.value.status_code == 302

        async def request_async() -> None:
            async with HieraChainAsyncClient(config) as client:
                with pytest.raises(HieraChainAPIError) as async_error:
                    await client._request("GET", "/resource")
                assert async_error.value.status_code == 302

        asyncio.run(request_async())

    assert len(source_headers) == 2
    assert all(headers.get("X-API-Key") == synthetic_key for headers in source_headers)
    assert destination_headers == []
