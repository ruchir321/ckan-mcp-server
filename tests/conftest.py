import os
import re
import sys

import pytest

# Make the top-level module importable when tests run from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mcp_ckan_server as server

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
