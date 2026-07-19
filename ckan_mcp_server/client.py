"""Async client for the CKAN action API."""

import logging
import ssl
from typing import Any
from urllib.parse import urljoin, urlsplit

import aiohttp
import certifi
from fastmcp.exceptions import ToolError

DEFAULT_TIMEOUT = 30

logger = logging.getLogger("mcp-ckan-server.client")


def validate_ckan_url(value: str | None) -> str:
    """Validate and normalize the configured CKAN base URL."""
    if not value:
        raise ToolError(
            "CKAN_URL is not configured. Set the CKAN_URL environment variable "
            "(e.g. https://ckan0.cf.opendata.inter.prod-toronto.ca)."
        )

    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ToolError(
            "CKAN_URL must be an http(s) base URL without credentials, query, or fragment."
        )
    return value.rstrip("/")


class CKANAPIClient:
    """CKAN API client backed by a single reusable aiohttp session."""

    def __init__(
        self,
        base_url: str | None,
        api_key: str | None = None,
        basic_auth_username: str | None = None,
        basic_auth_password: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.base_url = validate_ckan_url(base_url)
        self.api_key = api_key
        self.basic_auth_username = basic_auth_username
        self.basic_auth_password = basic_auth_password
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: aiohttp.ClientSession | None = None

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

    def _get_headers(self) -> dict[str, str]:
        headers = {"User-Agent": "MCP-CKAN-Server"}
        if self.api_key:
            headers["Authorization"] = self.api_key
        return headers

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: dict | None = None,
        params: dict | None = None,
    ) -> Any:
        """Make an HTTP request to the CKAN action API and return its result."""
        await self.connect()
        url = urljoin(f"{self.base_url}/api/3/action/", endpoint)

        auth = None
        if self.basic_auth_username and self.basic_auth_password:
            auth = aiohttp.BasicAuth(
                login=self.basic_auth_username,
                password=self.basic_auth_password,
            )
        if params:
            params = {key: value for key, value in params.items() if value is not None}

        try:
            assert self.session is not None
            async with self.session.request(
                method,
                url,
                headers=self._get_headers(),
                json=data,
                params=params,
                auth=auth,
            ) as response:
                result = await response.json()
        except TimeoutError as exc:
            raise ToolError(
                f"CKAN request timed out after {self.timeout.total}s: {endpoint}"
            ) from exc
        except aiohttp.ClientError as exc:
            raise ToolError(f"Failed to reach configured CKAN endpoint: {exc}") from exc

        if not result.get("success", False):
            error = result.get("error", {})
            logger.warning("CKAN API error for %s: %s", endpoint, error)
            raise ToolError(f"CKAN API error on {endpoint}: {error}")
        return result.get("result", {})
