# Verification record

Verified locally on 2026-09-28.

## Data

- Ingested the live openFDA API through HTTP, with no browser scraping.
- Snapshot: 458 source records; 457 contain text; 352 distinct application identifiers.
- FDA source update: 2026-08-13. One Chiesi record is metadata only and marked “Under Review for Release.”
- 18 authored review areas; 423 candidate evidence spans. Every span exactly equals its source text slice.
- Classified with `rule_keyword_context_v4`. Categories are candidate topic mentions and have no expert-reviewed precision/recall estimate.
- Checked individual FDA PDF URLs for both newer and archived naming patterns. Pending-release metadata has no generated PDF link.
- The source snapshot hash and fetch/index timestamps are retained. The snapshot hash is distinct from the per-record hash.

## Automated checks

- Core Python tests: 9 passed. Cover idempotent ingestion, shared PDF identities, incomplete snapshot rejection, pagination, filter combinations, FTS punctuation safety, export escaping, missing PDFs, exact evidence spans, and boilerplate/positive-statement exclusions.
- Frontend logic: 3 Node tests passed. Cover workspace restore validation, unsupported statuses, and rendering untrusted source text safely.
- HTTP smoke: health, filtered statistics, filtered search, taxonomy, CSV export, and JSONL export all return successful nonempty responses.
- JavaScript syntax check passed.
- MCP: final SDK integration test passed under the project virtual environment (official SDK 2.2.0). The client initialized over stdio, listed all four tools, and called search, letter retrieval, corpus statistics, and checklist tools. All four tools were also exercised against the live local API.
- CI workflow includes core, frontend, API, and optional MCP protocol tests. The workflow has not been run on a hosted GitHub repository.
- Container recipe is supplied; the container build has not been verified in this session.

## Chrome checks

- Inspected RXA’s filters, table, and timeline as the interaction reference.
- Desktop overview rendered with real counts, ranked review areas, a continuous yearly axis, source cards, and methodology links.
- Full-text search for “potency” returned 21 records.
- Combined “potency” + 2024 + BLA + Approved returned the Akeso record.
- Niche-category drill-down for extractables/leachables returned 18 records.
- Pagination advanced from records 1–25 to 26–50.
- A nonsense search showed an explicit empty state and disabled pagination.
- Letter dialog showed source text, evidence, PDF link, and provenance; close control returned to the archive.
- Saved a synthetic QA program, changed a review status to Open gap, added notes, and reloaded. The name, context, status, and notes persisted.
- Stage selection and local context matching worked.
- Markdown and JSON workspace exports created files in Downloads. Inspected the Markdown file to confirm the program context, status, note, source identifiers, and interpretation caveat.
- JSON restore’s browser file chooser was blocked by the automation layer with “Not allowed.” The restore validation logic passes unit tests; the file-picker round trip remains unverified.
- Mobile planner and overview checked at 390 px. Fixed a chart-grid overflow; the final document width is 375 px inside the 390 px viewport, with no horizontal overflow.
- No JavaScript errors were observed during the browser workflows.

## Remaining release work

Human adjudication and measured extraction quality are required before treating category labels as established failure reasons. A public host/domain has not been provisioned. Browser workspaces stay on the local device; the MCP adapter exposes the public corpus only.
