"""Redis-backed request and conversation state for the Compose profile."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from redis import Redis


@dataclass
class RedisState:
    client: Any
    prefix: str = "runtime-lab"

    @classmethod
    def from_url(cls, url: str) -> "RedisState":
        return cls(Redis.from_url(url, decode_responses=True))

    def submit(self, request_id: str, conversation_id: str) -> tuple[dict[str, Any], bool]:
        state = {"request_id": request_id, "conversation_id": conversation_id, "status": "queued", "worker_id": None, "response": None, "attempts": 0}
        created = bool(self.client.set(self._request_key(request_id), json.dumps(state), nx=True))
        if created:
            return state, True
        return self.get_request(request_id), False

    def complete(self, request_id: str, worker_id: str, response: str, attempts: int) -> dict[str, Any]:
        state = self.get_request(request_id)
        if state["status"] == "completed":
            return state
        state.update({"status": "completed", "worker_id": worker_id, "response": response, "attempts": attempts})
        self.client.set(self._request_key(request_id), json.dumps(state))
        self.client.rpush(self._conversation_key(state["conversation_id"]), response)
        return state

    def get_request(self, request_id: str) -> dict[str, Any]:
        payload = self.client.get(self._request_key(request_id))
        if payload is None:
            raise KeyError(request_id)
        return json.loads(payload)

    def _request_key(self, request_id: str) -> str:
        return f"{self.prefix}:request:{request_id}"

    def _conversation_key(self, conversation_id: str) -> str:
        return f"{self.prefix}:conversation:{conversation_id}"
