"""Redis Streams worker for the deterministic local runtime."""

from __future__ import annotations

import os
import time
from typing import Any

from runtime_lab.redis_state import RedisState


GROUP = "agent-workers"


class StreamWorker:
    def __init__(self, state: RedisState, consumer: str, processing_delay_ms: int = 0) -> None:
        self.state = state
        self.consumer = consumer
        self.processing_delay_ms = processing_delay_ms
        self.state.ensure_consumer_group(GROUP)

    def process_once(self, block_ms: int = 1_000) -> bool:
        batches = self.state.client.xreadgroup(GROUP, self.consumer, {self.state._stream_key(): ">"}, count=1, block=block_ms)
        if not batches:
            return False
        stream, entries = batches[0]
        entry_id, fields = entries[0]
        self._complete_and_ack(stream, entry_id, fields)
        return True

    def recover_once(self, minimum_idle_ms: int = 1_000) -> bool:
        _cursor, entries, _deleted = self.state.client.xautoclaim(
            self.state._stream_key(), GROUP, self.consumer, minimum_idle_ms, "0-0", count=1
        )
        if not entries:
            return False
        entry_id, fields = entries[0]
        self._complete_and_ack(self.state._stream_key(), entry_id, fields)
        return True

    def _complete_and_ack(self, stream: str, entry_id: str, fields: dict[str, str]) -> None:
        if self.processing_delay_ms:
            time.sleep(self.processing_delay_ms / 1_000)
        request_id = fields["request_id"]
        message = fields["message"]
        current = self.state.get_request(request_id)
        if current["status"] != "completed":
            self.state.complete(request_id, self.consumer, f"Worker received: {message.strip()}", int(current["attempts"]) + 1)
        self.state.client.xack(stream, GROUP, entry_id)

    def run_forever(self, recovery_idle_ms: int = 1_000) -> None:
        while True:
            self.recover_once(recovery_idle_ms)
            self.process_once()
            time.sleep(0.01)


def main() -> None:
    url = os.environ.get("REDIS_URL")
    if not url:
        raise RuntimeError("REDIS_URL is required for a stream worker")
    consumer = os.environ.get("WORKER_ID", os.environ.get("HOSTNAME", "worker-local"))
    recovery_idle_ms = int(os.environ.get("RECOVERY_IDLE_MS", "1000"))
    processing_delay_ms = int(os.environ.get("PROCESSING_DELAY_MS", "0"))
    StreamWorker(RedisState.from_url(url), consumer, processing_delay_ms).run_forever(recovery_idle_ms)


if __name__ == "__main__":
    main()
