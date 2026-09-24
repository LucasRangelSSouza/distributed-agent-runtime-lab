"""Small local HTTP surface for the runtime demonstration.

It deliberately depends only on the Python standard library so a reader can
run the walkthrough before choosing a web framework or a model provider.
"""

from __future__ import annotations

import json
import os
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from runtime_lab.runtime import Runtime
from runtime_lab.redis_state import RedisState


STATIC_ROOT = Path(__file__).with_name("static")
RUNTIME = Runtime()
WORKERS = ["worker-amber", "worker-slate"]
MAX_MESSAGE_LENGTH = 2_000
REDIS_STATE = RedisState.from_url(os.environ["REDIS_URL"]) if os.environ.get("REDIS_URL") else None


def execute(request_id: str, message: str, conversation_id: str | None = None) -> dict[str, object]:
    """Run an intentionally deterministic worker and return safe UI fields."""
    if REDIS_STATE:
        redis_state, created = REDIS_STATE.submit(request_id, conversation_id or request_id)
        if not created:
            return {**redis_state, "cache_hit": redis_state["status"] == "completed"}
        REDIS_STATE.enqueue(request_id, conversation_id or request_id, message)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            redis_state = REDIS_STATE.get_request(request_id)
            if redis_state["status"] == "completed":
                return {**redis_state, "cache_hit": False}
            time.sleep(0.05)
        return {**REDIS_STATE.get_request(request_id), "cache_hit": False}
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


def inspect_request(request_id: str) -> dict[str, object]:
    if REDIS_STATE:
        return REDIS_STATE.get_request(request_id)
    state = RUNTIME.requests[request_id]
    return {"request_id": state.request_id, "conversation_id": state.conversation_id, "status": state.status, "worker_id": state.worker_id, "response": state.response, "attempts": state.attempts}


def inspect_conversation(conversation_id: str) -> dict[str, object]:
    messages = REDIS_STATE.get_conversation(conversation_id) if REDIS_STATE else RUNTIME.conversations.get(conversation_id, [])
    return {"conversation_id": conversation_id, "responses": messages}


class RuntimeHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - required stdlib method name
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            self._send_file("index.html", "text/html; charset=utf-8")
        elif path == "/healthz":
            self._send_json(HTTPStatus.OK, {"status": "ok", "workers": WORKERS, "state_backend": "redis" if REDIS_STATE else "in_memory"})
        elif path.startswith("/api/requests/"):
            self._inspect(lambda: inspect_request(path.removeprefix("/api/requests/")))
        elif path.startswith("/api/conversations/"):
            self._inspect(lambda: inspect_conversation(path.removeprefix("/api/conversations/")))
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

    def _inspect(self, loader: Any) -> None:
        try:
            self._send_json(HTTPStatus.OK, loader())
        except KeyError:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def log_message(self, _format: str, *_args: object) -> None:
        """Keep the demo output focused on explicit validation messages."""


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8080), RuntimeHandler)
    print("Runtime demo available at http://localhost:8080")
    server.serve_forever()


if __name__ == "__main__":
    main()
