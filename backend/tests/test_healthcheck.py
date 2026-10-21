"""The container health probe (issue #8): exit code per kind of answer.

Each test talks real HTTP to a throwaway stdlib server on an ephemeral port.
"""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.healthcheck import main


def serve(status: int) -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/health"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def healthy() -> Iterator[str]:
    yield from serve(200)


@pytest.fixture
def failing() -> Iterator[str]:
    yield from serve(503)


def test_exit_0_on_http_200(healthy: str) -> None:
    assert main(healthy) == 0


def test_exit_1_on_a_non_200_status(failing: str) -> None:
    assert main(failing) == 1


def test_exit_1_when_the_connection_is_refused() -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    # The port is free again once the socket closes: nothing listens on it.
    assert main(f"http://127.0.0.1:{port}/health") == 1
