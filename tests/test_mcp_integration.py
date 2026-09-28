"""Exercise the public-good adapter through the official MCP SDK client."""

from __future__ import annotations

import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    import anyio
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters
except ModuleNotFoundError:
    anyio = None
    Client = None
    StdioServerParameters = None

SDK_AVAILABLE = anyio is not None


ROOT = Path(__file__).resolve().parents[1]
SERVER_SCRIPT = ROOT / "integrations" / "public_good_mcp.py"


class _CorpusHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/stats":
            response = {"total_letters": 1, "years": [2024]}
        elif parsed.path == "/api/letters":
            query = parse_qs(parsed.query)
            response = {
                "total": 1,
                "results": [{"id": "letter-1", "date": "2024-03-15", "query": query}],
            }
        elif parsed.path == "/api/letters/letter-1":
            response = {
                "id": "letter-1",
                "full_text": "Example public letter text",
                "evidence_excerpts": ["Example excerpt"],
                "provenance": {"url": "https://example.test/source"},
            }
        elif parsed.path == "/api/taxonomy":
            response = {
                "categories": [
                    {
                        "id": "clinical-endpoints",
                        "label": "Clinical endpoints",
                        "description": "Endpoint design and evidence.",
                        "question": "Are endpoints fit for purpose?",
                        "stages": ["Development", "Submission"],
                        "terms": ["endpoint", "outcome measure"],
                        "count": 4,
                        "examples": ["letter-1"],
                    }
                ]
            }
        else:
            self.send_error(404)
            return
        body = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


class PublicGoodMcpIntegrationTest(unittest.TestCase):
    @unittest.skipUnless(SDK_AVAILABLE, "install integrations/requirements.txt to test MCP")
    def test_mcp_client_initializes_lists_and_calls_tools(self) -> None:
        api = ThreadingHTTPServer(("127.0.0.1", 0), _CorpusHandler)
        worker = threading.Thread(target=api.serve_forever, daemon=True)
        worker.start()
        api_base = f"http://127.0.0.1:{api.server_port}"

        async def exercise_server() -> None:
            params = StdioServerParameters(
                command=sys.executable,
                args=[str(SERVER_SCRIPT)],
                env={**os.environ, "PUBLIC_GOOD_API_BASE": api_base},
            )
            async with Client(params) as client:
                listed = await client.list_tools()
                names = {tool.name for tool in listed.tools}
                self.assertEqual(
                    names,
                    {
                        "search_letters",
                        "get_letter",
                        "get_corpus_stats",
                        "get_planning_checklist",
                    },
                )

                searched = await client.call_tool(
                    "search_letters",
                    {
                        "q": "endpoint",
                        "year": 2024,
                        "category": "clinical-endpoints",
                        "status": "unapproved",
                        "application_type": "NDA",
                        "limit": 25,
                        "offset": 0,
                        "sort": "date_desc",
                    },
                )
                self.assertFalse(searched.is_error)
                self.assertEqual(searched.structured_content["total"], 1)
                self.assertEqual(searched.structured_content["results"][0]["query"]["q"], ["endpoint"])

                letter = await client.call_tool("get_letter", {"letter_id": "letter-1"})
                self.assertFalse(letter.is_error)
                self.assertEqual(letter.structured_content["full_text"], "Example public letter text")
                self.assertIn("untrusted source data", letter.structured_content["source_data_notice"])

                stats = await client.call_tool("get_corpus_stats", {})
                self.assertFalse(stats.is_error)
                self.assertEqual(stats.structured_content["stats"]["total_letters"], 1)

                checklist = await client.call_tool(
                    "get_planning_checklist", {"stage": "Development"}
                )
                self.assertFalse(checklist.is_error)
                self.assertEqual(
                    [item["id"] for item in checklist.structured_content["categories"]],
                    ["clinical-endpoints"],
                )
                self.assertIn("does not predict approval", checklist.structured_content["caveat"])

        try:
            anyio.run(exercise_server)
        finally:
            api.shutdown()
            api.server_close()
            worker.join(timeout=2)
