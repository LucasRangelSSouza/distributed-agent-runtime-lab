"""Deterministic RAG gateway stand-in for the local public-demo profile.

This is NOT the ai-platform-rag-observability service. It mirrors only its
HTTP contract (``POST /v1/answer`` and ``GET /healthz``) so the public-demo
composition can be validated before a pinned RAG image digest exists. It
answers from a small fixture corpus that describes the synthetic education
view, cites dataset and version for every passage, abstains when evidence is
absent, and never logs or stores the question text.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse


MODE = "fixture-stand-in"
DATASET = "public-demo-education-finance-fixture"
DATASET_VERSION = "fixture-2026-09-25"
MAX_QUESTION_LENGTH = 1_000
MAX_BODY_BYTES = 8_192
INJECTION_PATTERNS = ("ignore previous", "system prompt", "reveal instructions")
STOPWORDS = {"about", "does", "from", "have", "how", "into", "that", "the", "this", "what", "when", "with", "which", "are", "for"}

CORPUS: list[dict[str, str]] = [
    {
        "id": "view-grain",
        "content": "The approved municipality education finance view has one row per municipality code and year. It is built from synthetic fixture data, not from an official release.",
    },
    {
        "id": "mde-minimum-share",
        "content": "The column mde_minimum_share_pct reports the share of tax revenue applied to education maintenance and development. The Brazilian constitutional minimum for municipalities is 25 percent.",
    },
    {
        "id": "investment-per-student",
        "content": "The column investment_per_basic_education_student reports annual education spending divided by basic education enrollment, in fixture currency units.",
    },
    {
        "id": "population-column",
        "content": "The population column holds a synthetic resident population per municipality and year so that dashboards can show size bands.",
    },
]


def tokens(text: str) -> set[str]:
    return {part for part in re.findall(r"[a-z0-9_]{3,}", text.casefold()) if part not in STOPWORDS}


def answer(question: str) -> dict[str, Any]:
    """Return a cited answer, an abstention, or a refusal for one question."""
    trace_id = hashlib.sha256(question.encode("utf-8")).hexdigest()[:16]
    base = {"mode": MODE, "trace_id": trace_id}
    normalized = question.casefold()
    if any(pattern in normalized for pattern in INJECTION_PATTERNS):
        return {**base, "status": "refused", "answer": "I can answer questions about the approved demo corpus only.", "citations": [], "safety_reason": "prompt_injection_pattern"}
    query_terms = tokens(question)
    scored = []
    for document in CORPUS:
        overlap = query_terms & tokens(document["content"])
        if len(overlap) >= 2:
            scored.append((len(overlap), document["id"], document))
    if not scored:
        return {**base, "status": "abstained", "answer": "The approved demo corpus does not contain enough evidence to answer this question.", "citations": [], "safety_reason": "insufficient_retrieval"}
    scored.sort(key=lambda item: (-item[0], item[1]))
    best = scored[:2]
    return {
        **base,
        "status": "answered",
        "answer": best[0][2]["content"],
        "citations": [{"document_id": doc["id"], "dataset": DATASET, "dataset_version": DATASET_VERSION, "score": score} for score, _, doc in best],
        "safety_reason": None,
    }


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = "rag-fixture"
    sys_version = ""

    def do_GET(self) -> None:  # noqa: N802 - stdlib method name
        if urlparse(self.path).path == "/healthz":
            self._send(HTTPStatus.OK, {"status": "ok", "mode": MODE, "dataset": DATASET, "dataset_version": DATASET_VERSION})
        else:
            self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib method name
        if urlparse(self.path).path != "/v1/answer":
            self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY_BYTES:
                raise ValueError
            question = str(json.loads(self.rfile.read(length)).get("question", "")).strip()
            if not question or len(question) > MAX_QUESTION_LENGTH:
                raise ValueError
        except (ValueError, AttributeError, json.JSONDecodeError):
            self._send(HTTPStatus.BAD_REQUEST, {"error": "question must contain 1 to 1000 characters"})
            return
        self._send(HTTPStatus.OK, answer(question))

    def _send(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        """Never write request lines or bodies to the container log."""


def main() -> None:
    port = int(os.environ.get("RAG_FIXTURE_PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), FixtureHandler)
    print(f"RAG fixture stand-in listening on port {port} (mode={MODE})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
