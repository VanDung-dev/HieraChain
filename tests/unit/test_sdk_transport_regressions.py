"""Focused SDK URL and redirect regressions."""

import asyncio
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterator

import pytest

from hierachain.sdk.async_client import HieraChainAsyncClient
from hierachain.sdk.client import HieraChainClient
from hierachain.sdk.exceptions import HieraChainAPIError
from hierachain.sdk.types import HieraChainClientConfig
from hierachain.serialization import loads_json


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


@contextmanager
def _json_origin(response_body: bytes | None = None) -> Iterator[
    tuple[str, list[tuple[str, bytes, str | None]]]
]:
    received: list[tuple[str, bytes, str | None]] = []

    class Handler(BaseHTTPRequestHandler):
        def _reply(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            received.append((self.command, body, self.headers.get("Content-Type")))
            result = response_body if response_body is not None else body
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(result)))
            self.end_headers()
            self.wfile.write(result)

        def do_POST(self) -> None:
            self._reply()

        def do_GET(self) -> None:
            self._reply()

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = _LocalHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_sdk_json_bodies_and_unicode_round_trip_over_http() -> None:
    payload: dict[str, Any] = {
        "name": "Thiết bị 🌱", "details": {"measurements": [0.00001, 2**80 + 1, None]},
    }
    with _json_origin() as (url, received):
        config = HieraChainClientConfig(base_url=url, max_retries=0)
        with HieraChainClient(config) as client:
            assert client._request("POST", "/echo", data=payload) == payload

        async def run_async() -> None:
            async with HieraChainAsyncClient(config) as client:
                assert await client._request("POST", "/echo", data=payload) == payload

        asyncio.run(run_async())

    assert len(received) == 2
    for method, body, content_type in received:
        assert method == "POST"
        assert content_type == "application/json"
        assert "Thiết bị 🌱".encode("utf-8") in body
        assert loads_json(body) == payload


@pytest.mark.parametrize("body", [b"not-json", b'{"reading":NaN}', b'{"reading":1e400}'])
def test_sdk_invalid_json_records_failure_without_retrying_mutations(body: bytes) -> None:
    with _json_origin(body) as (url, received):
        config = HieraChainClientConfig(base_url=url, max_retries=5)
        with HieraChainClient(config) as client:
            with pytest.raises(HieraChainAPIError):
                client._request("POST", "/echo", data={"entity_id": "asset-1"})
            assert client._circuit._failure_count == 1

        async def run_async() -> None:
            async with HieraChainAsyncClient(config) as client:
                with pytest.raises(HieraChainAPIError):
                    await client._request("POST", "/echo", data={"entity_id": "asset-1"})
                assert client._circuit._failure_count == 1

        asyncio.run(run_async())

    assert len(received) == 2


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_sdk_rejects_unrepresentable_values_before_sending_http(invalid: int | float) -> None:
    with _json_origin() as (url, received):
        config = HieraChainClientConfig(base_url=url, max_retries=0)
        with HieraChainClient(config) as client:
            with pytest.raises((TypeError, ValueError)):
                client._request("POST", "/echo", data={"reading": invalid})

        async def run_async() -> None:
            async with HieraChainAsyncClient(config) as client:
                with pytest.raises((TypeError, ValueError)):
                    await client._request("POST", "/echo", data={"reading": invalid})

        asyncio.run(run_async())

    assert received == []


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
