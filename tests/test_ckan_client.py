"""Offline tests for the CKAN client and tools (HTTP mocked with aioresponses)."""

import os
import subprocess
import sys

import httpx
import pytest
from aioresponses import aioresponses
from conftest import action_re, action_url
from fastmcp import Client
from fastmcp.exceptions import ToolError

from ckan_mcp_server import server

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A representative raw CKAN package, with noisy fields (extras, tracking) that
# the summarizer is expected to drop.
SAMPLE_PACKAGE = {
    "id": "abc-123",
    "name": "apartment-building-evaluation",
    "title": "Apartment Building Evaluation",
    "notes": "Evaluation scores for registered apartment buildings.",
    "information_url": "https://example.test/standards",
    "num_resources": 2,
    "metadata_modified": "2025-01-02T00:00:00",
    "organization": {"title": "Municipal Licensing & Standards", "id": "org-1"},
    "tags": [{"name": "housing"}, {"name": "rentsafe"}],
    "extras": [{"key": "noise", "value": "x" * 5000}],
    "tracking_summary": {"total": 999, "recent": 12},
    "resources": [
        {
            "id": "r1",
            "name": "2024 CSV",
            "format": "CSV",
            "url": "http://x/1.csv",
            "datastore_active": True,
            "size": 12345,
        },
        {
            "id": "r2",
            "name": "2024 JSON",
            "format": "JSON",
            "url": "http://x/1.json",
            "datastore_active": False,
        },
    ],
}


# --- Config validation ---


def test_missing_url_raises_tool_error():
    with pytest.raises(ToolError, match="CKAN_URL is not configured"):
        server.CKANAPIClient(None)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.test",
        "https://user:secret@example.test",
        "https://example.test/path?redirect=http://internal.test",
        "https://example.test:invalid",
        "https://example.test:99999",
        "https://example.test:0",
        "https://[invalid",
    ],
)
def test_invalid_ckan_base_url_raises_tool_error(url):
    with pytest.raises(ToolError, match=r"CKAN_URL must be an http\(s\) base URL"):
        server.CKANAPIClient(url)


# --- _make_request behaviour ---


async def test_make_request_success():
    with aioresponses() as m:
        m.get(
            action_url("status_show"), payload={"success": True, "result": {"ckan_version": "2.10"}}
        )
        result = await server.ckan_status_show()
    assert result == {"ckan_version": "2.10"}


async def test_make_request_ckan_error_raises_tool_error():
    with aioresponses() as m:
        m.get(
            action_re("package_show"),
            payload={
                "success": False,
                "error": {"message": "Not found", "__type": "Not Found Error"},
            },
        )
        with pytest.raises(ToolError, match="Not found"):
            await server.ckan_package_show(id="missing")


@pytest.mark.parametrize("status", [200, 404])
async def test_api_error_preserves_ckan_message_on_http_error(status):
    with aioresponses() as mocked:
        mocked.get(
            action_re("package_show"),
            status=status,
            payload={"success": False, "error": {"message": "Dataset not found"}},
        )
        with pytest.raises(ToolError, match="Dataset not found"):
            await server.ckan_package_show(id="missing")


@pytest.mark.parametrize(
    "status,body,content_type,message",
    [
        (502, "<h1>Gateway unavailable</h1>", "text/html", "non-JSON response.*502"),
        (200, "{broken", "application/json", "non-JSON response"),
        (200, "[]", "application/json", "invalid response envelope"),
        (200, "null", "application/json", "invalid response envelope"),
        (200, '{"success": "false"}', "application/json", "invalid response envelope"),
        (200, '{"success": true}', "application/json", "without a result"),
        (503, '{"success": true, "result": {}}', "application/json", "HTTP error 503"),
    ],
)
async def test_unexpected_response_is_a_useful_tool_error(status, body, content_type, message):
    with aioresponses() as mocked:
        mocked.get(action_url("status_show"), status=status, body=body, content_type=content_type)
        with pytest.raises(ToolError, match=message):
            await server.ckan_status_show()


@pytest.mark.parametrize("all_fields,encoded", [(True, "true"), (False, "false")])
async def test_optional_tool_encodes_boolean_query_parameters(all_fields, encoded):
    with aioresponses() as mocked:
        mocked.get(
            action_url("organization_list") + f"?all_fields={encoded}",
            payload={"success": True, "result": []},
        )
        assert await server.ckan_organization_list(all_fields=all_fields) == []


async def test_mcp_discovery_advertises_read_only_tools_and_calls_search():
    with aioresponses() as mocked:
        mocked.get(
            action_re("package_search"),
            payload={"success": True, "result": {"count": 0, "results": []}},
        )
        async with Client(server.mcp) as client:
            assert await client.ping()
            tools = await client.list_tools()
            for tool in tools:
                assert tool.annotations.readOnlyHint is True
                assert tool.annotations.destructiveHint is False
                assert tool.annotations.idempotentHint is True
                assert tool.annotations.openWorldHint is True
            result = await client.call_tool("ckan_package_search", {"q": "housing"})
            assert not result.is_error
            assert result.data == {"count": 0, "results": []}


async def test_streamable_http_initialization_and_tool_discovery():
    # Exercise the real ASGI endpoint without opening a port or exposing a server.
    app = server.mcp.http_app(stateless_http=True, json_response=True)
    headers = {"Accept": "application/json, text/event-stream"}
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            initialized = await client.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "offline-test", "version": "1.0"},
                    },
                },
            )
            assert initialized.status_code == 200
            result = initialized.json()["result"]
            assert result["serverInfo"]["name"] == "ckan-mcp-server"
            headers["MCP-Protocol-Version"] = result["protocolVersion"]
            discovered = await client.post(
                "/mcp",
                headers=headers,
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            )
            assert discovered.status_code == 200
            tools = discovered.json()["result"]["tools"]
            assert "ckan_package_search" in {t["name"] for t in tools}
            assert all(t["annotations"]["readOnlyHint"] for t in tools)


async def test_shared_client_is_reused():
    with aioresponses() as m:
        m.get(action_url("status_show"), payload={"success": True, "result": {}}, repeat=True)
        await server.ckan_status_show()
        first = server._client
        await server.ckan_status_show()
    assert server._client is first
    assert first.session is not None and not first.session.closed


# --- Response trimming ---


def test_summarize_package_drops_noise_keeps_essentials():
    summary = server._summarize_package(SAMPLE_PACKAGE)
    assert summary["id"] == "abc-123"
    assert summary["information_url"] == "https://example.test/standards"
    assert summary["organization"] == "Municipal Licensing & Standards"
    assert summary["tags"] == ["housing", "rentsafe"]
    assert summary["formats"] == ["CSV", "JSON"]
    assert "extras" not in summary
    assert "tracking_summary" not in summary
    # Resource entries are themselves trimmed.
    assert summary["resources"][0] == {
        "id": "r1",
        "name": "2024 CSV",
        "format": "CSV",
        "url": "http://x/1.csv",
        "datastore_active": True,
    }


def test_summarize_package_can_omit_resources():
    summary = server._summarize_package(SAMPLE_PACKAGE, include_resources=False)
    assert "resources" not in summary
    assert summary["formats"] == ["CSV", "JSON"]


async def test_package_search_returns_trimmed_results():
    payload = {"success": True, "result": {"count": 1, "results": [SAMPLE_PACKAGE]}}
    with aioresponses() as m:
        m.get(action_re("package_search"), payload=payload)
        result = await server.ckan_package_search(q="rentsafe")
    assert result["count"] == 1
    assert result["results"][0]["name"] == "apartment-building-evaluation"
    assert "resources" not in result["results"][0]
    assert "extras" not in result["results"][0]


async def test_package_search_full_returns_raw():
    payload = {"success": True, "result": {"count": 1, "results": [SAMPLE_PACKAGE]}}
    with aioresponses() as m:
        m.get(action_re("package_search"), payload=payload)
        result = await server.ckan_package_search(q="rentsafe", full=True)
    assert result["results"][0]["extras"][0]["key"] == "noise"


async def test_package_show_full_vs_trimmed():
    payload = {"success": True, "result": SAMPLE_PACKAGE}
    with aioresponses() as m:
        m.get(action_re("package_show"), payload=payload, repeat=True)
        trimmed = await server.ckan_package_show(id="abc-123")
        raw = await server.ckan_package_show(id="abc-123", full=True)
    assert "extras" not in trimmed
    assert "tracking_summary" in raw


# --- resource_preview fallback ---


async def test_resource_preview_falls_back_to_metadata():
    with aioresponses() as m:
        # DataStore inactive -> CKAN returns success=False -> ToolError -> fallback.
        m.post(
            action_re("datastore_search"),
            payload={"success": False, "error": {"message": "no datastore"}},
        )
        m.get(
            action_re("resource_show"),
            payload={"success": True, "result": {"id": "r1", "format": "CSV"}},
        )
        result = await server.ckan_resource_preview(resource_id="r1")
    assert result == {"id": "r1", "format": "CSV"}


# --- Tool-surface gating (CKAN_EXPOSE_ALL_TOOLS) ---


def _gating_probe(flag_value):
    """Import the server in a fresh process and report whether a gated low-value
    tool and an always-on high-value tool are registered."""
    code = (
        "import asyncio;"
        "from ckan_mcp_server import server as s;"
        "names={tool.name for tool in asyncio.run(s.mcp.list_tools())};"
        "print(len(names), 'ckan_status_show' in names, 'ckan_package_show' in names)"
    )
    env = dict(os.environ)
    env["CKAN_URL"] = "https://ckan.test"
    env.pop("CKAN_EXPOSE_ALL_TOOLS", None)
    if flag_value is not None:
        env["CKAN_EXPOSE_ALL_TOOLS"] = flag_value
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def test_low_value_tools_hidden_by_default():
    # Lean default: status_show unregistered, package_show still registered.
    assert _gating_probe(None) == "8 False True"


def test_expose_all_tools_flag_registers_low_value_tools():
    assert _gating_probe("1") == "16 True True"
