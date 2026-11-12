# CHANGELOG

2026-11-11 - unreleased crawler and result-size work

* FIX: Document crawl scope follows redirects; pages are reported and deduplicated by final URL, and a child page that redirects out of scope is dropped
* FIX: A document that fails extraction (for example a corrupt PDF) is skipped instead of aborting the crawl
* FIX: Non-document content types (images, spreadsheets, archives) are refused before download
* ENH: `ckan_fetch_dataset_docs` output is capped at 60,000 characters, with `total_chars` and `truncated` per page
* ENH: `ckan_datastore_search` returns 20 rows when `limit` is omitted; `limit=0` still returns a count only
* ENH: DataStore row results carry only `id` and `type` per field and no `_links`
* ENH: `ckan_package_search` shortens notes to 300 characters
* ENH: Bare URLs in dataset notes are used as documentation seeds
* ENH: Crawl cache serves smaller requests from a larger crawl, runs one crawl per key and holds at most 32 entries
* ENH: CKAN requests retry twice on 429, 502, 503, 504 and connection errors
* ENH: Parsing and DNS checks run in worker threads
* ENH: Server instructions describe the query workflow
* SEC: Compose HTTP profile binds to loopback; stdio service no longer sets `tty`
* RMV: `rank-bm25` (and numpy) replaced by a built-in BM25 scorer
* RMV: Stale `ckan://api/docs` resource, legacy test helpers and the `python_files` collection allowlist
* DOC: Trimmed `.gitignore`; removed the dependency maintenance table from the README (see the 2026-09-30 entry)

2026-09-30 - unreleased maintenance

* Update aiohttp, certifi, FastMCP 3.x and pypdf within supported dependency ranges.
* Advertise read-only MCP annotations while preserving the eight default tools.
* Preserve information_url in trimmed dataset metadata for source discovery.
* Encode Boolean CKAN query parameters and return useful errors for malformed URLs, HTTP failures and invalid JSON envelopes.
* Handle empty document vocabularies and nonpositive retrieval limits without ranking failures.
* Add offline regression and MCP/HTTP protocol coverage; document transport behavior, dependency decisions and the Plugin Creator route.

2026-06-21 - unreleased

* FIX: Packaging — include `document_scraper` in the built distribution (the server imports it; it was previously omitted from `py-modules`)
* RMV: Delete `tests/test.py` (stale OpenAI Agents SDK scaffold) and the `openai-agents` dependency
* ENH: Lean tool surface by default — only 8 high-value tools are registered; the lower-value list/health endpoints (`package_list`, `organization_*`, `group_list`, `tag_list`, `resource_show`, `site_read`, `status_show`) are gated behind `CKAN_EXPOSE_ALL_TOOLS=1`, cutting per-turn schema context
* RMV: Drop the four `@mcp.prompt` templates (`search_datasets`, `analyze_neighborhood`, `business_insights`, `educational_data`) — they were an unused proof-of-concept; domain workflows now live in the Toronto Skill
* DOC: Position the project as a generic CKAN core + Toronto flagship Skill (README); refresh stale model references in `docs/` to current Claude tiers (Opus 4.8 / Sonnet 4.6 / Haiku 4.5)
* DOC: Add `skills/toronto-open-data/SKILL.md` — a Claude Agent Skill carrying Toronto domain knowledge (portal conventions, dynamic dataset-discovery + search-chaining patterns, workflow recipes) and the grounding discipline, so domain IP lives in a progressively-disclosed Skill while the MCP server stays a lean, portable tool layer
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

---
Author: Claude Code | Model: claude-sonnet-5-5 | Date: 2026-11-11 (updated)
