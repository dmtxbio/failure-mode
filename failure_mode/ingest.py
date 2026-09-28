"""Fetch all published openFDA CRLs and build the local search database."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .store import DEFAULT_DB, ROOT, SOURCE_URL, connect, ingest_snapshot

RAW_PATH = ROOT / "data" / "raw" / "openfda_crl.json"
USER_AGENT = "failure-mode-explorer/0.1 (public FDA data research)"


def _fetch_page(skip: int, limit: int, retries: int = 4) -> bytes:
    query = urllib.parse.urlencode({"limit": limit, "skip": skip})
    url = "https://api.fda.gov/transparency/crl.json?" + query
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            retryable = not isinstance(exc, urllib.error.HTTPError) or exc.code in (429, 500, 502, 503, 504)
            if attempt == retries or not retryable:
                raise
            time.sleep(min(12, (2 ** attempt) + random.random()))
    raise AssertionError("unreachable")


def fetch_all(page_size: int = 1000) -> bytes:
    """Page the API, rejecting incomplete or changing snapshots."""
    if not 1 <= page_size <= 1000:
        raise ValueError("page_size must be between 1 and 1000")
    records: list[dict] = []
    total = None
    last_updated = None
    first_meta = None
    skip = 0
    while total is None or skip < total:
        page = json.loads(_fetch_page(skip, page_size))
        page_meta = page.get("meta", {})
        page_results = page.get("results")
        if not isinstance(page_results, list):
            raise ValueError("openFDA did not return a results list")
        reported = int(page_meta.get("results", {}).get("total", -1))
        if reported < 0:
            raise ValueError("openFDA omitted total")
        if total is None:
            total = reported
            last_updated = page_meta.get("last_updated")
            first_meta = page_meta
        elif reported != total or page_meta.get("last_updated") != last_updated:
            raise ValueError("openFDA changed during pagination; retry ingestion")
        if not page_results:
            raise ValueError("openFDA returned an empty page before total")
        records.extend(page_results)
        skip += len(page_results)
        if skip > total:
            raise ValueError("openFDA returned more records than reported")
    first_meta = dict(first_meta or {})
    first_meta["results"] = {"skip": 0, "limit": page_size, "total": total}
    return json.dumps({"meta": first_meta, "results": records}, ensure_ascii=False, indent=2).encode("utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cached", action="store_true", help="Use the checked-in raw response without network access")
    parser.add_argument("--raw", type=Path, default=RAW_PATH)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--page-size", type=int, default=1000)
    args = parser.parse_args(argv)
    sidecar = args.raw.with_suffix(".meta.json")
    if args.cached:
        payload = args.raw.read_bytes()
        if sidecar.exists():
            cache_meta = json.loads(sidecar.read_text())
            if cache_meta.get("sha256") != hashlib.sha256(payload).hexdigest():
                raise ValueError("raw cache hash does not match metadata")
            fetched_at = cache_meta["fetched_at"]
        else:
            fetched_at = datetime.fromtimestamp(args.raw.stat().st_mtime, timezone.utc).isoformat()
    else:
        payload = fetch_all(args.page_size)
        fetched_at = datetime.now(timezone.utc).isoformat()
        args.raw.parent.mkdir(parents=True, exist_ok=True)
        temp = args.raw.with_suffix(".tmp")
        temp.write_bytes(payload)
        temp.replace(args.raw)
        sidecar.write_text(json.dumps({"source_url": SOURCE_URL, "fetched_at": fetched_at, "sha256": hashlib.sha256(payload).hexdigest(), "source_updated": json.loads(payload)["meta"].get("last_updated"), "record_count": len(json.loads(payload)["results"])}, indent=2) + "\n")
    args.db.parent.mkdir(parents=True, exist_ok=True)
    with connect(args.db) as db:
        result = ingest_snapshot(db, payload, str(args.raw), fetched_at, SOURCE_URL)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
