"""Redis Streams worker for the deterministic local runtime."""

from __future__ import annotations

import os
import time
from typing import Any

from runtime_lab.redis_state import RedisState


GROUP = "agent-workers"


class StreamWorker:
    def __init__(self, state: RedisState, consumer: str) -> None:
        self.state = state
        self.consumer = consumer
        self.state.ensure_consumer_group(GROUP)

    def process_once(self, block_ms: int = 1_000) -> bool:
        batches = self.state.client.xreadgroup(GROUP, self.consumer, {self.state._stream_key(): ">"}, count=1, block=block_ms)
        if not batches:
            return False
        stream, entries = batches[0]
        entry_id, fields = entries[0]
        request_id = fields["request_id"]
        message = fields["message"]
        current = self.state.get_request(request_id)
        if current["status"] != "completed":
            self.state.complete(request_id, self.consumer, f"Worker received: {message.strip()}", int(current["attempts"]) + 1)
        self.state.client.xack(stream, GROUP, entry_id)
        return True

    def run_forever(self) -> None:
        while True:
            self.process_once()
            time.sleep(0.01)


def main() -> None:
    url = os.environ.get("REDIS_URL")
    if not url:
        raise RuntimeError("REDIS_URL is required for a stream worker")
    consumer = os.environ.get("WORKER_ID", os.environ.get("HOSTNAME", "worker-local"))
    StreamWorker(RedisState.from_url(url), consumer).run_forever()


if __name__ == "__main__":
    main()
