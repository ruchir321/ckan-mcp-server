
# CKAN MCP Server

A Model Context Protocol (MCP) server for the CKAN API that enables browsing and managing CKAN data portals through MCP-compatible clients.

## What is this?

This MCP server bridges the gap between manual data fetching and automated analysis. Instead of manually searching for datasets, downloading files, and figuring out schemas, this server allows AI agents to:
1.  **Discover Data**: Search and filter datasets using natural language.
2.  **Understand Structure**: Automatically retrieve schemas and field definitions.
3.  **Preview Content**: Peek into data resources without downloading the entire file.
4.  **Analyze**: Perform SQL-like queries on DataStore-enabled resources.

It is designed to be dropped into any MCP-compatible IDE or agent to instantly give it access to the wealth of open data available on CKAN portals.

### Generic core + Toronto flagship Skill

The **MCP server is portal-agnostic** — point `CKAN_URL` at any CKAN instance and the tools work.
Portal-specific *domain knowledge* (which datasets matter, how to chain searches, the grounding
discipline for citing source documents) lives separately in a **Claude Agent Skill**, keeping the
server lean and reusable. The reference Skill ships in this repo:
[`skills/toronto-open-data/`](skills/toronto-open-data/SKILL.md) for the City of Toronto Open Data
portal. Copy or symlink it into `~/.claude/skills/` to use it; author similar Skills for other
portals while reusing the same server.

## Requirements

- Python 3.13 or higher
- `uv` (recommended) or `pip`

## Installation

### Using uv (Recommended)

This project uses `uv` for dependency management. `uv` will automatically create and manage a virtual environment for you.

1.  Install `uv`:
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
2.  Sync dependencies (this creates the `.venv` folder):
    ```bash
    uv sync
    ```

### Using pip

If you prefer `pip`, you should manually create a virtual environment to avoid conflicts and to ensure the IDE integration works as expected.

1.  Create a virtual environment:
    ```bash
    python -m venv .venv
    ```
2.  Activate the virtual environment:
    -   **Linux/macOS**: `source .venv/bin/activate`
    -   **Windows**: `.venv\Scripts\activate`
3.  Install Python dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

Set the following environment variables:

-   `CKAN_URL`: The base URL of your CKAN portal (e.g. `https://demo.ckan.org`)
-   `CKAN_API_KEY`: (Optional) Your CKAN API key for write operations
-   `CKAN_DOC_ALLOWED_HOSTS`: (Optional) Comma-separated allowlist of hosts the document tools may fetch. By default only public http(s) hosts are allowed and private/loopback/link-local addresses are blocked (SSRF protection); set this to restrict fetches to specific hosts.
-   `CKAN_EXPOSE_ALL_TOOLS`: (Optional) Set to `1` to register the lower-value list/health endpoints in addition to the default lean tool set.

Example:

```bash
export CKAN_URL="https://demo.ckan.org"
export CKAN_API_KEY="your-api-key-here"
```

You can also copy `.env.example` to `.env` and set your configuration there.

## Usage

### Running the server directly

```bash
# With uv
uv run mcp_ckan_server.py

# With python
python mcp_ckan_server.py
```

### Using Docker

```bash
# Build the image
docker build -t ckan-mcp-server .

# Run with environment variables
docker run -e CKAN_URL="https://demo.ckan.org" -e CKAN_API_KEY="your-key" ckan-mcp-server
```

### Using Docker Compose

```bash
# Copy environment file and configure
cp .env.example .env
# Edit .env with your settings

# Run the server
docker-compose up
```

## IDE Integration

To use this server with a coding agent IDE (like Cursor, Windsurf, or others supporting MCP), you need to configure it as an MCP server.

### General Configuration

Most IDEs allow you to configure MCP servers in a JSON file or settings UI. Use the following command:

-   **Command**: `uv` (or `python` if you installed via pip)
-   **Args**:
    -   `run` (if using uv)
    -   `/absolute/path/to/ckan-mcp-server/mcp_ckan_server.py`
-   **Environment Variables**:
    -   `CKAN_URL`: `https://ckan0.cf.opendata.inter.prod-toronto.ca` (or your target CKAN instance)

### Example: Claude Desktop / Generic Config

Use the absolute path to the Python executable in your virtual environment to ensure all dependencies are found.

```json
{
  "mcpServers": {
    "ckan-mcp-server": {
      "command": "/absolute/path/to/ckan-mcp-server/.venv/bin/python",
      "args": [
        "/absolute/path/to/ckan-mcp-server/mcp_ckan_server.py"
      ],
      "env": {
        "CKAN_URL": "https://ckan0.cf.opendata.inter.prod-toronto.ca",
        "CKAN_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

## Available Tools

By default the server exposes a lean set of **8 high-value tools** (below). The lower-value
list/health endpoints are hidden to keep the advertised tool surface — and its per-turn context
cost — small. Set `CKAN_EXPOSE_ALL_TOOLS=1` to register the additional endpoints as well.

### Default tools

**Packages/Datasets**
-   `ckan_package_show`: Show details of a specific package (trimmed by default; `full=True` for raw)
-   `ckan_package_search`: Search for packages (trimmed by default; `full=True` for raw)
-   `ckan_dataset_schema`: Get the schema/structure of a dataset (resources and fields)

**Data Analysis**
-   `ckan_resource_preview`: Preview the content of a resource (first N rows)
-   `ckan_datastore_search`: Search and query DataStore tables (SQL-like capabilities)

**Grounded Documentation** — read the authoritative documents linked from a dataset's metadata
(`information_url` + links in `notes`), so the agent can answer legal/bylaw follow-ups from a cited
source of truth instead of guessing.
-   `ckan_fetch_dataset_docs`: Crawl a dataset's linked docs (HTML + PDF, in-scope subpages) and return them as Markdown with source URLs
-   `ckan_search_dataset_docs`: Return the top-k passages from those docs matching a query, each with its source URL and heading (citable)
-   `ckan_read_web_document`: Fetch a single URL as clean Markdown (public hosts only; see SSRF note)

### Additional tools (`CKAN_EXPOSE_ALL_TOOLS=1`)
-   `ckan_package_list`: List all packages
-   `ckan_organization_list` / `ckan_organization_show`: List / show organizations
-   `ckan_group_list`: List all groups
-   `ckan_tag_list`: List all tags
-   `ckan_resource_show`: Show resource details
-   `ckan_site_read`: Site information
-   `ckan_status_show`: Status and version information

## Resources

The server also provides the following resources:

-   `ckan://api/docs`: API documentation
-   `ckan://config`: Server configuration

## License

Mozilla Public License Version 2.0

## Authors

-   **Current Maintainer**: Ruchir Attri (ruchir.attri99@gmail.com)
-   **Original Author**: (C) 2025, Ondics GmbH, https://ondics.de
