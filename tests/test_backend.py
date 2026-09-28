import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from failure_mode import ingest
from failure_mode.store import connect, export_data, get_letter, ingest_snapshot, list_letters, stats, taxonomy
from failure_mode.taxonomy import classify


def record(filename, date, company, status="Unapproved", text="", application=None):
    return {"file_name": filename, "letter_date": date, "company_name": company, "approval_status": status, "application_number": application or ["NDA 123456"], "letter_type": "COMPLETE RESPONSE", "text": text}


def snapshot(records):
    return json.dumps({"meta": {"last_updated": "2026-08-13", "results": {"total": len(records)}}, "results": records}).encode()


DEFICIENCY = """We have described our reasons for this action below and, where possible,
our recommendations to address these issues.
FACILITY INSPECTIONS
During a recent inspection of the manufacturing facility, our investigator
conveyed deficiencies to its representative. Satisfactory resolution is required.
SAFETY UPDATE
When you respond, include a safety update with all serious adverse events.
"""


class ClassifierTests(unittest.TestCase):
    def test_wrapped_intro_exact_span_and_boilerplate_boundary(self):
        found = classify(DEFICIENCY)
        self.assertEqual([item["category_id"] for item in found], ["facility"])
        self.assertEqual(found[0]["excerpt"], DEFICIENCY[found[0]["start"]:found[0]["end"]])

    def test_positive_validation_and_routine_labeling_are_not_issues(self):
        text = "We have described our reasons for this action below. The assay is validated. The manufacturing process is controlled. PRESCRIBING INFORMATION\nWe reserve comment on the proposed labeling until the application is otherwise adequate.\nSAFETY UPDATE\nThe safety update should include data from all clinical trials."
        self.assertEqual(classify(text), [])

    def test_specific_nonclinical_and_microbiology_findings(self):
        text = "We have described our reasons for this action below. You have not provided adequate nonclinical data to support your application. Lack of method suitability data for endotoxin, sterility, and antimicrobial effectiveness testing (AET)."
        ids = {item["category_id"] for item in classify(text)}
        self.assertEqual(ids, {"nonclinical", "microbiology"})


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = connect(Path(self.tmp.name) / "test.sqlite3")
        self.records = [
            record("shared.pdf", "01/01/2024", "Alpha Labs", "Approved", DEFICIENCY),
            record("shared.pdf", "02/01/2024", "Beta Labs", "Unapproved", "There is a safety concern for anaphylaxis.", ["BL 125706"]),
            record("Under Review for Release", "03/01/2026", "=Formula Corp", "Unapproved", ""),
        ]
        self.payload = snapshot(self.records)
        ingest_snapshot(self.db, self.payload, "raw.json", "2026-09-28T00:00:00Z")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_shared_pdf_unique_letters_and_idempotent_upsert(self):
        before = {x["id"] for x in list_letters(self.db, {"limit": 10})["results"]}
        ingest_snapshot(self.db, self.payload, "raw.json", "2026-09-28T00:00:00Z")
        after = {x["id"] for x in list_letters(self.db, {"limit": 10})["results"]}
        self.assertEqual(len(before), 3)
        self.assertEqual(before, after)
        self.assertEqual(self.db.execute("SELECT count(*) FROM letters_fts").fetchone()[0], 3)
        self.assertEqual(self.db.execute("SELECT count(*) FROM evidence").fetchone()[0], 2)

    def test_search_escaping_filters_and_pagination(self):
        self.assertEqual(list_letters(self.db, {"q": 'Alpha") OR status:Unapproved', "limit": 10})["total"], 0)
        self.assertEqual(list_letters(self.db, {"q": "Alpha", "year": "2024", "category": "facility", "status": "approved"})["total"], 1)
        result = list_letters(self.db, {"year": "2024", "sort": "date_asc", "limit": 1, "offset": 1})
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["results"][0]["company_name"], "Beta Labs")
        self.assertEqual(list_letters(self.db, {"application_type": "BLA"})["total"], 1)
        self.assertEqual(list_letters(self.db, {"q": "shared.pdf"})["total"], 0)

    def test_subset_stats_and_missing_pdf(self):
        filtered = stats(self.db, {"status": "unapproved"})
        self.assertEqual(filtered["total_letters"], 2)
        self.assertEqual(filtered["corpus_total"], 3)
        self.assertEqual(filtered["text_available"], 1)
        pending = next(x for x in list_letters(self.db, {"limit": 10})["results"] if x["file_name"] == "Under Review for Release")
        self.assertIsNone(pending["pdf_url"])
        self.assertEqual(pending["text_status"], "source_text_missing")
        self.assertEqual(len(taxonomy(self.db)["categories"]), 18)
        detail = get_letter(self.db, pending["id"])
        self.assertIn("record_sha256", detail["provenance"])

    def test_export_csv_formula_escape_and_jsonl_filter(self):
        body, _ = export_data(self.db, {"status": "unapproved"}, "csv")
        rows = list(csv.DictReader(io.StringIO(body.decode())))
        self.assertEqual(len(rows), 2)
        self.assertEqual(next(x for x in rows if "Formula" in x["company_name"])["company_name"], "'=Formula Corp")
        body, _ = export_data(self.db, {"category": "facility"}, "jsonl")
        lines = [json.loads(line) for line in body.splitlines()]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["company_name"], "Alpha Labs")

    def test_reject_incomplete_snapshot_without_mutating_store(self):
        bad = json.dumps({"meta": {"results": {"total": 4}}, "results": self.records}).encode()
        with self.assertRaises(ValueError):
            ingest_snapshot(self.db, bad, "bad.json")
        self.assertEqual(stats(self.db)["total_letters"], 3)


class FetchTests(unittest.TestCase):
    def test_pagination_and_inconsistent_total(self):
        one = snapshot([record("a.pdf", "01/01/2024", "A"), record("b.pdf", "01/02/2024", "B")])
        two = snapshot([record("c.pdf", "01/03/2024", "C")])
        one_data = json.loads(one)
        two_data = json.loads(two)
        one_data["meta"]["results"]["total"] = 3
        two_data["meta"]["results"]["total"] = 3
        with patch("failure_mode.ingest._fetch_page", side_effect=[json.dumps(one_data).encode(), json.dumps(two_data).encode()]):
            result = json.loads(ingest.fetch_all(page_size=2))
        self.assertEqual(len(result["results"]), 3)
        two_data["meta"]["results"]["total"] = 4
        with patch("failure_mode.ingest._fetch_page", side_effect=[json.dumps(one_data).encode(), json.dumps(two_data).encode()]):
            with self.assertRaises(ValueError):
                ingest.fetch_all(page_size=2)


if __name__ == "__main__":
    unittest.main()
