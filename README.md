# Failure Mode

**v0.1.0 · by [@dmtxbio](https://github.com/dmtxbio)**

[Source](https://github.com/dmtxbio/failure-mode) · [Releases](https://github.com/dmtxbio/failure-mode/releases) · [Report an issue](https://github.com/dmtxbio/failure-mode/issues)

Explore FDA complete response letters and turn source evidence into a development planning review. Inspired by [Justin Yan’s RXA](https://rxa.justinyan.com/).

## Run locally

Python 3.10+ with SQLite FTS5 is the only requirement for the dashboard and API. No API key, model subscription, Node build, or browser automation is needed.

```sh
python3 -m failure_mode.ingest --cached
python3 -m failure_mode.server
```

Open http://127.0.0.1:8000.

To keep the dashboard running after closing the launching terminal or tool session:

```sh
python3 -m scripts.start_local
```

This binds to localhost, detaches the process, and writes its PID and logs under `.runtime/`. It checks HTTP health before reporting success.

The included raw snapshot contains **458 FDA records**, of which **457 contain text**; one is marked “Under Review for Release.” FDA reports the snapshot last updated **2026-08-13**. The records span 2002–2026, including historical releases. These are records in the published corpus, not all FDA decisions. Some applications have multiple letters, and some files contain multiple dated letters.

To refresh directly from openFDA:

```sh
python3 -m failure_mode.ingest
```

Ingestion paginates the JSON API, retries transient failures, records provenance, and rebuilds the FTS search index. The raw snapshot allows offline rebuilding. Run refreshes as a separate scheduled job; page views query local SQLite and never call FDA.

## What is included

- Overview with shared search, year, application type, source status, and candidate review-area filters.
- Full-text archive with pagination, sorting, source PDFs, exact evidence excerpts, and provenance.
- A transparent, versioned topic taxonomy with broad and specialized review areas.
- Multiple private planning workspaces: development stage, plan context, review status, notes, evidence references, and owners/next actions.
- Local term matching to suggest relevant review areas; it does not assess whether a plan satisfies them.
- Markdown reports and portable workspace JSON export/import.
- CSV and JSONL corpus exports, reusable REST API, and an optional official-SDK MCP integration.

Plans are saved in the browser’s local storage and are not sent to the server. The app loads no third-party scripts, fonts, analytics, or model services. Other people using the same browser profile can access local workspaces. Export a backup before clearing browser storage.

## Data and interpretation

The [openFDA CRL API](https://open.fda.gov/apis/transparency/completeresponseletters/) already supplies extracted text. OCR is therefore not required for this snapshot. Public PDFs remain linked for checking layout, redactions, and extraction errors. The metadata-only pending-release record has no released text or source PDF to OCR.

A CRL means the application was not approved **in its current form** at that review. “Approved” / “Unapproved” are source dataset labels, not our determination of present market status. The API does not provide reliable normalized drug names; the interface uses sponsor and application identifiers.

Review-area assignments are deterministic **candidate topic mentions**, not adjudicated deficiencies or causal failure labels. The classifier suppresses routine boilerplate and retains exact source spans. It still has false positives and false negatives. No formal precision/recall claim is made. All assignments are unreviewed. Counts describe this selective, redacted disclosure corpus and cannot estimate approval probabilities.

Checklist questions are authored research prompts. A reviewer’s “Addressed” status records their own assessment; it does not certify readiness. Review full source context and relevant current guidance. See [research and source limitations](docs/research.md).

## API

```text
GET /api/health
GET /api/stats
GET /api/letters?q=potency&limit=25&offset=0
GET /api/letters/{id}
GET /api/taxonomy
GET /api/export?format=jsonl
GET /api/export?format=csv
```

Search, stats, and export accept `q`, `year`, `category`, `status=approved|unapproved`, and `application_type=NDA|BLA`. Letter search also accepts `sort=date_desc|date_asc|company`, `limit` (1–1000), and `offset`. Search treats user tokens as literal FTS terms. Letter detail and JSONL include source text, evidence, and provenance. CSV exports neutralize spreadsheet formula prefixes.

For assistant access, see [MCP installation and configuration](integrations/README.md). The MCP tools expose search, source retrieval, corpus statistics, and planning questions using the same HTTP API. They do not need access to browser workspaces.

## Test

```sh
python3 -m unittest discover -s tests -v
node --check web/app.js
node --test tests/test_frontend.cjs
```

The optional MCP protocol test requires the dependencies described in `integrations/README.md`. Without them it skips. See [verification notes](docs/verification.md) for browser checks and remaining limits.

## Deploy a public instance

A container recipe is included:

```sh
docker build -t failure-mode .
docker run --rm -p 8000:8000 failure-mode
```

This builds the database from the snapshot during the image build. Put the service behind an HTTPS reverse proxy with request limits when exposing it publicly. The bundled Python server is intended for this small read-only research application, not an unbounded multi-tenant service. For larger deployments, retain the ingestion/schema/taxonomy layer and move the HTTP layer to a production application server and search to PostgreSQL or another indexed store. The ingest CLI supports a separate database path for building snapshots before an atomic publication step.

The source is published at [dmtxbio/failure-mode](https://github.com/dmtxbio/failure-mode). v0.1.0 runs locally or in a self-hosted container; it does not include a hosted public dashboard. Hosting and an expert-reviewed release dataset are separate release steps.

## Next data-quality work

1. Build a stratified, expert-reviewed set with deficiency vs. advisory vs. boilerplate labels, then measure extraction precision and recall by review area.
2. Add adjudicated structured findings with requested action, page/section citation, review provenance, and modality-specific planning prompts.
3. Link drug and indication identities to authoritative application records with explicit ambiguity handling.
4. Preserve snapshots and evaluate extraction changes before publishing refreshed classifications.
5. Add PDF extraction/OCR only for released documents whose API text is absent or unusable; keep the original text and extraction method separately.

## License

Code is MIT licensed. FDA source material has its own [openFDA terms and license](https://open.fda.gov/license/); this project makes no FDA endorsement claim. Third-party dashboard code and datasets have not been copied.
