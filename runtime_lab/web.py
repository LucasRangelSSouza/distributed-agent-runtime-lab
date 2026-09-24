"""Small local HTTP surface for the runtime demonstration.

It deliberately depends only on the Python standard library so a reader can
run the walkthrough before choosing a web framework or a model provider.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from runtime_lab.runtime import Runtime


STATIC_ROOT = Path(__file__).with_name("static")
RUNTIME = Runtime()
WORKERS = ["worker-amber", "worker-slate"]
MAX_MESSAGE_LENGTH = 2_000


def execute(request_id: str, message: str, conversation_id: str | None = None) -> dict[str, object]:
    """Run an intentionally deterministic worker and return safe UI fields."""
    was_completed = request_id in RUNTIME.requests and RUNTIME.requests[request_id].status == "completed"
    state = RUNTIME.process(request_id, WORKERS, lambda _: f"Worker received: {message.strip()}", conversation_id=conversation_id)
    return {
        "request_id": state.request_id,
        "conversation_id": state.conversation_id,
        "status": state.status,
        "worker_id": state.worker_id,
        "response": state.response,
        "attempts": state.attempts,
        "cache_hit": was_completed,
    }


class RuntimeHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - required stdlib method name
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            self._send_file("index.html", "text/html; charset=utf-8")
        elif path == "/healthz":
            self._send_json(HTTPStatus.OK, {"status": "ok", "workers": WORKERS})
        elif path.startswith("/assets/"):
            asset = path.removeprefix("/")
            content_type = guess_type(asset)[0] or "application/octet-stream"
            self._send_file(asset, f"{content_type}; charset=utf-8")
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - required stdlib method name
        if urlparse(self.path).path != "/api/messages":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            message = str(payload.get("message", "")).strip()
            request_id = str(payload.get("request_id") or uuid4())
            conversation_id = str(payload.get("conversation_id") or uuid4())
            if not message or len(message) > MAX_MESSAGE_LENGTH:
                raise ValueError("message must contain 1 to 2000 characters")
        except (ValueError, json.JSONDecodeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "message must contain 1 to 2000 characters"})
            return
        self._send_json(HTTPStatus.OK, execute(request_id, message, conversation_id))

    def _send_file(self, name: str, content_type: str) -> None:
        target = (STATIC_ROOT / name).resolve()
        if STATIC_ROOT.resolve() not in target.parents or not target.is_file():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        """Keep the demo output focused on explicit validation messages."""


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8080), RuntimeHandler)
    print("Runtime demo available at http://localhost:8080")
    server.serve_forever()


if __name__ == "__main__":
    main()
