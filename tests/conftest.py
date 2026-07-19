import os
import re
import socket
import sys
from functools import wraps
from types import SimpleNamespace

import aiohttp
import pytest

# Make the top-level module importable when tests run from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Exercise the full tool surface under test (the low-value endpoints are gated off
# by default). Must be set before importing the server, since tools register at import.
os.environ.setdefault("CKAN_EXPOSE_ALL_TOOLS", "1")

from ckan_mcp_server import documents as document_scraper
from ckan_mcp_server import server

# aioresponses 0.7.9 predates aiohttp 3.14's required ``stream_writer``
# ClientResponse argument. Keep the existing offline mocks usable until its next
# release; this changes constructor plumbing only, not response behavior.
_client_response_init = aiohttp.ClientResponse.__init__


@wraps(_client_response_init)
def _compatible_client_response_init(self, *args, stream_writer=None, **kwargs):
    if stream_writer is None:
        stream_writer = SimpleNamespace(output_size=0)
    return _client_response_init(
        self,
        *args,
        stream_writer=stream_writer,
        **kwargs,
    )


aiohttp.ClientResponse.__init__ = _compatible_client_response_init


@pytest.fixture(autouse=True)
def stub_dns(monkeypatch):
    """Keep the SSRF guard offline-deterministic: resolve every host to a fixed
    public IP so the mocked crawler isn't blocked and no real DNS is hit. Tests
    that exercise is_safe_url's IP logic override this with their own mock."""

    def fake_getaddrinfo(host, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(document_scraper.socket, "getaddrinfo", fake_getaddrinfo)


TEST_CKAN_URL = "https://ckan.test"


@pytest.fixture(autouse=True)
async def configure_server():
    """Point the server at a fake CKAN URL and reset the shared client per test."""
    previous_url = server.CKAN_URL
    server.CKAN_URL = TEST_CKAN_URL
    server._client = None
    try:
        yield
    finally:
        if server._client is not None:
            await server._client.close()
        server._client = None
        server.CKAN_URL = previous_url


def action_url(endpoint: str) -> str:
    return f"{TEST_CKAN_URL}/api/3/action/{endpoint}"


def action_re(endpoint: str):
    """Match an action endpoint regardless of query string (aioresponses)."""
    return re.compile(rf"{re.escape(action_url(endpoint))}(\?.*)?$")
