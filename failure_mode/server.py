"""Small dependency-free API and static web server."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sqlite3
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .store import DEFAULT_DB, ROOT, connect, export_data, get_letter, list_letters, stats, taxonomy

WEB_ROOT = ROOT / "web"


class Handler(BaseHTTPRequestHandler):
    db_path: Path = DEFAULT_DB
    web_root: Path = WEB_ROOT

    def _write(self, status: int, payload: bytes, content_type: str, filename: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store" if self.path.startswith("/api/") else "no-cache")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _json(self, status: int, value: object) -> None:
        self._write(status, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)
        params = {key: value[-1] for key, value in parse_qs(parsed.query, keep_blank_values=True).items()}
        if path.startswith("/api/"):
            try:
                with connect(self.db_path) as db:
                    if path == "/api/health":
                        db.execute("SELECT 1 FROM letters LIMIT 1")
                        return self._json(200, {"ok": True})
                    if path == "/api/stats":
                        return self._json(200, stats(db, params))
                    if path == "/api/letters":
                        return self._json(200, list_letters(db, params))
                    if path.startswith("/api/letters/"):
                        letter_id = path.removeprefix("/api/letters/")
                        item = get_letter(db, letter_id)
                        return self._json(200, item) if item else self._json(404, {"error": "letter not found"})
                    if path == "/api/taxonomy":
                        return self._json(200, taxonomy(db))
                    if path == "/api/export":
                        fmt = params.get("format", "jsonl")
                        body, content_type = export_data(db, params, fmt)
                        return self._write(200, body, content_type, f"fda-crl.{fmt}")
            except ValueError as exc:
                return self._json(400, {"error": str(exc)})
            except sqlite3.OperationalError as exc:
                return self._json(503, {"error": "database unavailable", "detail": str(exc)})
            return self._json(404, {"error": "unknown endpoint"})
        return self._static(path)

    def _static(self, path: str) -> None:
        relative = (path.lstrip("/") or "index.html")
        target = (self.web_root / relative).resolve()
        root = self.web_root.resolve()
        if not target.is_relative_to(root) or not target.is_file():
            return self._json(404, {"error": "file not found"})
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if mime.startswith("text/") or mime in ("application/javascript", "application/json"):
            mime += "; charset=utf-8"
        self._write(200, target.read_bytes(), mime)


def make_server(host: str = "127.0.0.1", port: int = 8000, db_path: Path = DEFAULT_DB, web_root: Path = WEB_ROOT) -> ThreadingHTTPServer:
    class ConfiguredHandler(Handler):
        pass
    ConfiguredHandler.db_path = db_path
    ConfiguredHandler.web_root = web_root
    return ThreadingHTTPServer((host, port), ConfiguredHandler)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("FAILURE_MODE_DB", DEFAULT_DB)))
    args = parser.parse_args(argv)
    with make_server(args.host, args.port, args.db) as server:
        print(f"Serving http://{args.host}:{server.server_port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
