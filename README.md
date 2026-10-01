# CKAN MCP Server

Connect ChatGPT to CKAN open data portals so you can find datasets, inspect their
fields, query records, and answer follow-up questions using linked source documents.
The included Toronto Open Data skill guides that workflow for City of Toronto data.
The server is read-only: it does not create, update, or delete portal data.

## Add it to ChatGPT

Once you have this repository locally, follow the steps below to connect it to
ChatGPT. You need ChatGPT developer-mode access; packaging the Toronto workflow
also needs ChatGPT Work with Plugin Creator available in the desktop app.
This repository provides the server, skill, and setup helpers, without a hosted
endpoint or credentials. You create your own connection and plugin; there is
no ready-made plugin to install from this repository.

### 1. Prepare the local server

Install Python 3.13 or higher and [`uv`](https://docs.astral.sh/uv/), then run this
from the repository root:

```bash
uv sync --all-extras --frozen
```

This creates the virtual environment used by the tunnel helper. Toronto public
data needs no CKAN API key. See [server configuration](#configuration) if you
want to use a different portal.

### 2. Make the server reachable from ChatGPT

For a local server, use a dedicated
[Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).
Create it in Platform tunnel settings, associate it with your ChatGPT workspace,
and obtain a runtime API key and the `tunnel-client` binary. Tunnel permissions
and ChatGPT developer-mode access are separate prerequisites.

Follow the [Linux private tunnel setup](#user-operated-private-tunnel-handoff-linux)
below. The helper launches this server over stdio and keeps credentials in private,
Git-ignored files. Choose the connection method and authorize credential and
workspace access before starting. Keep the tunnel running while using ChatGPT.
If you already operate an HTTPS Streamable HTTP endpoint, you can connect that instead;
review the [transport and access guidance](#development-and-transport-validation).

### 3. Add the connection in ChatGPT

Enable Developer mode in **Settings → Security and login**, then open the
ChatGPT Plugins page and select **+**. For the private route, choose **Tunnel**
under Connection and select your dedicated CKAN tunnel. For a hosted server,
supply its MCP URL and connection details. Finish registration and test that
ChatGPT can discover the server's tools.

If your tunnel is missing, check its workspace association and your Tunnels
Read + Use permission. Menu labels and feature availability can vary by account;
follow the linked official documentation if your interface differs.

### 4. Add the Toronto workflow with Plugin Creator

After registration, copy the connection's technical ID from its browser URL
(the ID starts with `plugin_asdk_app`). In ChatGPT Work, invoke `@plugin-creator`
and ask it to bundle that connection with
[`skills/toronto-open-data/`](skills/toronto-open-data/SKILL.md).
For example, replace the placeholder below with your actual connection ID and
provide access to this repository's skill folder:

> @plugin-creator Create a Toronto Open Data plugin using my registered MCP
> connection CONNECTION_ID and this repository's Toronto skill. Include a
> personal marketplace entry for testing.

Review the generated connection mapping, install from your local source in the
Plugins Directory, and test in a new chat. See the
[official packaging workflow](https://developers.openai.com/plugins/build/plugins)
for details. This creates a plugin for your own testing; public directory
submission is a separate process.

### 5. Try it in a chat

With the connection available, try:

- “Find Toronto apartment building evaluation datasets and show me their fields.”
- “Preview a resource, then filter records by an exact field value.”
- “Read the documentation linked to this dataset and cite the source for your answer.”

The server can query records when a resource uses CKAN DataStore. Other resources
return metadata in previews. Document answers depend on the sources linked from
the dataset; ask ChatGPT to cite those sources and say when they do not cover a
question. See [available tools](#available-tools) for the full capabilities.

The connection and packaging steps above were checked against official OpenAI
documentation on 2026-10-01. They do not establish that setup has succeeded in
your account; verify discovery and a real tool call after connecting.

## Server and developer reference

The sections below cover other MCP clients, configuration, tools, validation,
and deployment. ChatGPT setup above does not require a Codex session or editing
client configuration JSON.

### Reusing the server with other portals

The **MCP server is portal-agnostic** — point `CKAN_URL` at any CKAN instance and the tools work.
Portal-specific *domain knowledge* (which datasets matter, how to chain searches, the grounding
discipline for citing source documents) lives separately in an **Agent Skill**, keeping the
server lean and reusable. The reference Skill ships in this repo:
[`skills/toronto-open-data/`](skills/toronto-open-data/SKILL.md) for the City of Toronto Open Data
portal. Install it in your client’s supported skills location, or bundle it using Plugin Creator
(see the ChatGPT setup above). Author similar skills for other portals while reusing the same server.

## Requirements

- Python 3.13 or higher
- [`uv`](https://docs.astral.sh/uv/)

## Installation

This project uses `uv` for dependency management. `uv` will automatically create and manage a virtual environment for you.

1.  Install `uv`:
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
2.  Sync dependencies (this creates the `.venv` folder):
    ```bash
    uv sync --all-extras --frozen
    ```

## Configuration

Set the following environment variables:

-   `CKAN_URL`: The base URL of your CKAN portal (e.g. `https://demo.ckan.org`)
-   `CKAN_API_KEY`: (Optional) A CKAN API key for reading protected datasets; not needed for Toronto public data
-   `CKAN_DOC_ALLOWED_HOSTS`: (Optional) Comma-separated allowlist of hosts the document tools may fetch. By default only public http(s) hosts are allowed and private/loopback/link-local addresses are blocked (SSRF protection); set this to restrict fetches to specific hosts.
-   `CKAN_EXPOSE_ALL_TOOLS`: (Optional) Set to `1` to register the lower-value list/health endpoints in addition to the default lean tool set.

Example:

```bash
export CKAN_URL="https://demo.ckan.org"
```

The server reads the process environment only; it does not implicitly load dotenv files.

## Running the server in other environments

### Running the server directly

```bash
CKAN_URL=https://ckan0.cf.opendata.inter.prod-toronto.ca uv run --frozen ckan-mcp-server
```

### Using Docker

```bash
# Build the image
docker build -t ckan-mcp-server .

# Run with environment variables
docker run --rm -i -e CKAN_URL="https://demo.ckan.org" ckan-mcp-server
```

### Using Docker Compose

```bash
# Run an interactive stdio instance (only when an existing instance is not running)
CKAN_URL=https://demo.ckan.org docker compose --profile stdio run --rm ckan-mcp-server-stdio
```

## Optional IDE and desktop client integration

To use this server with a coding agent IDE (like Cursor, Windsurf, or others supporting MCP), you need to configure it as an MCP server.

### General Configuration

Most IDEs allow you to configure MCP servers in a JSON file or settings UI. Use the following command:

-   **Command**: `uv`
-   **Args**:
    -   `run`
    -   `--directory`
    -   `/absolute/path/to/ckan-mcp-server`
    -   `ckan-mcp-server`
-   **Environment Variables**:
    -   `CKAN_URL`: `https://ckan0.cf.opendata.inter.prod-toronto.ca` (or your target CKAN instance)

### Example: Claude Desktop / Generic Config

Point `uv` at the project directory so it uses the locked environment.

```json
{
  "mcpServers": {
    "ckan-mcp-server": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/ckan-mcp-server",
        "ckan-mcp-server"
      ],
      "env": {
        "CKAN_URL": "https://ckan0.cf.opendata.inter.prod-toronto.ca"
      }
    }
  }
}
```

### Optional Codex packaging

If you prefer to create the plugin in Codex, invoke `$plugin-creator` with the
registered connection ID and the Toronto skill folder. Follow the same
[packaging workflow](https://developers.openai.com/plugins/build/plugins) and
review the generated mapping before installation.

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
-   `ckan_resource_preview`: Preview DataStore rows; return resource metadata when DataStore is unavailable (no CSV download fallback)
-   `ckan_datastore_search`: Search DataStore records with text queries, exact field filters, field selection, sorting and pagination (no arbitrary SQL)

DataStore `q` uses the portal's full-text index. A value visible in a preview may
return no text-search matches when the index does not cover that field. Use
`filters={"FIELD_NAME": "value"}` for exact field matches, with multiple fields
combined using AND; a list matches any listed value within a field. Match the
schema's value types and use `limit=0` to request a count without rows. Keep `q`
omitted when only exact filters are needed. Filtering
preserves CKAN's returned records and counts; it does not aggregate or deduplicate
rows. See the [CKAN DataStore search reference](https://docs.ckan.org/en/2.11/maintaining/datastore.html#ckanext.datastore.logic.action.datastore_search).

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

All tools advertise `readOnlyHint=true`, `destructiveHint=false`,
`idempotentHint=true` and `openWorldHint=true`. These describe tool behavior;
they do not provide authentication or enforce permissions.

## Resources

The server also provides the following resources:

-   `ckan://api/docs`: API documentation
-   `ckan://config`: Server configuration

## Development and transport validation

```bash
uv sync --all-extras --frozen
make check
```

The default suite is offline and includes MCP discovery/calls and Streamable HTTP
initialization through an in-process ASGI client. No listening socket is opened.
`tests/test_web_document_tool.py` is a legacy manual live-network probe, excluded
from the offline suite; passing offline tests does not establish live portal health.

The default transport is stdio. `MCP_TRANSPORT=http` selects Streamable HTTP at
`/mcp`; `MCP_HOST` defaults to `127.0.0.1` and `MCP_PORT` to `8000`.
`MCP_TRANSPORT=sse` remains available for legacy clients. Check running services
and choose an unused port before starting HTTP. The Compose HTTP profile publishes
port 8000 on all host interfaces and has no application authentication; review its
binding and access controls before choosing that profile.

## Dependency maintenance

Direct runtime and development requirements were checked against official PyPI
metadata on 2026-09-30. Compatible updates applied:

| Package | Previous lock | Updated lock | Upstream reference |
| --- | --- | --- | --- |
| aiohttp | 3.14.1 | 3.14.3 | [Release notes](https://github.com/aio-libs/aiohttp/releases/tag/v3.14.3) |
| FastMCP / fastmcp-slim | 3.4.4 | 3.4.7 | [Release notes](https://github.com/PrefectHQ/fastmcp/releases/tag/v3.4.7) |
| certifi | 2026.6.17 | 2026.7.22 | [PyPI release](https://pypi.org/project/certifi/2026.7.22/) |
| pypdf | 6.14.2 | 6.19.0 | [Release notes](https://github.com/py-pdf/pypdf/releases/tag/6.19.0) |

The other direct packages were already current within their declared ranges.
[FastMCP 4.0.10](https://pypi.org/project/fastmcp/4.0.10/) and
[Ruff 0.16.9](https://pypi.org/project/ruff/0.16.9/) were available outside those
ranges. Their major/runtime and lint-policy migrations are deferred to separate
changes. The test-only aiohttp/aioresponses compatibility shim remains necessary
with aioresponses 0.7.9; it does not alter production sessions.

## Private tunnel and service reference

Run the following commands from the repository root.

### User-operated private tunnel handoff (Linux)

With the existing tunnel-client binary, run this yourself in an ordinary terminal,
not an agent-captured terminal. Replace the binary path with its installed location:

```bash
.venv/bin/python scripts/start_private_tunnel.py --binary /path/to/tunnel-client
```

The helper asks for a **dedicated CKAN tunnel ID**, your `SAVE` confirmation, and
then the runtime API key through a hidden prompt. It saves the key under
`.local-tunnel/runtime-key` with mode 0600 inside a mode-0700 directory. The
separate `ckan` profile references the file; the key is never placed in command
arguments, shell history, or the profile itself. Private state is Git-ignored.
The helper does not read or reuse another service's environment or credentials.

A second `CONNECT` confirmation authorizes doctor and foreground startup. Doctor
failure stops the procedure; resolve the reported permission/configuration issue
before retrying. Keep the terminal open. Ctrl-C stops this CKAN process. No system
service or ChatGPT app is installed. A process lock prevents a duplicate launch
through this helper. Restart the saved CKAN profile using the same command with
`--resume`; this requires `CONNECT` again and does not prompt for or read the key
in the Python helper (tunnel-client resolves its file reference).

The health listener uses an available loopback port recorded in
`.local-tunnel/health.url`, with its PID in `.local-tunnel/tunnel.pid`. After the
user confirms setup is complete, verify readiness using the installed binary:

```bash
/path/to/tunnel-client health --url-file .local-tunnel/health.url \
  --pid-file .local-tunnel/tunnel.pid --require-control-plane-poll --json
```

Agent handoff boundary: do not run this helper's credential-entry flow through
agent tools, read the credential file, or inspect the user's clipboard/Notepad.
User-operated saving and connection confirmation must precede agent readiness
checks. Verify any existing independent tunnel remains healthy separately.

### Persistent user service

`deploy/ckan-mcp-tunnel.service.in` is the native systemd template. Render
`@REPO_ROOT@` and `@TUNNEL_BINARY@` to reviewed absolute paths, keep the result
owner-only at `.local-tunnel/ckan-mcp-tunnel.service`, and validate it with
`systemd-analyze --user verify` before activation. The saved profile and key file
must already exist from the user-operated handoff. The unit contains a credential
file reference only and clears inherited environment overrides. Never put key
values in a unit, command argument, log, or Git.

This service supervises native tunnel-client, which launches CKAN's virtualenv
stdio server. Docker is not involved. It restarts after exit with a 10-second
delay, stops its own process group, and uses the same CKAN lock as the terminal
helper. Lock contention exits without a restart loop. Loopback health ports are
allocated automatically, independently of other tunnels.

**User activation:** review the prepared unit, then press Ctrl-C in the terminal
running the foreground CKAN tunnel. Do not stop other tunnels. From this repository,
run the following yourself to authorize persistent access with the saved key:

```bash
flock --nonblock .local-tunnel/run.lock true && \
  systemctl --user enable --now "$PWD/.local-tunnel/ckan-mcp-tunnel.service"
```

The first command refuses activation while the foreground helper holds the lock.
The second links/enables this separate user unit and starts it immediately. It
will subsequently start with the user manager; boot startup without a login needs
user lingering to be enabled (check it separately; do not change it implicitly).
Keep the checkout and its private state in place while this service is enabled.

After user-confirmed activation, verify `is-enabled`, `is-active`, `Restart`,
`RestartUSec`, `MainPID`, and `NRestarts` with `systemctl --user`, then use the
health command above to verify a successful control-plane poll. Separately verify
any existing tunnel's health. Local readiness does not establish that a ChatGPT
connection can discover tools; verify that connection separately.

To stop and remove autostart yourself:

```bash
systemctl --user disable --now ckan-mcp-tunnel.service
```

## Read features proposed for a later decision

These are proposals, not additional registered tools:

- **Bounded file previews:** sample CSV/GeoJSON when DataStore is unavailable.
  Agree on byte/row limits, supported formats and provenance before adding downloads.
- **Dataset quality summaries:** report freshness, licensing, field completeness
  and retired-dataset warnings, distinguishing metadata claims from measured data.

Keep the default eight-tool surface small; prefer an optional parameter or
opt-in capability where appropriate. Arbitrary SQL, bulk exports and write tools
are outside this maintenance change.

## License

Mozilla Public License Version 2.0

## Authors

-   **Current Maintainer**: Ruchir Attri (ruchir.attri99@gmail.com)
-   **Original Author**: (C) 2025, Ondics GmbH, https://ondics.de
