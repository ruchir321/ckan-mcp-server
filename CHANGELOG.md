# CHANGELOG

2026-06-21 - unreleased

* SEC: SSRF guard on the document tools — `ckan_read_web_document` and the crawler now fetch only public http(s) hosts; private/loopback/link-local addresses (e.g. cloud metadata `169.254.169.254`) are blocked. Opt-in `CKAN_DOC_ALLOWED_HOSTS` allowlist for locked-down deployments
* ENH: Finer section chunking for grounded-doc retrieval — long sections split on paragraph boundaries, restoring meaningful BM25 scoring on small per-dataset corpora and yielding tighter citations
* FIX: Strip inline markdown-link syntax from section headings so citations read `Standards` instead of `[Standards](https://…)`
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
