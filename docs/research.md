# FDA CRL API and RXA dashboard research

Checked 2026-09-28. FDA findings below use the live openFDA API and official openFDA documentation. RXA findings are from the public site HTML and its loaded JavaScript/data assets.

## FDA endpoint and schema

The official endpoint is [`https://api.fda.gov/transparency/crl.json`](https://api.fda.gov/transparency/crl.json). It returns a JSON object with `meta` and `results`; each `results[]` entry has letter metadata and the extracted full text. A live `limit=1` request returned `meta.last_updated: 2026-08-13`, `meta.results.total: 458`, and these fields: `letter_date`, `approver_title`, `file_name`, `letter_year`, `approval_status`, `approver_name`, `approver_center`, `company_rep`, `company_address`, `company_name`, `text`, `application_number`, and `letter_type`. `application_number` and `approver_center` are arrays; `text` is a plain-text extraction, not the PDF.

Example (valid live query):

```text
https://api.fda.gov/transparency/crl.json?search=letter_year%3A2025&limit=1
```

That query returns a 2025 letter and reported 59 matching records. Current count by `approval_status` is Approved 309 / Unapproved 149. The API does not require a key for occasional use. For a repeatable ingestion job, FDA recommends a free key; standard limits are 240 requests/minute and 1,000/day without a key, or 240/minute and 120,000/day with a key. Query options include `search`, `sort`, `count`, `limit` (maximum 1,000), and `skip` (maximum 25,000). Paging with `skip`/`limit` is sufficient for this 458-record corpus. For future datasets larger than 26,000 matches, FDA documents `search_after` or bulk downloads. See [query parameters](https://open.fda.gov/apis/query-parameters/), [paging](https://open.fda.gov/apis/paging/), and [authentication/rate limits](https://open.fda.gov/apis/authentication/).

The openFDA field-reference page appears stale relative to the live API: it lists 11 fields and uses `approval_name`, `approval_title`, and `approval_center`, while current responses use `approver_name`, `approver_title`, and `approver_center` and also include `letter_year` and `approval_status`. Validate the schema from live responses and tolerate new fields. FDA itself cautions that openFDA may rename source fields and converts the records to JSON ([dataset overview](https://open.fda.gov/apis/transparency/completeresponseletters/), [field reference](https://open.fda.gov/apis/transparency/completeresponseletters/searchable-fields/)).

## PDFs and text

The API provides extracted text but no per-record PDF URL field. FDA also provides two bulk PDF archives: [approved_CRLs.zip](https://download.open.fda.gov/approved_CRLs.zip) and [unapproved_CRLs.zip](https://download.open.fda.gov/unapproved_CRLs.zip). Match a PDF to an API record using `file_name` and, as a secondary check, the application number and letter date. The live record filenames include `.pdf`. The site labels the files as redacted public copies; CCI and trade secrets are redacted before release. Preserve both API text and the PDF: OCR/text extraction may be imperfect, while the source PDF retains layout and redaction context.

## Corpus coverage and analysis limits

- FDA says the database covers CRLs associated with approved and unapproved NDAs and BLAs, includes letters issued as recently as 2025, and may add archived letters for withdrawn and approved applications. Its overview's “Key Facts” separately says “2020-2024 null” and update frequency “Infrequently”; the live API has 59 records with `letter_year=2025`. Treat the live API and release date as the operational truth, and record snapshots because the dataset is changing.
- This is a disclosure corpus, not a complete census of all FDA non-approval decisions or applications. The published population is shaped by the agency's release and redaction process; historical additions can create uneven time coverage. The API scope statement names NDAs and BLAs, so do not assume it covers ANDAs or other FDA centers/programs comprehensively.
- A CRL says the application will not be approved in its current form; it is not a final rejection. FDA states that letters describe deficiencies and may recommend actions. `approval_status` should not automatically be interpreted as the outcome of the individual letter; it is a separate API field, and follow-on approval/outcome linkage needs an independent source and explicit matching rules.
- Redactions, missing detail, variable letter structure, multiple applications/centers per record, and OCR artifacts constrain text-only comparisons. Counts measure themes in disclosed letters, not prevalence across all submitted applications or causal predictors of approval.

## Practical issue taxonomy

Use a multi-label scheme because one letter can identify several independent blockers. Capture the source heading/paragraph and classify the deficiency separately from FDA's additional, non-blocking comments. An initial broad taxonomy can include clinical efficacy, clinical safety, product quality/CMC, manufacturing/facility/GMP, device/human factors, nonclinical, biopharmaceutics/PK, labeling, and administrative/procedural. These labels are an analysis layer, not an FDA-provided controlled vocabulary; retain original headings and an `other/unclear` path. Record approvability/blocking status, requested action, discipline, and evidence span independently. Avoid inferring severity or eventual outcome from a keyword alone.

## RXA (`rxa.justinyan.com`) feature inventory

RXA presents itself as “FDA Approvals, visualized,” rather than a CRL explorer. The public client loads a static approvals dataset and renders four views: Market Share, Top 10, Timeline, and a paginated/sortable table. Shared filters include approval period/date, FDA center, therapeutic area, developer, distributor, modality, target, route, revenue ranges, and epistemic status; selected values can be cleared, and list-valued fields can filter by clicking a datum. Charts support interactive points/tooltips and constituent items. Drug detail panels show approval attributes, indication, and a research report; organization detail panels include operating status, founding date, headquarters, ticker, successor, therapeutic/modality focus, website, and an organization report. The data model exposes per-record fields such as approval date, FDA center, therapeutic area, modality, target, route, peak/cumulative revenue, and `epistemic_status` values `hallucinated` / `human_checked`. That epistemic-status marker is a useful pattern for making evidence quality visible.

Sources inspected: [RXA landing page](https://rxa.justinyan.com/), its [client script](https://rxa.justinyan.com/app.js), and [data asset](https://rxa.justinyan.com/data.js). The dashboard is a static third-party analysis; it does not establish FDA endorsement or source-ground every enrichment field from its interface alone.

## Official references

- [Complete Response Letters overview, scope, redactions, and PDF archive links](https://open.fda.gov/apis/transparency/completeresponseletters/)
- [Endpoint usage and request limits](https://open.fda.gov/apis/transparency/completeresponseletters/how-to-use-the-endpoint/)
- [Searchable fields](https://open.fda.gov/apis/transparency/completeresponseletters/searchable-fields/)
- [Example CRL queries](https://open.fda.gov/apis/transparency/completeresponseletters/example-api-queries/)
- [Understanding result shape](https://open.fda.gov/apis/transparency/completeresponseletters/understanding-the-api-results/)
- [FDA rate limits](https://open.fda.gov/apis/authentication/)

## Rule taxonomy audit against the fetched corpus

Read-only audit of `failure_mode/taxonomy.py` against `data/raw/openfda_crl.json` (458 records). The classifier is best treated as a candidate-mention finder: any category hit needs a supporting excerpt and should not be described as the definitive reason an application failed. The taxonomy file changed during this audit, so these counts describe the current version at inspection, not a stable benchmark: 283 records matched at least one topic; 10 of 16 topics matched. Counts by topic were facility 233, safety 31, human factors 15, stability 13, efficacy 10, CMC quality 10, trial design 3, assay/potency 2, bioavailability 1, and data integrity 1. Clinical data, immunogenicity, labeling, nonclinical, pediatric, and microbiology matched zero.

Actual FDA wording that should seed broader candidate-mention patterns includes:

- Nonclinical: “You have not provided adequate nonclinical data to support …” — `CRL_NDA218506_20240613.pdf`.
- Immunogenicity: “insufficient follow up data” to determine whether a reduction was caused by immunogenicity, described as a potential risk — `761184_2023_Orig1s000OtherActionLtrs.pdf`.
- Microbiology: “Lack of method suitability data for endotoxin, sterility, and antimicrobial effectiveness testing” — `210605_2020_Orig1s000OtherActionLtrs.pdf`.
- Pediatric: “insufficient number of untrained injection-naive pediatric patients” in each human-factors study group — `210605_2020_Orig1s000OtherActionLtrs.pdf`.
- Labeling: an Instructions for Use identifies areas to modify from a medication-error perspective — `210605_2020_Orig1s000OtherActionLtrs.pdf`.
- Efficacy: a “single … phase 3 pivotal trial failed on the co-primary endpoint” — `212122_2021_Orig1s000OtherActionLtrs.pdf`.

The earlier taxonomy version had an optional-negative validation pattern that could match affirmative wording such as “is validated.” The current file explicitly requires negative language in its manufacturing/assay validation patterns, which removes that specific false-positive path. The high facility count (233) merits spot-checking to ensure the UI describes it as evidence of a phrase match, since an inspection deficiency mention can appear alongside other issues and is not itself a complete causal explanation.
