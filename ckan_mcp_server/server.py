"""FastMCP tool surface and process lifecycle."""

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from . import documents
from .client import CKANAPIClient

# Configure logging (stderr; stdout must stay clean for the stdio transport)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-ckan-server")

CKAN_URL = os.getenv("CKAN_URL")

# Max characters returned by ckan_read_web_document to avoid context overflow.
MAX_DOCUMENT_CHARS = 30000


# --- Shared client lifecycle ---

_client: CKANAPIClient | None = None


async def get_client() -> CKANAPIClient:
    """Return the process-wide CKAN client, creating it on first use."""
    global _client
    if _client is None:
        _client = CKANAPIClient(
            CKAN_URL,
            api_key=os.getenv("CKAN_API_KEY"),
            basic_auth_username=os.getenv("CKAN_BASIC_AUTH_USERNAME"),
            basic_auth_password=os.getenv("CKAN_BASIC_AUTH_PASSWORD"),
        )
    await _client.connect()
    return _client


@asynccontextmanager
async def lifespan(_server: FastMCP):
    """Close the shared HTTP session cleanly on server shutdown."""
    try:
        yield
    finally:
        if _client is not None:
            await _client.close()


# Initialize FastMCP server
mcp = FastMCP("ckan-mcp-server", lifespan=lifespan)


# Low-value list/health endpoints are hidden by default to keep the advertised tool
# surface (and the per-turn context cost of its schemas) lean. Set CKAN_EXPOSE_ALL_TOOLS=1
# to register them as well.
EXPOSE_ALL_TOOLS = os.getenv("CKAN_EXPOSE_ALL_TOOLS", "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)


def optional_tool(fn):
    """Register a tool only when CKAN_EXPOSE_ALL_TOOLS is set.

    When the flag is off, the bare function is returned unregistered, so it is not
    advertised to MCP clients (but remains importable/callable in-process)."""
    return mcp.tool()(fn) if EXPOSE_ALL_TOOLS else fn


# --- Response helpers ---


def _summarize_package(pkg: dict[str, Any], include_resources: bool = True) -> dict[str, Any]:
    """Trim a raw CKAN package dict down to the fields an agent usually needs.

    The raw payload includes large, rarely-useful blobs (extras, tracking, full
    resource metadata for every file) that bloat the model's context. Callers can
    request the untrimmed object via the tool's `full=True` argument.
    """
    summary: dict[str, Any] = {
        "id": pkg.get("id"),
        "name": pkg.get("name"),
        "title": pkg.get("title"),
        "notes": pkg.get("notes"),
        "organization": (pkg.get("organization") or {}).get("title"),
        "tags": [t.get("name") for t in pkg.get("tags", [])],
        "formats": sorted({r.get("format") for r in pkg.get("resources", []) if r.get("format")}),
        "num_resources": pkg.get("num_resources"),
        "metadata_modified": pkg.get("metadata_modified"),
    }
    if include_resources:
        summary["resources"] = [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "format": r.get("format"),
                "url": r.get("url"),
                "datastore_active": r.get("datastore_active"),
            }
            for r in pkg.get("resources", [])
        ]
    return summary


# --- Tools ---


@optional_tool
async def ckan_package_list(limit: int = 100, offset: int = 0) -> list[str]:
    """Get list of all packages (datasets) in CKAN (unsorted)"""
    client = await get_client()
    return await client._make_request(
        "GET", "package_list", params={"limit": limit, "offset": offset}
    )


@mcp.tool()
async def ckan_package_show(id: str, full: bool = False) -> dict[str, Any]:
    """Get details of a specific package/dataset.

    Returns a trimmed summary by default; pass `full=True` for the raw CKAN object.
    """
    client = await get_client()
    package = await client._make_request("GET", "package_show", params={"id": id})
    return package if full else _summarize_package(package)


@mcp.tool()
async def ckan_package_search(
    q: str = "*:*",
    fq: str | None = None,
    sort: str | None = None,
    rows: int = 10,
    start: int = 0,
    full: bool = False,
) -> dict[str, Any]:
    """Search for packages using queries.

    Returns `{count, results}` with trimmed package summaries by default; pass
    `full=True` for the raw CKAN response.
    """
    client = await get_client()
    params = {"q": q, "fq": fq, "sort": sort, "rows": rows, "start": start}
    result = await client._make_request("GET", "package_search", params=params)
    if full:
        return result
    return {
        "count": result.get("count"),
        "results": [
            _summarize_package(pkg, include_resources=False) for pkg in result.get("results", [])
        ],
    }


@optional_tool
async def ckan_organization_list(all_fields: bool = False) -> list[Any]:
    """Get list of all organizations"""
    client = await get_client()
    return await client._make_request("GET", "organization_list", params={"all_fields": all_fields})


@optional_tool
async def ckan_organization_show(id: str, include_datasets: bool = False) -> dict[str, Any]:
    """Get details of a specific organization"""
    client = await get_client()
    return await client._make_request(
        "GET",
        "organization_show",
        params={"id": id, "include_datasets": include_datasets},
    )


@optional_tool
async def ckan_group_list(all_fields: bool = False) -> list[Any]:
    """Get list of all groups"""
    client = await get_client()
    return await client._make_request("GET", "group_list", params={"all_fields": all_fields})


@optional_tool
async def ckan_tag_list(vocabulary_id: str | None = None) -> list[Any]:
    """Get list of all tags"""
    client = await get_client()
    params = {"vocabulary_id": vocabulary_id} if vocabulary_id else {}
    return await client._make_request("GET", "tag_list", params=params)


@optional_tool
async def ckan_resource_show(id: str) -> dict[str, Any]:
    """Get details of a specific resource"""
    client = await get_client()
    return await client._make_request("GET", "resource_show", params={"id": id})


@optional_tool
async def ckan_site_read() -> dict[str, Any]:
    """Get site information and statistics"""
    client = await get_client()
    return await client._make_request("GET", "site_read")


@optional_tool
async def ckan_status_show() -> dict[str, Any]:
    """Get CKAN site status and version information"""
    client = await get_client()
    return await client._make_request("GET", "status_show")


@mcp.tool()
async def ckan_datastore_search(
    resource_id: str,
    q: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    sort: str | None = None,
    fields: list[str] | None = None,
) -> dict[str, Any]:
    """Search records in a dataset"""
    client = await get_client()
    data = {
        "resource_id": resource_id,
        "q": q,
        "limit": limit,
        "offset": offset,
        "sort": sort,
        "fields": fields,
    }
    # Remove None values so optional params are omitted.
    data = {k: v for k, v in data.items() if v is not None}
    return await client._make_request("POST", "datastore_search", data=data)


# --- Data Analysis Tools ---


@mcp.tool()
async def ckan_resource_preview(resource_id: str, rows: int = 5) -> dict[str, Any]:
    """
    Preview the content of a resource.
    Tries to fetch data via DataStore first, falling back to resource metadata.
    """
    client = await get_client()
    try:
        return await client._make_request(
            "POST", "datastore_search", data={"resource_id": resource_id, "limit": rows}
        )
    except ToolError:
        # DataStore not active for this resource; return its metadata instead.
        # A fuller implementation might download and parse the CSV here.
        return await client._make_request("GET", "resource_show", params={"id": resource_id})


@mcp.tool()
async def ckan_read_web_document(url: str, max_chars: int = MAX_DOCUMENT_CHARS) -> str:
    """
    Fetch a webpage and return its content as clean Markdown.
    Crucial for reading 'More Information' documentation links or bylaws associated with datasets.

    Outbound requests pass an SSRF guard (`documents.is_safe_url`): only public
    http(s) hosts are fetched. Set CKAN_DOC_ALLOWED_HOSTS to restrict to an allowlist.
    """
    if not documents.is_safe_url(url):
        return (
            "Refused to fetch this URL: it does not resolve to a public http(s) address "
            "(SSRF guard). CKAN_DOC_ALLOWED_HOSTS can further restrict public hosts."
        )
    try:
        async with documents.create_safe_session() as session:
            content_type, body = await documents.fetch_document(session, url)
        if content_type == "pdf":
            md = documents.pdf_to_text(body)
        else:
            md = documents.html_to_markdown(body)
    except Exception as exc:
        return f"Failed to fetch or parse the document: {exc}"

    limit = max(1, min(max_chars, MAX_DOCUMENT_CHARS))
    if len(md) > limit:
        return md[:limit] + "\n\n...[Content truncated due to length]..."
    return md


@mcp.tool()
async def ckan_dataset_schema(id: str) -> dict[str, Any]:
    """
    Get the schema/structure of a dataset.
    Returns a summary of resources and their fields (if available in DataStore).
    """
    client = await get_client()
    package = await client._make_request("GET", "package_show", params={"id": id})

    schema_info: dict[str, Any] = {
        "dataset_title": package.get("title"),
        "resources": [],
    }

    for resource in package.get("resources", []):
        res_info = {
            "name": resource.get("name"),
            "format": resource.get("format"),
            "id": resource.get("id"),
            "fields": "Unknown (not in DataStore)",
        }

        if resource.get("datastore_active"):
            try:
                # Fetch zero rows just to read field definitions.
                ds_data = await client._make_request(
                    "POST",
                    "datastore_search",
                    data={"resource_id": resource.get("id"), "limit": 0},
                )
                res_info["fields"] = ds_data.get("fields", [])
            except ToolError:
                pass

        schema_info["resources"].append(res_info)

    return schema_info


# --- Grounded Document Knowledge ---


async def _dataset_doc_seeds(dataset_id: str) -> list[str]:
    """Discover the authoritative document URLs referenced by a dataset."""
    client = await get_client()
    package = await client._make_request("GET", "package_show", params={"id": dataset_id})
    seeds = documents.discover_doc_urls(package)
    if not seeds:
        raise ToolError(
            f"Dataset '{dataset_id}' has no external document links "
            "(no information_url or links in notes)."
        )
    return seeds


@mcp.tool()
async def ckan_fetch_dataset_docs(
    dataset_id: str, max_pages: int = documents.DEFAULT_MAX_PAGES
) -> dict[str, Any]:
    """
    Fetch the authoritative documentation linked from a dataset's metadata
    (information_url + links in notes), crawling in-scope subpages.

    Returns each page as Markdown with its source URL, for grounded, citable
    reading. Use this for legal/bylaw follow-up questions instead of guessing.
    """
    seeds = await _dataset_doc_seeds(dataset_id)
    pages = await documents.gather_dataset_pages(seeds, max_pages=max_pages)
    return {
        "dataset_id": dataset_id,
        "seed_urls": seeds,
        "pages": [
            {"url": p.url, "title": p.title, "content_type": p.content_type, "text": p.text}
            for p in pages
        ],
    }


@mcp.tool()
async def ckan_search_dataset_docs(
    dataset_id: str,
    query: str,
    k: int = 5,
    max_pages: int = documents.DEFAULT_MAX_PAGES,
) -> dict[str, Any]:
    """
    Search a dataset's linked documentation for passages relevant to `query`.

    Crawls the dataset's external links (cached per session) and returns the
    top-k matching sections, each with its source URL and heading. Answer only
    from these passages, quote verbatim, and cite the URL; if nothing is
    returned, say the source does not cover it.
    """
    seeds = await _dataset_doc_seeds(dataset_id)
    pages = await documents.gather_dataset_pages(seeds, max_pages=max_pages)
    sections = documents.rank_sections(pages, query, k=k)
    return {
        "dataset_id": dataset_id,
        "query": query,
        "seed_urls": seeds,
        "results": [{"url": s.url, "heading": s.heading, "text": s.text} for s in sections],
    }


# --- Resources ---


@mcp.resource("ckan://api/docs")
def get_api_docs() -> str:
    """Official CKAN API documentation and endpoints"""
    return """
CKAN API Documentation Summary

Base URL: Configure via CKAN_URL environment variable (Default: https://ckan0.cf.opendata.inter.prod-toronto.ca)
API Version: 3

Key Endpoints:
- package_list: Get all packages/datasets
- package_show: Get package details
- package_search: Search packages
- organization_list: Get all organizations  
- organization_show: Get organization details
- group_list: Get all groups
- tag_list: Get all tags
- resource_show: Get resource details
- site_read: Get site information
- status_show: Get site status

Authentication: Set CKAN_API_KEY environment variable for write operations

Full documentation: https://docs.ckan.org/en/latest/api/
    """


@mcp.resource("ckan://config")
def get_config() -> str:
    """Current CKAN server configuration and connection details"""
    return json.dumps(
        {
            "base_url": CKAN_URL,
            "api_key_configured": bool(os.getenv("CKAN_API_KEY")),
        },
        indent=2,
    )


def main() -> None:
    """Console-script / module entry point."""
    transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "stdio":
        mcp.run(transport="stdio", show_banner=False)
        return
    if transport not in {"http", "sse"}:
        raise ValueError("MCP_TRANSPORT must be one of: stdio, http, sse")
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8000"))
    mcp.run(transport=transport, host=host, port=port, show_banner=False)


if __name__ == "__main__":
    main()
