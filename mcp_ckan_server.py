#!/usr/bin/env python3

import asyncio
import json
import logging
import os
import ssl
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import aiohttp
import certifi
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

import document_scraper

# Load environment variables
load_dotenv()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

# Configure logging (stderr; stdout must stay clean for the stdio transport)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-ckan-server")

CKAN_URL = os.getenv("CKAN_URL")

# Default network timeout (seconds) applied to all outbound HTTP requests.
DEFAULT_TIMEOUT = 30
# Max characters returned by ckan_read_web_document to avoid context overflow.
MAX_DOCUMENT_CHARS = 30000


class CKANAPIClient:
    """CKAN API client backed by a single reusable aiohttp session."""

    def __init__(
        self,
        base_url: Optional[str],
        api_key: Optional[str] = None,
        basic_auth_username: Optional[str] = None,
        basic_auth_password: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        if not base_url:
            raise ToolError(
                "CKAN_URL is not configured. Set the CKAN_URL environment variable "
                "(e.g. https://ckan0.cf.opendata.inter.prod-toronto.ca)."
            )
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.basic_auth_username = basic_auth_username
        self.basic_auth_password = basic_auth_password
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None

    async def connect(self) -> "CKANAPIClient":
        """Lazily create the shared session (idempotent)."""
        if self.session is None or self.session.closed:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            self.session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=ssl_context),
                timeout=self.timeout,
            )
        return self

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()
        self.session = None

    async def __aenter__(self):
        return await self.connect()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def _get_headers(self) -> Dict[str, str]:
        headers = {"User-Agent": "MCP-CKAN-Server"}
        if self.api_key:
            headers["Authorization"] = self.api_key
        return headers

    async def _make_request(
        self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None
    ) -> Any:
        """Make an HTTP request to the CKAN action API and return its `result`."""
        await self.connect()
        url = urljoin(f"{self.base_url}/api/3/action/", endpoint)

        auth = None
        if self.basic_auth_username and self.basic_auth_password:
            auth = aiohttp.BasicAuth(
                login=self.basic_auth_username, password=self.basic_auth_password
            )

        # Filter out None values so optional params are omitted entirely.
        if params:
            params = {k: v for k, v in params.items() if v is not None}

        try:
            async with self.session.request(
                method, url, headers=self._get_headers(), json=data, params=params, auth=auth
            ) as response:
                result = await response.json()
        except asyncio.TimeoutError as e:
            raise ToolError(
                f"CKAN request timed out after {self.timeout.total}s: {endpoint}"
            ) from e
        except aiohttp.ClientError as e:
            raise ToolError(f"Failed to reach CKAN at {url}: {e}") from e

        if not result.get("success", False):
            error_msg = result.get("error", {})
            logger.warning("CKAN API error for %s: %s", endpoint, error_msg)
            raise ToolError(f"CKAN API error on {endpoint}: {error_msg}")

        return result.get("result", {})


# --- Shared client lifecycle ---

_client: Optional[CKANAPIClient] = None


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
    "1", "true", "yes", "on",
)


def optional_tool(fn):
    """Register a tool only when CKAN_EXPOSE_ALL_TOOLS is set.

    When the flag is off, the bare function is returned unregistered, so it is not
    advertised to MCP clients (but remains importable/callable in-process)."""
    return mcp.tool()(fn) if EXPOSE_ALL_TOOLS else fn


# --- Response helpers ---

def _summarize_package(pkg: Dict[str, Any], include_resources: bool = True) -> Dict[str, Any]:
    """Trim a raw CKAN package dict down to the fields an agent usually needs.

    The raw payload includes large, rarely-useful blobs (extras, tracking, full
    resource metadata for every file) that bloat the model's context. Callers can
    request the untrimmed object via the tool's `full=True` argument.
    """
    summary: Dict[str, Any] = {
        "id": pkg.get("id"),
        "name": pkg.get("name"),
        "title": pkg.get("title"),
        "notes": pkg.get("notes"),
        "organization": (pkg.get("organization") or {}).get("title"),
        "tags": [t.get("name") for t in pkg.get("tags", [])],
        "formats": sorted(
            {r.get("format") for r in pkg.get("resources", []) if r.get("format")}
        ),
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
async def ckan_package_list(limit: int = 100, offset: int = 0) -> List[str]:
    """Get list of all packages (datasets) in CKAN (unsorted)"""
    client = await get_client()
    return await client._make_request(
        "GET", "package_list", params={"limit": limit, "offset": offset}
    )


@mcp.tool()
async def ckan_package_show(id: str, full: bool = False) -> Dict[str, Any]:
    """Get details of a specific package/dataset.

    Returns a trimmed summary by default; pass `full=True` for the raw CKAN object.
    """
    client = await get_client()
    package = await client._make_request("GET", "package_show", params={"id": id})
    return package if full else _summarize_package(package)


@mcp.tool()
async def ckan_package_search(
    q: str = "*:*",
    fq: Optional[str] = None,
    sort: Optional[str] = None,
    rows: int = 10,
    start: int = 0,
    full: bool = False,
) -> Dict[str, Any]:
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
            _summarize_package(pkg, include_resources=False)
            for pkg in result.get("results", [])
        ],
    }


@optional_tool
async def ckan_organization_list(all_fields: bool = False) -> List[Any]:
    """Get list of all organizations"""
    client = await get_client()
    return await client._make_request(
        "GET", "organization_list", params={"all_fields": all_fields}
    )


@optional_tool
async def ckan_organization_show(id: str, include_datasets: bool = False) -> Dict[str, Any]:
    """Get details of a specific organization"""
    client = await get_client()
    return await client._make_request(
        "GET",
        "organization_show",
        params={"id": id, "include_datasets": include_datasets},
    )


@optional_tool
async def ckan_group_list(all_fields: bool = False) -> List[Any]:
    """Get list of all groups"""
    client = await get_client()
    return await client._make_request(
        "GET", "group_list", params={"all_fields": all_fields}
    )


@optional_tool
async def ckan_tag_list(vocabulary_id: Optional[str] = None) -> List[Any]:
    """Get list of all tags"""
    client = await get_client()
    params = {"vocabulary_id": vocabulary_id} if vocabulary_id else {}
    return await client._make_request("GET", "tag_list", params=params)


@optional_tool
async def ckan_resource_show(id: str) -> Dict[str, Any]:
    """Get details of a specific resource"""
    client = await get_client()
    return await client._make_request("GET", "resource_show", params={"id": id})


@optional_tool
async def ckan_site_read() -> Dict[str, Any]:
    """Get site information and statistics"""
    client = await get_client()
    return await client._make_request("GET", "site_read")


@optional_tool
async def ckan_status_show() -> Dict[str, Any]:
    """Get CKAN site status and version information"""
    client = await get_client()
    return await client._make_request("GET", "status_show")


@mcp.tool()
async def ckan_datastore_search(
    resource_id: str,
    q: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    sort: Optional[str] = None,
    fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
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
async def ckan_resource_preview(resource_id: str, rows: int = 5) -> Dict[str, Any]:
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
        return await client._make_request(
            "GET", "resource_show", params={"id": resource_id}
        )


@mcp.tool()
async def ckan_read_web_document(url: str, max_chars: int = MAX_DOCUMENT_CHARS) -> str:
    """
    Fetch a webpage and return its content as clean Markdown.
    Crucial for reading 'More Information' documentation links or bylaws associated with datasets.

    Outbound requests pass an SSRF guard (`document_scraper.is_safe_url`): only public
    http(s) hosts are fetched. Set CKAN_DOC_ALLOWED_HOSTS to restrict to an allowlist.
    """
    if not document_scraper.is_safe_url(url):
        return (
            "Refused to fetch this URL: it does not resolve to a public http(s) address "
            "(SSRF guard). Set CKAN_DOC_ALLOWED_HOSTS to permit specific hosts."
        )
    timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
    headers = {"User-Agent": "MCP-CKAN-Server"}
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                html = await response.text()
    except Exception as e:
        return f"Failed to fetch or parse the document: {str(e)}"

    md = document_scraper.html_to_markdown(html)
    if len(md) > max_chars:
        return md[:max_chars] + "\n\n...[Content truncated due to length]..."
    return md


@mcp.tool()
async def ckan_dataset_schema(id: str) -> Dict[str, Any]:
    """
    Get the schema/structure of a dataset.
    Returns a summary of resources and their fields (if available in DataStore).
    """
    client = await get_client()
    package = await client._make_request("GET", "package_show", params={"id": id})

    schema_info: Dict[str, Any] = {
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

async def _dataset_doc_seeds(dataset_id: str) -> List[str]:
    """Discover the authoritative document URLs referenced by a dataset."""
    client = await get_client()
    package = await client._make_request("GET", "package_show", params={"id": dataset_id})
    seeds = document_scraper.discover_doc_urls(package)
    if not seeds:
        raise ToolError(
            f"Dataset '{dataset_id}' has no external document links "
            "(no information_url or links in notes)."
        )
    return seeds


@mcp.tool()
async def ckan_fetch_dataset_docs(
    dataset_id: str, max_pages: int = document_scraper.DEFAULT_MAX_PAGES
) -> Dict[str, Any]:
    """
    Fetch the authoritative documentation linked from a dataset's metadata
    (information_url + links in notes), crawling in-scope subpages.

    Returns each page as Markdown with its source URL, for grounded, citable
    reading. Use this for legal/bylaw follow-up questions instead of guessing.
    """
    seeds = await _dataset_doc_seeds(dataset_id)
    pages = await document_scraper.gather_dataset_pages(seeds, max_pages=max_pages)
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
    max_pages: int = document_scraper.DEFAULT_MAX_PAGES,
) -> Dict[str, Any]:
    """
    Search a dataset's linked documentation for passages relevant to `query`.

    Crawls the dataset's external links (cached per session) and returns the
    top-k matching sections, each with its source URL and heading. Answer only
    from these passages, quote verbatim, and cite the URL; if nothing is
    returned, say the source does not cover it.
    """
    seeds = await _dataset_doc_seeds(dataset_id)
    pages = await document_scraper.gather_dataset_pages(seeds, max_pages=max_pages)
    sections = document_scraper.rank_sections(pages, query, k=k)
    return {
        "dataset_id": dataset_id,
        "query": query,
        "seed_urls": seeds,
        "results": [
            {"url": s.url, "heading": s.heading, "text": s.text} for s in sections
        ],
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
    mcp.run()


if __name__ == "__main__":
    main()
