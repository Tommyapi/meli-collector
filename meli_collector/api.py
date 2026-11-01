"""Read-only local HTTP API."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from .config import api_port, db_path
from .store import Store

HOST = "127.0.0.1"


class Handler(BaseHTTPRequestHandler):
    server_version = "meli-collector/0.1"

    def log_message(self, fmt: str, *args: object) -> None:
        print("[api] " + fmt % args, flush=True)

    def _send(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        try:
            with Store(db_path()) as store:
                if path == "/health":
                    self._send(200, {"ok": True, "service": "meli-collector", "db": db_path()})
                elif path == "/search":
                    keyword = parse_qs(parsed.query).get("kw", [None])[0]
                    self._send(200, {"keyword": keyword, "rows": store.latest_listings(keyword)})
                elif path.startswith("/item/"):
                    item_id = unquote(path.rsplit("/", 1)[-1]).upper().replace("-", "")
                    row = store.latest_item(item_id)
                    self._send(200 if row else 404, row or {"error": "not_found", "item_id": item_id})
                elif path.startswith("/growth/"):
                    item_id = unquote(path.rsplit("/", 1)[-1]).upper().replace("-", "")
                    self._send(200, {"item_id": item_id, "rows": store.growth(item_id)})
                else:
                    self._send(404, {"error": "not_found"})
        except Exception as exc:
            self._send(500, {"error": type(exc).__name__, "message": str(exc)})


def main() -> None:
    port = api_port()
    server = ThreadingHTTPServer((HOST, port), Handler)
    print(f"meli-collector API listening on http://{HOST}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
