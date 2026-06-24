"""Offline tests for the CKAN client and tools (HTTP mocked with aioresponses)."""

import os
import subprocess
import sys

import pytest
from aioresponses import aioresponses
from fastmcp.exceptions import ToolError

import mcp_ckan_server as server
from conftest import action_re, action_url

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# A representative raw CKAN package, with noisy fields (extras, tracking) that
# the summarizer is expected to drop.
SAMPLE_PACKAGE = {
    "id": "abc-123",
    "name": "apartment-building-evaluation",
    "title": "Apartment Building Evaluation",
    "notes": "Evaluation scores for registered apartment buildings.",
    "num_resources": 2,
    "metadata_modified": "2025-01-02T00:00:00",
    "organization": {"title": "Municipal Licensing & Standards", "id": "org-1"},
    "tags": [{"name": "housing"}, {"name": "rentsafe"}],
    "extras": [{"key": "noise", "value": "x" * 5000}],
    "tracking_summary": {"total": 999, "recent": 12},
    "resources": [
        {"id": "r1", "name": "2024 CSV", "format": "CSV", "url": "http://x/1.csv",
         "datastore_active": True, "size": 12345},
        {"id": "r2", "name": "2024 JSON", "format": "JSON", "url": "http://x/1.json",
         "datastore_active": False},
    ],
}


# --- Config validation ---

def test_missing_url_raises_tool_error():
    with pytest.raises(ToolError, match="CKAN_URL is not configured"):
        server.CKANAPIClient(None)


# --- _make_request behaviour ---

async def test_make_request_success():
    with aioresponses() as m:
        m.get(action_url("status_show"), payload={"success": True, "result": {"ckan_version": "2.10"}})
        result = await server.ckan_status_show.fn()
    assert result == {"ckan_version": "2.10"}


async def test_make_request_ckan_error_raises_tool_error():
    with aioresponses() as m:
        m.get(
            action_re("package_show"),
            payload={"success": False, "error": {"message": "Not found", "__type": "Not Found Error"}},
        )
        with pytest.raises(ToolError, match="Not found"):
            await server.ckan_package_show.fn(id="missing")


async def test_shared_client_is_reused():
    with aioresponses() as m:
        m.get(action_url("status_show"), payload={"success": True, "result": {}}, repeat=True)
        await server.ckan_status_show.fn()
        first = server._client
        await server.ckan_status_show.fn()
    assert server._client is first
    assert first.session is not None and not first.session.closed


# --- Response trimming ---

def test_summarize_package_drops_noise_keeps_essentials():
    summary = server._summarize_package(SAMPLE_PACKAGE)
    assert summary["id"] == "abc-123"
    assert summary["organization"] == "Municipal Licensing & Standards"
    assert summary["tags"] == ["housing", "rentsafe"]
    assert summary["formats"] == ["CSV", "JSON"]
    assert "extras" not in summary
    assert "tracking_summary" not in summary
    # Resource entries are themselves trimmed.
    assert summary["resources"][0] == {
        "id": "r1", "name": "2024 CSV", "format": "CSV",
        "url": "http://x/1.csv", "datastore_active": True,
    }


def test_summarize_package_can_omit_resources():
    summary = server._summarize_package(SAMPLE_PACKAGE, include_resources=False)
    assert "resources" not in summary
    assert summary["formats"] == ["CSV", "JSON"]


async def test_package_search_returns_trimmed_results():
    payload = {"success": True, "result": {"count": 1, "results": [SAMPLE_PACKAGE]}}
    with aioresponses() as m:
        m.get(action_re("package_search"), payload=payload)
        result = await server.ckan_package_search.fn(q="rentsafe")
    assert result["count"] == 1
    assert result["results"][0]["name"] == "apartment-building-evaluation"
    assert "resources" not in result["results"][0]
    assert "extras" not in result["results"][0]


async def test_package_search_full_returns_raw():
    payload = {"success": True, "result": {"count": 1, "results": [SAMPLE_PACKAGE]}}
    with aioresponses() as m:
        m.get(action_re("package_search"), payload=payload)
        result = await server.ckan_package_search.fn(q="rentsafe", full=True)
    assert result["results"][0]["extras"][0]["key"] == "noise"


async def test_package_show_full_vs_trimmed():
    payload = {"success": True, "result": SAMPLE_PACKAGE}
    with aioresponses() as m:
        m.get(action_re("package_show"), payload=payload, repeat=True)
        trimmed = await server.ckan_package_show.fn(id="abc-123")
        raw = await server.ckan_package_show.fn(id="abc-123", full=True)
    assert "extras" not in trimmed
    assert "tracking_summary" in raw


# --- resource_preview fallback ---

async def test_resource_preview_falls_back_to_metadata():
    with aioresponses() as m:
        # DataStore inactive -> CKAN returns success=False -> ToolError -> fallback.
        m.post(action_re("datastore_search"), payload={"success": False, "error": {"message": "no datastore"}})
        m.get(action_re("resource_show"), payload={"success": True, "result": {"id": "r1", "format": "CSV"}})
        result = await server.ckan_resource_preview.fn(resource_id="r1")
    assert result == {"id": "r1", "format": "CSV"}


# --- Tool-surface gating (CKAN_EXPOSE_ALL_TOOLS) ---

def _gating_probe(flag_value):
    """Import the server in a fresh process and report whether a gated low-value
    tool and an always-on high-value tool are registered (have a `.fn`)."""
    code = (
        "import mcp_ckan_server as s;"
        "print(hasattr(s.ckan_status_show, 'fn'), hasattr(s.ckan_package_show, 'fn'))"
    )
    env = dict(os.environ)
    env["CKAN_URL"] = "https://ckan.test"
    env.pop("CKAN_EXPOSE_ALL_TOOLS", None)
    if flag_value is not None:
        env["CKAN_EXPOSE_ALL_TOOLS"] = flag_value
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, env=env, cwd=REPO_ROOT,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def test_low_value_tools_hidden_by_default():
    # Lean default: status_show unregistered, package_show still registered.
    assert _gating_probe(None) == "False True"


def test_expose_all_tools_flag_registers_low_value_tools():
    assert _gating_probe("1") == "True True"
