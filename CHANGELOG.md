# CHANGELOG

2026-06-21 - unreleased

* ENH: Grounded documentation tools `ckan_fetch_dataset_docs` and `ckan_search_dataset_docs` — crawl a dataset's external links (HTML + PDF, in-scope subpages) and retrieve cited passages (BM25) for hallucination-free legal/bylaw answers
* ENH: Shared HTTP session with timeouts; trimmed `package_search`/`package_show` responses (`full=True` to opt out); clear `ToolError`s; `CKAN_URL` validation
* FIX: Corrected `pyproject.toml` (cleaned dependencies, relaxed `requires-python` to 3.10, removed redundant `setup.py`)
* TST: Offline mocked pytest suite (`aioresponses`)

2025-11-26 - v1.2.0

* ENH: Migrated to FastMCP for better performance and simplified codebase
* ENH: Added new data analysis tools: `ckan_resource_preview` and `ckan_datastore_search`
* ENH: Added `ckan_dataset_schema` tool for understanding data structure
* ENH: Added context-aware prompts: `search_datasets`, `analyze_neighborhood`, `business_insights`, `educational_data`
* DOC: Updated README with IDE integration steps and developer guidelines

2025-11-12 - v1.1.0

* ENH: Added HTTP as transport protocol (MCP SSE Server Transport)
* ENH: Logging Configurable CLI Params
* ENH: BasicAuth for accessing protected CKAN sites
* ENH: Added tool to access CKAN datastore contents

2025-06-11 - v1.0.0

* ENH: Added basic tests
* ENH: std-io communication provided

2025-05-25

* ENH: initial release with basic toolset
