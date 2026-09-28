"""Start the dashboard independently of an interactive tool or terminal session."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def healthy(url: str) -> bool:
    try:
        with urlopen(url + "/api/health", timeout=1) as response:
            return response.status == 200 and json.load(response).get("ok") is True
    except (OSError, URLError, ValueError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    url = f"http://127.0.0.1:{args.port}"
    if healthy(url):
        print(f"Dashboard already responds at {url}")
        return
    runtime = ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    log_path = runtime / f"server-{args.port}.log"
    with log_path.open("ab", buffering=0) as log:
        process = subprocess.Popen(
            [sys.executable, "-u", "-m", "failure_mode.server", "--port", str(args.port)],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
            close_fds=True,
        )
    for _ in range(30):
        if process.poll() is not None:
            raise SystemExit(f"Server failed to start. See {log_path}")
        if healthy(url):
            (runtime / f"server-{args.port}.pid").write_text(str(process.pid) + "\n")
            print(f"Dashboard: {url}\nPID: {process.pid}\nLog: {log_path}")
            return
        time.sleep(0.2)
    raise SystemExit(f"Server did not become ready. See {log_path}")


if __name__ == "__main__":
    main()
