---
name: toronto-open-data
description: Explore and analyze City of Toronto Open Data (CKAN portal) — find datasets, read their schemas, query records, and answer civic/legal/bylaw questions from cited source documents. Use whenever a request involves Toronto datasets, neighbourhoods, wards, city services, licensing, housing, or other Toronto municipal data.
---

# Toronto Open Data

Domain knowledge for working with the City of Toronto Open Data portal, which runs on
CKAN. This Skill knows *which* Toronto datasets matter, *how* to chain searches across
them, and *how to answer grounded* from authoritative source documents instead of guessing.

The portal: <https://open.toronto.ca> (human UI) is backed by the CKAN Action API at
`https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/...`.

## How to access the data

Prefer the **`ckan-mcp-server` MCP tools** when they are available in the client:
`ckan_package_search`, `ckan_package_show`, `ckan_dataset_schema`, `ckan_datastore_search`,
`ckan_resource_preview`, plus the grounded-doc tools `ckan_fetch_dataset_docs` and
`ckan_search_dataset_docs`. If those tools are not present, call the CKAN Action API
directly (e.g. `GET /api/3/action/package_search?q=...`) — the endpoints and parameters
are identical.

A dataset's **resources** (CSV/XML/GeoJSON) are the *data*. A dataset's `information_url`
(and links inside its `notes`) point to the *authoritative prose/legal source of truth* —
standards pages, bylaws, methodology. Use the data for numbers; use the source documents
for rules and definitions.

## Core workflow

1. **Discover** — `ckan_package_search(q=...)` to find candidate datasets; skim titles/notes.
2. **Inspect** — `ckan_dataset_schema(id=...)` for fields, or `ckan_package_show(id=...)` for
   the full record (resources, `information_url`).
3. **Query / preview** — `ckan_datastore_search(resource_id=...)` for SQL-like filtering, or
   `ckan_resource_preview(resource_id=...)` for the first rows.
4. **Ground** — for any rule/definition/legal follow-up, pull the source document with
   `ckan_search_dataset_docs(dataset_id, query)` and answer from the cited passage.

## Grounding discipline (do not skip)

When a question turns on a rule, threshold, eligibility, definition, or any legal/bylaw point:

> **Answer only from the passages returned by `ckan_search_dataset_docs` (or
> `ckan_fetch_dataset_docs`). Quote the relevant text verbatim, and cite its source URL.
> If nothing relevant is returned, say the source does not cover it — do not guess.**

This is the project's anti-hallucination guarantee: civic/legal answers must be traceable to
a City of Toronto document. Use the model's citation capability to attach the source URL to
quoted claims.

## Discovering and chaining datasets

There is **no hardcoded dataset list** — datasets are discovered dynamically with
`ckan_package_search` at query time. Do not assume specific dataset slugs exist; search for what
each step needs. To answer a multi-faceted question, chain searches:

1. **Anchor** — find the dataset most central to the question via search, and inspect its schema.
2. **Chain spatially** — by ward or neighbourhood — to related datasets (e.g. complaints, service
   requests, environmental or infrastructure data).
3. **Chain by entity** — by a shared key such as address, property, business, or organization — to
   enforcement, registration, or licensing datasets.
4. **Layer context** — census / "neighbourhood profile"-style datasets add a demographic or equity
   lens when spatially joined.
5. **Synthesize** across the chained datasets, grounding any rule / threshold / definition claim in
   the source documents via `ckan_search_dataset_docs`.

## Notes

- This Skill carries the Toronto domain expertise; the MCP server stays a lean, portable tool
  layer. Keep portal-agnostic mechanics (HTTP, pagination) in the tools, and Toronto specifics here.
- The grounded-doc tools only fetch public hosts (SSRF guard). If a dataset's `information_url`
  is on a restricted host, set `CKAN_DOC_ALLOWED_HOSTS` on the server.
