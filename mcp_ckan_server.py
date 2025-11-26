#!/usr/bin/env python3

import asyncio
import json
import logging
import os
import ssl
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import aiohttp
import certifi
from dotenv import load_dotenv
from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-ckan-server")

# Initialize FastMCP server
mcp = FastMCP("ckan-mcp-server")

# Default CKAN URL to Toronto if not set
CKAN_URL = os.getenv("CKAN_URL", "https://open.toronto.ca")


class CKANAPIClient:
    """CKAN API client for making HTTP requests"""

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        basic_auth_username: Optional[str] = None,
        basic_auth_password: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = None
        self.basic_auth_username = basic_auth_username
        self.basic_auth_password = basic_auth_password

    async def __aenter__(self):
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=ssl_context)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MCP-CKAN-Server/1.0",
        }
        if self.api_key:
            headers["Authorization"] = self.api_key
        return headers

    async def _make_request(
        self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to CKAN API"""
        url = urljoin(f"{self.base_url}/api/3/action/", endpoint)
        headers = self._get_headers()

        try:
            auth = None
            if self.basic_auth_username and self.basic_auth_password:
                auth = aiohttp.BasicAuth(
                    login=self.basic_auth_username, password=self.basic_auth_password
                )

            # Filter out None values from params
            if params:
                params = {k: v for k, v in params.items() if v is not None}

            async with self.session.request(
                method, url, headers=headers, json=data, params=params, auth=auth
            ) as response:
                result = await response.json()
                if not result.get("success", False):
                    error_msg = result.get("error", {})
                    # Log warning but don't crash, let the caller handle it or return the error
                    logger.warning(f"CKAN API Error: {error_msg}")
                    raise Exception(f"CKAN API Error: {error_msg}")

                return result.get("result", {})
        except aiohttp.ClientError as e:
            raise Exception(f"HTTP Error: {str(e)}")
        except Exception as e:
            raise Exception(f"Request failed: {str(e)}")


# Helper to get client
async def get_client() -> CKANAPIClient:
    api_key = os.getenv("CKAN_API_KEY")
    username = os.getenv("CKAN_BASIC_AUTH_USERNAME")
    password = os.getenv("CKAN_BASIC_AUTH_PASSWORD")
    client = CKANAPIClient(
        CKAN_URL,
        api_key=api_key,
        basic_auth_username=username,
        basic_auth_password=password,
    )
    await client.__aenter__()
    return client


# --- Tools ---

@mcp.tool()
async def ckan_package_list(limit: int = 100, offset: int = 0) -> List[str]:
    """Get list of all packages (datasets) in CKAN (unsorted)"""
    client = await get_client()
    try:
        result = await client._make_request(
            "GET", "package_list", params={"limit": limit, "offset": offset}
        )
        return result
    finally:
        await client.__aexit__(None, None, None)


@mcp.tool()
async def ckan_package_show(id: str) -> Dict[str, Any]:
    """Get details of a specific package/dataset (like dates)"""
    client = await get_client()
    try:
        result = await client._make_request("GET", "package_show", params={"id": id})
        return result
    finally:
        await client.__aexit__(None, None, None)


@mcp.tool()
async def ckan_package_search(
    q: str = "*:*",
    fq: Optional[str] = None,
    sort: Optional[str] = None,
    rows: int = 10,
    start: int = 0,
) -> Dict[str, Any]:
    """Search for packages using queries"""
    client = await get_client()
    try:
        params = {
            "q": q,
            "fq": fq,
            "sort": sort,
            "rows": rows,
            "start": start,
        }
        result = await client._make_request("GET", "package_search", params=params)
        return result
    finally:
        await client.__aexit__(None, None, None)


@mcp.tool()
async def ckan_organization_list(all_fields: bool = False) -> List[Any]:
    """Get list of all organizations"""
    client = await get_client()
    try:
        result = await client._make_request(
            "GET", "organization_list", params={"all_fields": all_fields}
        )
        return result
    finally:
        await client.__aexit__(None, None, None)


@mcp.tool()
async def ckan_organization_show(id: str, include_datasets: bool = False) -> Dict[str, Any]:
    """Get details of a specific organization"""
    client = await get_client()
    try:
        result = await client._make_request(
            "GET",
            "organization_show",
            params={"id": id, "include_datasets": include_datasets},
        )
        return result
    finally:
        await client.__aexit__(None, None, None)


@mcp.tool()
async def ckan_group_list(all_fields: bool = False) -> List[Any]:
    """Get list of all groups"""
    client = await get_client()
    try:
        result = await client._make_request(
            "GET", "group_list", params={"all_fields": all_fields}
        )
        return result
    finally:
        await client.__aexit__(None, None, None)


@mcp.tool()
async def ckan_tag_list(vocabulary_id: Optional[str] = None) -> List[Any]:
    """Get list of all tags"""
    client = await get_client()
    try:
        params = {}
        if vocabulary_id:
            params["vocabulary_id"] = vocabulary_id
        result = await client._make_request("GET", "tag_list", params=params)
        return result
    finally:
        await client.__aexit__(None, None, None)


@mcp.tool()
async def ckan_resource_show(id: str) -> Dict[str, Any]:
    """Get details of a specific resource"""
    client = await get_client()
    try:
        result = await client._make_request("GET", "resource_show", params={"id": id})
        return result
    finally:
        await client.__aexit__(None, None, None)


@mcp.tool()
async def ckan_site_read() -> Dict[str, Any]:
    """Get site information and statistics"""
    client = await get_client()
    try:
        result = await client._make_request("GET", "site_read")
        return result
    finally:
        await client.__aexit__(None, None, None)


@mcp.tool()
async def ckan_status_show() -> Dict[str, Any]:
    """Get CKAN site status and version information"""
    client = await get_client()
    try:
        result = await client._make_request("GET", "status_show")
        return result
    finally:
        await client.__aexit__(None, None, None)


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
    try:
        data = {
            "resource_id": resource_id,
            "q": q,
            "limit": limit,
            "offset": offset,
            "sort": sort,
            "fields": fields,
        }
        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}
        result = await client._make_request("POST", "datastore_search", data=data)
        return result
    finally:
        await client.__aexit__(None, None, None)


# --- Resources ---

@mcp.resource("ckan://api/docs")
def get_api_docs() -> str:
    """Official CKAN API documentation and endpoints"""
    return """
CKAN API Documentation Summary

Base URL: Configure via CKAN_URL environment variable (Default: https://open.toronto.ca)
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


# --- Prompts ---

@mcp.prompt()
def search_datasets(query: str, file_format: Optional[str] = None) -> str:
    """Help find datasets with specific criteria"""
    prompt = f"""
I am looking for datasets related to "{query}" in the City of Toronto Open Data portal.
Please help me find the most relevant packages.
1. Search for packages matching "{query}".
"""
    if file_format:
        prompt += f"2. Filter or prioritize results that contain resources in '{file_format}' format (e.g., CSV, GeoJSON).\n"
    
    prompt += "3. List the top results with their titles, IDs, and brief descriptions."
    return prompt


@mcp.prompt()
def analyze_neighborhood(neighborhood: str, topic: str) -> str:
    """Analyze a specific topic within a Toronto neighborhood"""
    return f"""
I want to analyze the neighborhood of "{neighborhood}" in Toronto regarding "{topic}".
Please guide me to the relevant data.
1. Search for datasets that contain "{topic}" and have geospatial data or neighborhood attributes.
2. Look for "Neighborhood Profiles" or census data that covers "{neighborhood}".
3. If available, show me how to filter the data for this specific neighborhood.
"""


@mcp.prompt()
def business_insights(business_type: str, location: str) -> str:
    """Get insights for opening a business in a specific location"""
    return f"""
I am planning to open a "{business_type}" business in "{location}", Toronto.
I need data to understand the market and competition.
1. Search for "Municipal Licensing and Standards" or "Business Licences" data.
2. Filter for existing businesses of type "{business_type}" in or near "{location}".
3. Find demographic data for "{location}" to understand the potential customer base.
"""


@mcp.prompt()
def educational_data(topic: str, level: str = "beginner") -> str:
    """Find datasets suitable for educational purposes"""
    prompt = f"""
I am a {level} student looking for data about "{topic}" to practice my analysis skills.
"""
    if level == "beginner":
        prompt += """
1. Please find simple, clean datasets (like CSVs) with clear column names.
2. Avoid complex geospatial formats or very large files.
3. Suggest a simple question I could answer with this data.
"""
    else:
        prompt += """
1. Find comprehensive datasets, potentially with multiple resources or time-series data.
2. It's okay if the data requires some cleaning or joining with other sets.
3. Suggest a challenging analysis or visualization project.
"""
    return prompt


if __name__ == "__main__":
    mcp.run()
