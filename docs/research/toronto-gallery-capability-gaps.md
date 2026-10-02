# Cross-project CKAN MCP capability backlog

> **Research snapshot, not an implementation plan or registered capability.**
>
> Canonical report: [CKAN-CAPABILITY-GAPS.md](../../../toronto-open-data-gallery-research/CKAN-CAPABILITY-GAPS.md)
> in the local `toronto-open-data-gallery-research` repository, source commit
> **7f91c5b1cf0cb046b1ba5bd49fe32cb266004c42**. This copy was added on 2026-10-02.
> Only this provenance block and companion-repository links differ from that source.
>
> **Sync responsibility:** the CKAN repository maintainer owns deliberate refreshes
> from the canonical research report. Update its source commit and date when syncing;
> there is no automatic synchronization. Record implementation decisions separately
> in this repository instead of treating this snapshot as current server behavior.
>
> Inventory and supporting research links require the sibling local research checkout;
> they are not vendored here and will not resolve in a standalone clone or GitHub view.
> Immutable public code citations remain usable independently. The behavior baseline
> below is MCP commit `e87ae8b`, not a claim about subsequent revisions.

Research date: **2026-10-02 UTC**. Proposals only; no server/client or creator code changed. Re-inspected the clean local MCP at **e87ae8bcd76b90db72a0cadd88b5a799909706a3**. The [88-entry inventory](../../../toronto-open-data-gallery-research/research/inventory.json), [ranked source evidence](../../../toronto-open-data-gallery-research/RANKED-REPORT.md), [live metadata checks](../../../toronto-open-data-gallery-research/research/datasets.json), and [Transportation Services ownership checks](../../../toronto-open-data-gallery-research/research/transportation-ownership.json) underpin this map. The deep code sample is selective, not a demonstration that all 88 projects need these features. Creator demand and time saved remain untested.

**Recommended sequence:** improve result diagnostics and metadata provenance first; add bounded file inspection next; then evaluate resource contracts and client orchestration. Keep bulk computation and spatial analysis in deterministic clients. SQL is a conditional option, not the assumed solution.

P0 means the next small reliability/provenance change; P1 means a broadly useful extension requiring design and fixtures; P2 means conditional/expensive work. Priorities reflect evidence and incremental benefit, not measured adoption. “Server” is the reusable CKAN API/tool layer; “client” is assistant orchestration or a deterministic analysis companion; Toronto terminology and ownership rules belong in the Toronto skill/client configuration.

## Current behavior verified before proposing gaps

| Area | Already implemented | Actual boundary |
|---|---|---|
| Discovery | `package_search(q,fq,sort,rows,start,full)` and `package_show(full)` | One configured portal; trimmed search excludes resources. Full metadata remains available. |
| Row access | `datastore_search(q,limit,offset,sort,fields,filters)`; exact filters AND across fields and OR for list values; `limit=0` counts | No range-expression, grouping, join, spatial or SQL tool; raw portal response is returned. Count is matching records, not sum of a measure. |
| Pagination | Explicit offset/limit parameters | No automatic complete extraction, resume checkpoint, or snapshot guarantee. Portal limits and mutations still matter. |
| Schema | `dataset_schema` zero-row requests for active DataStore resources | Fields/types are available; no persisted contracts/diffs. Non-DataStore files are unknown. DataStore errors are swallowed into that same unknown state. |
| Files | Metadata exposes download URLs; document fetcher downloads HTML/PDF internally | No structured CSV/XLSX/JSON/GeoJSON or archive download/parser tool. Preview falls back to metadata on **any** `ToolError`. |
| Provenance | Summary preserves package `metadata_modified`; raw metadata available with `full=True` | Summary drops licence, resource modification fields and Toronto `owner_division`; no observation/hash manifest in row outputs. Metadata update time is not observation time or data freshness. |
| Documents | Linked HTML/PDF crawling, bounded cache, BM25/term overlap retrieval with URL/heading | Missing seeds, fetch failures and crawl limits restrict coverage; not semantic row search or data-definition repair. |

Implementation: [metadata][mcp-meta], [rows/preview][mcp-rows], [schema][mcp-schema], [document tools][mcp-doc-tools], [HTTP errors/timeouts][mcp-http]. Existing [filter tests][mcp-tests] explicitly preserve separate rows and do not rewrite or retry text queries. No new runtime/live tests were performed for this documentation follow-up.

## G01 — Typed preview/schema failures and incomplete-result reporting

**Observed workflow / evidence:** the [events proxy][proxy-fetch] handles upstream non-JSON failures; [TTC ingestion][ttc-download] must distinguish file/dump sources. NORC's [README][norc] records missing column definitions and contradictory amenity flags. These establish acquisition and interpretation problems, not proof of a server production failure.

**Verified limit:** preview catches every `ToolError` and returns resource metadata, obscuring whether rows were unavailable because DataStore is inactive, the request timed out, or the portal rejected it. Schema catches DataStore errors and leaves “Unknown (not in DataStore)” even for active resources. HTTP client errors are otherwise useful and distinguish timeout/API/envelope failures. [Preview][mcp-rows], [schema][mcp-schema], [client][mcp-http].

**Proposal / owner:** P0 server: explicit result kind (`records`, `metadata_only`, `error`), attempted action, DataStore flag, structured failure reason and safe diagnostics. Preserve successful raw rows and distinguish declared capability from observed failure. Client must refuse to interpret metadata as sample rows and report unavailable evidence.

**Beneficiaries / tradeoff:** Event Buddy, proxy, TTC, Medha/Rahul 311, NORC and any mixed-resource dataset. New envelopes can break clients; add a versioned/compatible surface rather than silently changing return shapes. Do not expose auth values or entire sensitive error payloads.

**Concrete validation:** fixtures for inactive file, active timeout, active 403, invalid envelope, empty successful rows and valid sample. Each produces a distinct machine-readable state; zero rows is success, timeout is never labelled “not in DataStore”, and metadata has no fabricated `records`.

## G02 — Compact provenance, licence, ownership and freshness

**Observed workflow / evidence:** [BikeSpace wrappers][bike-provenance] retain source identity; the [events proxy][proxy-ckan] selects the first matching resource despite a “latest” name. [Permit acquisition][multiplex-fetch] pins UUIDs. NORC [documents][norc] potential disagreements between datasets and Street View vintages. The ownership checks show Toronto's broad organization label is less specific than `owner_division`.

**Verified limit:** raw fields exist through `full=True` or optional `resource_show`; they are not missing upstream merely because [summary trimming][mcp-meta] omits them. Current tool results do not add retrieval time/content hashes. Resource timestamps can themselves be absent or misleading.

**Proposal / owner:** P0 server: optional compact provenance profile with portal/package/resource IDs, source URL, licence fields when present, package/resource timestamps with original field names and `observed_at`. Optional content hash only when bytes actually fetched. P0 Toronto client/skill: inspect `owner_division` without imposing it on generic CKAN schemas; label unknowns. Separate metadata change, publication vintage, fetch time and data currency.

**Beneficiaries / tradeoff:** all shortlisted projects; particularly BikeSpace, proxy, census, permits and Jam source research. Slightly larger responses; freshness labels must not invent update frequency or turn catalogue ownership into enforcement responsibility. Dataset licence is separate from code licence.

**Concrete validation:** a package fixture with different package/resource dates, missing licence URL, broad organization and specific owner produces faithful fields and explicit unknowns. Re-fetch the same bytes at another time: hash stays constant, observation changes; no “latest data” assertion follows from metadata modification alone.

## G03 — Bounded structured-file preview and schema inspection

**Observed workflow / evidence:** [Event Buddy][event-route] fetches JSON directly; [Medha's instructions][medha-data] require a yearly CSV download; [TTC extraction][ttc-download] downloads CSV/XLSX/dumps; [BikeSpace][bike-resource] retrieves GeoJSON resources. Live evidence shows events/311 file-only and the 2021 census profile file-only. This is the strongest coverage extension.

**Verified limit:** [preview][mcp-rows] returns metadata after DataStore failure; [schema][mcp-schema] has no file parser. [Document fetching][mcp-file-doc] classifies non-PDF content as HTML; its bytes transfer is not a structured dataset interface.

**Proposal / owner:** P1 server: opt-in resource-ID-based, byte/row/time-bounded inspection; begin CSV and JSON/GeoJSON, defer XLSX/ZIP/GTFS until demand and parser limits are established. Return original field names, sample rows, parsing/inference caveats, content type, bytes consumed, truncation and provenance. Full downloads go through a separately authorized client workspace sink with a manifest rather than the model context.

**Beneficiaries / tradeoff:** Event Buddy/proxy, 311 studies, census, TTC and cycling maintainers. Encoding, nested arrays, huge JSON, formulas, archive expansion and remote URLs introduce complexity. Reuse/document the current public-address, redirect and host protections; do not weaken them. Samples cannot establish full-file schema consistency or completeness.

**Concrete validation:** fixtures for quoted CSV/newlines/BOM, JSON array, nested GeoJSON properties, empty file, misleading MIME, oversized input, private-address redirect and unsupported ZIP. Enforce limits before unlimited allocation; retain nulls/leading-zero IDs; explicitly report sampled/inferred schema; no executable content or formula evaluation.

## G04 — Resource selection contracts and schema evolution checks

**Observed workflow / evidence:** hardcoded [permit IDs/columns][multiplex-fetch] and [reference IDs][multiplex-reference]; [TTC][ttc-extract] selects yearly formats; [proxy][proxy-ckan] takes first eligible resource; [census loader][census-loader] and [crosswalk][census-crosswalk] depend on local schemas/vintages.

**Verified limit:** discovery and current schemas exist. [Schema tool][mcp-schema] has no previous version, expected-field contract, resource-selection explanation, type/unit comparison or inferred equivalence across years. It cannot know an unpublished unit or join relationship.

**Proposal / owner:** P1 client contract manifest: package slug, required fields/types, preferred format/year, explicitly accepted IDs, provenance and selected source. Diff fresh metadata/schema against a saved approved snapshot; classify additions, removals, type changes and UUID replacement. Server could expose a compact machine-readable capability/schema result, but persist study contracts in the client. Ask for selection when multiple plausible resources remain; never auto-accept a renamed field as equivalent.

**Beneficiaries / tradeoff:** Multiplex, TTC, census, proxy, gentle density and BikeSpace. Useful maintenance aid, limited incremental benefit for stable pipelines. Names/dates are imperfect selectors; keep deterministic ingestion and frozen-study choices.

**Concrete validation:** reorder unchanged resources, replace UUID, remove required field, change type, add a similarly named year and omit date. Order alone does not alter selection; incompatible changes block acceptance with evidence; a supported explicit vintage remains selected over an ambiguous “latest”.

## G05 — Complete, resumable pagination in the client

**Observed workflow / evidence:** [Multiplex client][multiplex-client] explicitly loops 20,000-row pages with a 120-second timeout. Its presence establishes existing pagination competence, not an unmet creator request.

**Verified limit:** [MCP row search][mcp-rows] already exposes offset, limit, sort and projection. It does not loop or checkpoint; no tool-enforced max page/response budget. [Client][mcp-http] uses a 30-second default timeout and no automatic retries. CKAN responses/limits depend on the portal; advancing by requested page size can skip rows if a portal caps it.

**Proposal / owner:** P1 deterministic client iterator/export helper with bounded budgets, actual returned-row offsets, progress/partial status, checkpoints and conservative transient retries. Use an explicit stable unique sort only when supported; record observed totals and source timestamp changes. Offer small-page guidance first. Keep raw page queries available; never pour all records into the conversation or claim a transactional snapshot.

**Beneficiaries / tradeoff:** permits, TTC and other repeated extraction/research. Existing production ETL may be preferable. Concurrent source mutation can still yield omissions/duplicates; retries and configurable per-operation timeouts need total budgets and failure visibility.

**Concrete validation:** requested page 100, portal cap 40, total 105; recover all 105 static fixture records exactly once. Add a transient second-page timeout and resume; exhausted retry budget yields a partial manifest. Concurrent mutation/changed total is surfaced, not certified complete. Exports remain inside the configured client workspace.

## G06 — Numeric aggregation and range filtering without SQL assumptions

**Observed workflow / evidence:** [Multiplex][multiplex-fetch] filters application dates locally before DuckDB/dbt; [Event Buddy][event-route] applies a month window; Medha/Rahul use local analysis files, while [gentle density][gentle-permits] applies study conditions. These are deterministic computation needs beyond exact lookups.

**Verified limit:** [row tool][mcp-rows] and [tests][mcp-tests] support exact filters, text search and `limit=0` record counts; there is no sum/group-by/range/SQL surface. Filters do not aggregate repeated keys. Multiplex's [comment][multiplex-client] reports a portal WAF SQL block; this claim was not independently re-tested and does not establish all CKAN portals lack SQL.

**Proposal / owner:** P1 client bounded tabular analysis companion for typed ranges and deterministic count/sum/group-by over a demonstrably complete input or an explicitly labelled sample. Preserve query plan, null handling, measure semantics and completeness. P2 optional server SQL/aggregate capability only after endpoint verification and read-only design review; cannot bypass a WAF or infer availability from CKAN branding. Prefer a constrained expression interface if SQL is explored.

**Beneficiaries / tradeoff:** permits, 311, TTC, cycling counts and census research. Cost scales with full retrieval; generic sum may be meaningless for rates, duplicated facts or suppressed census values. No business classification, forecast or chart backend replacement.

**Concrete validation:** rows with repeated grouping keys and measure values 2, 5, null: record count 3, non-null count 2, sum 7. A date boundary includes/excludes exactly as declared. A truncated input forbids an unlabeled population total; unavailable SQL returns an explicit capability failure without bypass or silent substitution.

## G07 — Document coverage diagnostics and evidence of unknown definitions

**Observed workflow / evidence:** NORC [README][norc] explains absent bench/shelter column descriptions, erroneous SITEID matching and inconsistent flags; census [semantic retrieval][census-rag] searches local rows. These are different tasks: source definitions versus semantic numerical retrieval.

**Verified limit:** [seed discovery][mcp-seeds] uses `information_url` and Markdown links in notes; [crawl][mcp-crawl] logs/skips unsafe, robots-disallowed or failed fetches and returns successful pages. Bounds/cache exist. [BM25][mcp-bm25] returns positive lexical hits with overlap fallback; it cannot establish that an unreturned definition does not exist. Current MCP results lack a structured failed/skipped/queued/coverage manifest.

**Proposal / owner:** P0 server crawl manifest: seed/fetch status, limits hit, skipped reasons, retrieval/cache age and unvisited count when known. P1 seed support for explicitly identified documentation resources/metadata links with format and URL checks. Client records “not found in fetched sources” and cites source passages; optional semantic document retrieval only after recall evaluation. Do not conflate this with census row embeddings or invent missing units/keys.

**Beneficiaries / tradeoff:** NORC, permits, census and source-grounded explanations. More diagnostics/tokens; mutable documents complicate stable citations. Keep crawl bounds and robots/public-host protections. Stronger retrieval cannot repair absent publication.

**Concrete validation:** seed HTML with one successful page, one 404, one robots refusal and another beyond page budget. Manifest accounts for all observed outcomes; a no-hit question reports limited coverage. A fake SITEID equivalence absent from source is not inferred; actual definition returns URL/heading and exact supporting passage.

## G08 — Spatial readiness before generic spatial execution

**Observed workflow / evidence:** NORC [README lines 13–36][norc] documents a 10-metre bench proximity workaround; [gentle density][gentle-joins] matches addresses/geometries; [BikeSpace wrappers][bike-wrapper] normalize source geometry. [Census crosswalk][census-crosswalk] relates differing geographic identifiers.

**Verified limit:** metadata/fields/rows can already contain geometry text and identifiers. No MCP spatial predicate, CRS transform, nearest-neighbour or join tool exists. Schema types alone do not prove compatible CRS, shared keys, unique keys or geographic vintage.

**Proposal / owner:** P1 client readiness report for published CRS/vintage, geometry encoding, candidate keys and source-backed definitions; optionally bounded shape/ID validation after G03. P2 deterministic spatial companion with explicit CRS/units and reproducible joins only if demand warrants it. Keep portal-specific key corrections in dataset adapters, not universal server heuristics.

**Beneficiaries / tradeoff:** NORC, BikeSpace, gentle density, census and simulation-input preparation. Spatial dependencies and heavy data make a server extension costly; the existing GeoPandas/OSM pipelines may be better. Preserve distinction between measured proximity and actual amenity association.

**Concrete validation:** points supplied in degrees must not be treated as metres; missing CRS blocks a 10-metre claim. Bench SITEID and stop_code remain separate unless documentation proves equivalence. A transformed synthetic fixture returns known distances and reports duplicate/null join keys and geography-vintage mismatch.

## G09 — Explicit multi-source orchestration rather than accidental federation

**Observed workflow / evidence:** [BikeSpace pipeline][bike-resource] combines City data with other sources; census [loader/crosswalk][census-crosswalk] uses prepared local inputs. Transportation ownership evidence separates TS, TTC, TPA and I&T even within the City catalogue. Conditional leads in the ranked report include external police/live feeds and another CKAN catalogue; their compatibility is untested.

**Verified limit:** [one process-wide client][mcp-single] targets configured `CKAN_URL`; [configuration resource][mcp-config] identifies it. A second server instance can already target another CKAN portal. Document hosts are not general live-feed adapters. No need to claim multi-portal access is impossible.

**Proposal / owner:** P2 client named-source registry using existing separate MCP instances first. Include portal identity in results/manifests and disambiguate identical slugs/UUIDs; use explicit adapters for non-CKAN feeds. Consider server multi-profile routing only after operational demand. Credentials remain scoped to a configured source.

**Beneficiaries / tradeoff:** mixed-source cycling, census and broader civic research. Direct evidence for CKAN federation demand is weaker than file/schema needs. Extra discovery schemas, auth and endpoint policies raise cost; remote metadata does not confer a shared geography or equivalent definitions.

**Concrete validation:** two configured fixtures share a slug/resource ID with different schemas: output provenance and tool routing remain unambiguous; credentials never cross destinations; unsupported live feed is labelled external rather than falsely queried as DataStore.

## Sequence and boundary for the dedicated Jam/SUMO task

1. P0: G01/G02/G07 to make present evidence trustworthy and explain missing information.
2. P1: G03 then G04, with G05/G06 as deterministic client work where current applications do not already cover the need.
3. P1/P2: G08 readiness; execute spatial work only with defined CRS/keys. G09 and optional SQL follow verified demand/capability.

The dedicated task can link to G02/G03/G04/G07/G08 for simulation **input research**. TorontoSUMONetworks' cached README claims TraCI and SUMO 1.9.0+, but implementation/control timing is deliberately unverified here. Vehicle actions, observation state, simulation clock, latency management, control safety, training and rewards are application-specific SUMO work, outside the CKAN backlog. BikeSpace remains evidence for general server improvement and personal use; it is excluded from fresh Jam recommendations because it already appeared at the TPS Jam. Focused Jam/SUMO work belongs in the separate repository; this map does not change the historical shortlist snapshot.

## Validation and remaining uncertainty

Tests above are **proposed acceptance tests**, not results. This follow-up used read-only local server/source/test inspection and existing pinned gallery evidence; no creator code was executed and no new endpoints were probed. Offline artifact validation checks navigation/reference paths and line ranges; it cannot establish tool performance, deployed project versions, creator demand, server feasibility or semantic correctness of unpublished definitions. Prior live dataset checks are timestamped observations, not permanent guarantees.

[bike-provenance]: https://github.com/bikespace/parking-map-data/blob/b4bbe979082815f74efca07b291a9bc0a87f6fdc/src/bikespace_data/bicycle_parking/wrappers.py#L125-L153
[bike-resource]: https://github.com/bikespace/parking-map-data/blob/b4bbe979082815f74efca07b291a9bc0a87f6fdc/src/bikespace_data/resources/toronto_open_data.py#L22-L62
[bike-wrapper]: https://github.com/bikespace/parking-map-data/blob/b4bbe979082815f74efca07b291a9bc0a87f6fdc/src/bikespace_data/bicycle_parking/wrappers.py#L67-L81
[census-crosswalk]: https://github.com/twotoque/torontoCensusVisualizer2/blob/0c6be16ade61697f1a3aca6ea8abd599bb5f1009/python/data_loader.py#L93-L116
[census-loader]: https://github.com/twotoque/torontoCensusVisualizer2/blob/0c6be16ade61697f1a3aca6ea8abd599bb5f1009/python/data_loader.py#L22-L50
[census-rag]: https://github.com/twotoque/torontoCensusVisualizer2/blob/0c6be16ade61697f1a3aca6ea8abd599bb5f1009/python/rag.py#L91-L121
[event-route]: https://github.com/osebom/toronto_data/blob/2ad1c1ed284dd17165e2b5643d10b9287f8102bc/app/api/events/route.ts#L41-L78
[gentle-joins]: https://github.com/schoolofcities/gentle-density/blob/2428084548b99584202cf2ab815c6397571db0d7/data/toronto-only/permit-to-geojson-toronto-addresses.py#L47-L90
[gentle-permits]: https://github.com/schoolofcities/gentle-density/blob/2428084548b99584202cf2ab815c6397571db0d7/data/toronto-only/permit-to-geojson-toronto-addresses.py#L12-L42
[mcp-bm25]: https://github.com/ruchir321/ckan-mcp-server/blob/e87ae8bcd76b90db72a0cadd88b5a799909706a3/ckan_mcp_server/documents.py#L513-L541
[mcp-config]: https://github.com/ruchir321/ckan-mcp-server/blob/e87ae8bcd76b90db72a0cadd88b5a799909706a3/ckan_mcp_server/server.py#L443-L452
[mcp-crawl]: https://github.com/ruchir321/ckan-mcp-server/blob/e87ae8bcd76b90db72a0cadd88b5a799909706a3/ckan_mcp_server/documents.py#L371-L444
[mcp-doc-tools]: https://github.com/ruchir321/ckan-mcp-server/blob/e87ae8bcd76b90db72a0cadd88b5a799909706a3/ckan_mcp_server/server.py#L351-L410
[mcp-file-doc]: https://github.com/ruchir321/ckan-mcp-server/blob/e87ae8bcd76b90db72a0cadd88b5a799909706a3/ckan_mcp_server/documents.py#L363-L368
[mcp-http]: https://github.com/ruchir321/ckan-mcp-server/blob/e87ae8bcd76b90db72a0cadd88b5a799909706a3/ckan_mcp_server/client.py#L89-L150
[mcp-meta]: https://github.com/ruchir321/ckan-mcp-server/blob/e87ae8bcd76b90db72a0cadd88b5a799909706a3/ckan_mcp_server/server.py#L88-L168
[mcp-rows]: https://github.com/ruchir321/ckan-mcp-server/blob/e87ae8bcd76b90db72a0cadd88b5a799909706a3/ckan_mcp_server/server.py#L225-L276
[mcp-schema]: https://github.com/ruchir321/ckan-mcp-server/blob/e87ae8bcd76b90db72a0cadd88b5a799909706a3/ckan_mcp_server/server.py#L309-L345
[mcp-seeds]: https://github.com/ruchir321/ckan-mcp-server/blob/e87ae8bcd76b90db72a0cadd88b5a799909706a3/ckan_mcp_server/documents.py#L150-L165
[mcp-single]: https://github.com/ruchir321/ckan-mcp-server/blob/e87ae8bcd76b90db72a0cadd88b5a799909706a3/ckan_mcp_server/server.py#L30-L41
[mcp-tests]: https://github.com/ruchir321/ckan-mcp-server/blob/e87ae8bcd76b90db72a0cadd88b5a799909706a3/tests/test_ckan_client.py#L163-L208
[medha-data]: https://github.com/Medha-04/toronto-311-data-analysis/blob/4f40f0fcdfcc90fb28c7e06d5eca23fc6caa3db0/data/README.md#L3-L18
[multiplex-client]: https://github.com/zuzubak/to-multiplex-map/blob/1320da36bd493f087276fb0b1a39617f7b8246d6/ingest/ckan_client.py#L13-L47
[multiplex-fetch]: https://github.com/zuzubak/to-multiplex-map/blob/1320da36bd493f087276fb0b1a39617f7b8246d6/ingest/fetch_permits.py#L22-L58
[multiplex-reference]: https://github.com/zuzubak/to-multiplex-map/blob/1320da36bd493f087276fb0b1a39617f7b8246d6/ingest/fetch_reference.py#L24-L57
[norc]: https://github.com/mkfreeman/norc-map/blob/68460db7a28548b5348f441a2f5bda9da495953d/README.md#L13-L36
[proxy-ckan]: https://github.com/CivicTechTO/toronto-opendata-festivalsandevents-jsonld-proxy/blob/cf81d7f9eb187ec95a7343fa0a544d078de66790/scripts/ckan.py#L19-L41
[proxy-fetch]: https://github.com/CivicTechTO/toronto-opendata-festivalsandevents-jsonld-proxy/blob/cf81d7f9eb187ec95a7343fa0a544d078de66790/scripts/ckan.py#L62-L96
[ttc-download]: https://github.com/smaranje/ttc-data-pipeline/blob/9a8b137b4f28403e605a142da5eda0cb302f87da/etl/extract.py#L67-L108
[ttc-extract]: https://github.com/smaranje/ttc-data-pipeline/blob/9a8b137b4f28403e605a142da5eda0cb302f87da/etl/extract.py#L11-L45
