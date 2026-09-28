"""SQLite store and read-only query helpers for published openFDA letters."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from .taxonomy import DEV, RULESET_VERSION, TOPICS, TOPIC_BY_ID, classify

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "crl.sqlite3"
SOURCE_URL = "https://api.fda.gov/transparency/crl.json?limit=1000"


def connect(path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def initialize(db: sqlite3.Connection) -> None:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS letters (
          id TEXT PRIMARY KEY,
          file_name TEXT NOT NULL,
          company_name TEXT NOT NULL,
          application_number TEXT NOT NULL,
          application_type TEXT NOT NULL,
          letter_date TEXT,
          letter_year INTEGER,
          letter_type TEXT,
          status TEXT NOT NULL,
          pdf_url TEXT NOT NULL,
          text TEXT NOT NULL,
          text_preview TEXT NOT NULL,
          source_record TEXT NOT NULL,
          source_sha256 TEXT NOT NULL,
          ingested_at TEXT NOT NULL,
          text_status TEXT NOT NULL DEFAULT 'available'
        );
        CREATE TABLE IF NOT EXISTS evidence (
          letter_id TEXT NOT NULL REFERENCES letters(id) ON DELETE CASCADE,
          category_id TEXT NOT NULL,
          excerpt TEXT NOT NULL,
          start INTEGER NOT NULL,
          end INTEGER NOT NULL,
          method TEXT NOT NULL,
          PRIMARY KEY(letter_id, category_id)
        );
        CREATE TABLE IF NOT EXISTS source_snapshots (
          sha256 TEXT PRIMARY KEY,
          url TEXT NOT NULL,
          fetched_at TEXT NOT NULL,
          last_updated TEXT,
          total_reported INTEGER,
          record_count INTEGER NOT NULL,
          raw_path TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS letters_date_idx ON letters(letter_date);
        CREATE INDEX IF NOT EXISTS letters_year_idx ON letters(letter_year);
        CREATE INDEX IF NOT EXISTS letters_status_idx ON letters(status);
        CREATE INDEX IF NOT EXISTS evidence_category_idx ON evidence(category_id);
        CREATE VIRTUAL TABLE IF NOT EXISTS letters_fts USING fts5(id UNINDEXED, company_name, application_number, text, tokenize='unicode61');
    """)
    columns = {row[1] for row in db.execute("PRAGMA table_info(letters)")}
    if "text_status" not in columns:
        db.execute("ALTER TABLE letters ADD COLUMN text_status TEXT NOT NULL DEFAULT 'available'")


def _date(value: str | None) -> str | None:
    if not value:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _application_type(numbers: list[str]) -> str:
    joined = " ".join(numbers).upper()
    if re.search(r"\bBL\s*\d", joined):
        return "BLA"
    for kind in ("BLA", "NDA", "ANDA"):
        if re.search(rf"\b{kind}\b", joined):
            return kind
    return "Unknown"


def ingest_snapshot(db: sqlite3.Connection, payload: bytes, raw_path: str, fetched_at: str | None = None, source_url: str = SOURCE_URL, ingested_at: str | None = None) -> dict:
    """Validate a complete API snapshot, then upsert it atomically."""
    data = json.loads(payload)
    records = data.get("results")
    meta = data.get("meta", {})
    if not isinstance(records, list):
        raise ValueError("openFDA results must be a list")
    reported = meta.get("results", {}).get("total")
    if reported is not None and len(records) != int(reported):
        raise ValueError(f"incomplete snapshot: {len(records)} of {reported} records")
    if not records:
        raise ValueError("empty snapshot")
    names = [record.get("file_name") for record in records]
    if any(not isinstance(name, str) or not name for name in names):
        raise ValueError("missing file_name in source snapshot")
    # Older FDA PDFs can contain several dated letters, so file_name alone is not unique.
    keys = [(record.get("file_name"), record.get("letter_date"), json.dumps(record.get("application_number"), sort_keys=True)) for record in records]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate letter identity in source snapshot")
    ids = [hashlib.sha256(json.dumps(key, separators=(",", ":")).encode()).hexdigest()[:20] for key in keys]
    digest = hashlib.sha256(payload).hexdigest()
    fetched_at = fetched_at or datetime.now(timezone.utc).isoformat()
    ingested_at = ingested_at or datetime.now(timezone.utc).isoformat()
    initialize(db)
    with db:
        db.execute("INSERT OR REPLACE INTO source_snapshots VALUES (?,?,?,?,?,?,?)", (digest, source_url, fetched_at, meta.get("last_updated"), reported, len(records), raw_path))
        for record, letter_id in zip(records, ids):
            filename = record["file_name"]
            numbers = record.get("application_number") or []
            if isinstance(numbers, str):
                numbers = [numbers]
            numbers = [str(n) for n in numbers]
            body = record.get("text") or ""
            date = _date(record.get("letter_date"))
            status = str(record.get("approval_status") or "Unknown")
            preview = re.sub(r"\s+", " ", body).strip()[:320]
            source_record = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            pdf_url = "https://download.open.fda.gov/crl/" + quote(filename) if filename.lower().endswith(".pdf") else ""
            text_status = "available" if body.strip() else "source_text_missing"
            values = (letter_id, filename, str(record.get("company_name") or "Unknown company"), json.dumps(numbers), _application_type(numbers), date, int(date[:4]) if date else None, record.get("letter_type"), status, pdf_url, body, preview, source_record, digest, ingested_at, text_status)
            db.execute("""INSERT INTO letters VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET file_name=excluded.file_name, company_name=excluded.company_name,
                application_number=excluded.application_number, application_type=excluded.application_type,
                letter_date=excluded.letter_date, letter_year=excluded.letter_year, letter_type=excluded.letter_type,
                status=excluded.status, pdf_url=excluded.pdf_url, text=excluded.text, text_preview=excluded.text_preview,
                source_record=excluded.source_record, source_sha256=excluded.source_sha256, ingested_at=excluded.ingested_at,
                text_status=excluded.text_status""", values)
            db.execute("DELETE FROM evidence WHERE letter_id=?", (letter_id,))
            for item in classify(body):
                db.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?)", (letter_id, item["category_id"], item["excerpt"], item["start"], item["end"], item["method"]))
            db.execute("DELETE FROM letters_fts WHERE id=?", (letter_id,))
            db.execute("INSERT INTO letters_fts(id, company_name, application_number, text) VALUES (?,?,?,?)", (letter_id, record.get("company_name") or "", " ".join(numbers), body))
        # A fetched full snapshot is authoritative; remove records no longer published.
        placeholders = ",".join("?" for _ in ids)
        db.execute(f"DELETE FROM letters_fts WHERE id NOT IN ({placeholders})", ids)
        db.execute(f"DELETE FROM letters WHERE id NOT IN ({placeholders})", ids)
        for key, value in (("source_sha256", digest), ("source_updated", meta.get("last_updated") or ""), ("source_fetched_at", fetched_at), ("ingested_at", ingested_at), ("source_url", source_url), ("taxonomy_version", RULESET_VERSION)):
            db.execute("INSERT INTO metadata VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    return {"count": len(records), "sha256": digest, "source_updated": meta.get("last_updated"), "fetched_at": fetched_at, "ingested_at": ingested_at}


def _filters(params: dict) -> tuple[str, list]:
    clauses = []
    values: list = []
    q = str(params.get("q") or "").strip()
    if q:
        # Quote each Unicode word: user punctuation cannot become FTS syntax.
        tokens = re.findall(r"\w+", q, re.UNICODE)[:16]
        if tokens:
            clauses.append("l.id IN (SELECT id FROM letters_fts WHERE letters_fts MATCH ?)")
            values.append(" AND ".join('"' + token.replace('"', '""') + '"' for token in tokens))
    year = str(params.get("year") or "").strip()
    if year:
        if not re.fullmatch(r"\d{4}", year):
            raise ValueError("year must be a four-digit year")
        clauses.append("l.letter_year=?")
        values.append(int(year))
    category = str(params.get("category") or "").strip()
    if category:
        if category not in TOPIC_BY_ID:
            raise ValueError("unknown category")
        clauses.append("EXISTS (SELECT 1 FROM evidence e WHERE e.letter_id=l.id AND e.category_id=?)")
        values.append(category)
    status = str(params.get("status") or "").strip().lower()
    if status:
        if status not in ("approved", "unapproved", "unknown"):
            raise ValueError("status must be approved or unapproved")
        clauses.append("LOWER(l.status)=?")
        values.append(status)
    app_type = str(params.get("application_type") or "").strip().upper()
    if app_type:
        if app_type not in ("NDA", "BLA", "ANDA", "UNKNOWN"):
            raise ValueError("unknown application_type")
        clauses.append("UPPER(l.application_type)=?")
        values.append(app_type)
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), values


def _metadata(db: sqlite3.Connection) -> dict:
    return {row["key"]: row["value"] for row in db.execute("SELECT key,value FROM metadata")}


def _categories(db: sqlite3.Connection, letter_id: str) -> list[dict]:
    ids = {r[0] for r in db.execute("SELECT category_id FROM evidence WHERE letter_id=?", (letter_id,))}
    return [{"id": topic.id, "label": topic.label} for topic in TOPICS if topic.id in ids]


def _summary(db: sqlite3.Connection, row: sqlite3.Row) -> dict:
    evidence = db.execute("SELECT excerpt FROM evidence WHERE letter_id=? ORDER BY start LIMIT 1", (row["id"],)).fetchone()
    evidence_preview = re.sub(r"\s+", " ", evidence[0]).strip()[:340] if evidence else None
    return {"id": row["id"], "company_name": row["company_name"], "application_number": json.loads(row["application_number"]), "application_type": row["application_type"], "letter_date": row["letter_date"], "letter_type": row["letter_type"], "status": row["status"], "file_name": row["file_name"], "pdf_url": row["pdf_url"] or None, "text_status": row["text_status"], "text_preview": row["text_preview"], "evidence_preview": evidence_preview, "categories": _categories(db, row["id"])}


def list_letters(db: sqlite3.Connection, params: dict) -> dict:
    where, values = _filters(params)
    limit = _bounded_int(params.get("limit"), 25, 1, 1000)
    offset = _bounded_int(params.get("offset"), 0, 0, 1000000)
    sort = str(params.get("sort") or "date_desc")
    order = {"date_desc": "l.letter_date DESC, l.id", "date_asc": "l.letter_date ASC, l.id", "company": "l.company_name COLLATE NOCASE ASC, l.id"}.get(sort)
    if order is None:
        raise ValueError("sort must be date_desc, date_asc, or company")
    total = db.execute("SELECT COUNT(*) FROM letters l" + where, values).fetchone()[0]
    rows = db.execute("SELECT l.* FROM letters l" + where + f" ORDER BY {order} LIMIT ? OFFSET ?", [*values, limit, offset]).fetchall()
    return {"total": total, "results": [_summary(db, row) for row in rows], "limit": limit, "offset": offset}


def _bounded_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        raise ValueError("limit and offset must be integers") from None
    if number < minimum or number > maximum:
        raise ValueError(f"value must be between {minimum} and {maximum}")
    return number


def get_letter(db: sqlite3.Connection, letter_id: str) -> dict | None:
    row = db.execute("SELECT * FROM letters WHERE id=?", (letter_id,)).fetchone()
    if row is None:
        return None
    result = _summary(db, row)
    result["text"] = row["text"]
    result["evidence"] = [dict(item) for item in db.execute("SELECT category_id, excerpt, start, end, method FROM evidence WHERE letter_id=? ORDER BY category_id", (letter_id,))]
    for item in result["evidence"]:
        item["category_label"] = TOPIC_BY_ID[item["category_id"]].label
    meta = _metadata(db)
    result["provenance"] = {"source_url": meta.get("source_url", SOURCE_URL), "source_updated": meta.get("source_updated"), "source_fetched_at": meta.get("source_fetched_at"), "source_sha256": row["source_sha256"], "record_sha256": hashlib.sha256(row["source_record"].encode()).hexdigest(), "ingested_at": row["ingested_at"], "file_name": row["file_name"], "taxonomy_version": meta.get("taxonomy_version")}
    return result


def stats(db: sqlite3.Connection, params: dict | None = None) -> dict:
    params = params or {}
    where, values = _filters(params)
    base = " FROM letters l" + where
    total = db.execute("SELECT COUNT(*)" + base, values).fetchone()[0]
    applications = set()
    for row in db.execute("SELECT l.application_number" + base, values):
        applications.update(json.loads(row[0]))
    text_available = db.execute("SELECT COUNT(*) FROM letters l" + (where + " AND " if where else " WHERE ") + "length(l.text)>0", values).fetchone()[0]
    unapproved = db.execute("SELECT COUNT(*) FROM letters l" + (where + " AND " if where else " WHERE ") + "LOWER(l.status)='unapproved'", values).fetchone()[0]
    years = [{"year": row[0], "count": row[1]} for row in db.execute("SELECT l.letter_year,COUNT(*)" + base + " GROUP BY l.letter_year ORDER BY l.letter_year DESC", values) if row[0] is not None]
    categories = []
    for topic in TOPICS:
        clause = (where + " AND " if where else " WHERE ") + "EXISTS (SELECT 1 FROM evidence e WHERE e.letter_id=l.id AND e.category_id=?)"
        count = db.execute("SELECT COUNT(*) FROM letters l" + clause, [*values, topic.id]).fetchone()[0]
        categories.append({"id": topic.id, "label": topic.label, "count": count})
    meta = _metadata(db)
    return {"total_letters": total, "corpus_total": db.execute("SELECT COUNT(*) FROM letters").fetchone()[0], "total_applications": len(applications), "text_available": text_available, "unapproved": unapproved, "years": years, "categories": categories, "source_updated": meta.get("source_updated"), "source_fetched_at": meta.get("source_fetched_at"), "ingested_at": meta.get("ingested_at"), "taxonomy_version": meta.get("taxonomy_version"), "coverage_note": "Counts describe published FDA letters in this dataset only. Topic categories are rule-based text mentions, not adjudicated causes. Approval status is the FDA dataset application status, not verified current market status; these counts are not approval probabilities."}


def taxonomy(db: sqlite3.Connection) -> dict:
    counts = {row[0]: row[1] for row in db.execute("SELECT category_id, COUNT(*) FROM evidence GROUP BY category_id")}
    result = []
    for topic in TOPICS:
        examples = []
        for row in db.execute("SELECT l.* FROM letters l JOIN evidence e ON e.letter_id=l.id WHERE e.category_id=? ORDER BY l.letter_date DESC LIMIT 3", (topic.id,)):
            examples.append({"id": row["id"], "company_name": row["company_name"], "letter_date": row["letter_date"], "application_number": json.loads(row["application_number"]), "text_preview": row["text_preview"]})
        result.append({"id": topic.id, "label": topic.label, "description": topic.description, "question": topic.question, "stages": list(dict.fromkeys((DEV, *topic.stages))), "terms": list(topic.terms), "count": counts.get(topic.id, 0), "examples": examples})
    return {"categories": result, "method": "rule-based topic mentions; not adjudicated causes", "taxonomy_version": _metadata(db).get("taxonomy_version")}


def export_data(db: sqlite3.Connection, params: dict, fmt: str) -> tuple[bytes, str]:
    where, values = _filters(params)
    rows = db.execute("SELECT l.* FROM letters l" + where + " ORDER BY l.letter_date DESC, l.id", values)
    if fmt == "jsonl":
        lines = []
        for row in rows:
            item = get_letter(db, row["id"])
            lines.append(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
        return ("\n".join(lines) + ("\n" if lines else "")).encode(), "application/x-ndjson; charset=utf-8"
    if fmt == "csv":
        def safe(value: object) -> object:
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                return "'" + value
            return value
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(("id", "company_name", "application_number", "application_type", "letter_date", "letter_type", "status", "file_name", "pdf_url", "categories", "text", "source_sha256"))
        for row in rows:
            writer.writerow([safe(value) for value in (row["id"], row["company_name"], "; ".join(json.loads(row["application_number"])), row["application_type"], row["letter_date"], row["letter_type"], row["status"], row["file_name"], row["pdf_url"], "; ".join(x["id"] for x in _categories(db, row["id"])), row["text"], row["source_sha256"])])
        return output.getvalue().encode("utf-8"), "text/csv; charset=utf-8"
    raise ValueError("format must be jsonl or csv")
