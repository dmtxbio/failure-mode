"""Exercise the HTTP API against the local indexed FDA snapshot."""

import json
import threading
import urllib.request

from failure_mode.server import make_server
from failure_mode.store import DEFAULT_DB


def main():
    server = make_server(port=0, db_path=DEFAULT_DB)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        for path in (
            "/api/health",
            "/api/stats?year=2026",
            "/api/letters?q=facility&status=unapproved&limit=2",
            "/api/taxonomy",
            "/api/export?format=jsonl&year=2026",
            "/api/export?format=csv&category=facility",
        ):
            with urllib.request.urlopen(base + path, timeout=10) as response:
                body = response.read()
                assert response.status == 200, path
                assert body, path
                print(path, response.status, len(body))
                if path.startswith("/api/stats"):
                    stats = json.loads(body)
                    assert stats["corpus_total"] > 0
                    assert 0 <= stats["total_letters"] <= stats["corpus_total"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
