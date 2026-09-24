from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Callable


@dataclass
class RequestState:
    request_id: str
    status: str = "queued"
    worker_id: str | None = None
    response: str | None = None
    attempts: int = 0


@dataclass
class Runtime:
    requests: dict[str, RequestState] = field(default_factory=dict)
    worker_load: dict[str, int] = field(default_factory=dict)
    lock: RLock = field(default_factory=RLock, repr=False)

    def submit(self, request_id: str) -> RequestState:
        with self.lock:
            if request_id not in self.requests:
                self.requests[request_id] = RequestState(request_id=request_id)
            return self.requests[request_id]

    def claim(self, request_id: str, workers: list[str]) -> RequestState:
        with self.lock:
            state = self.submit(request_id)
            if state.status == "completed":
                return state
            if not workers:
                raise ValueError("at least one worker is required")
            worker = min(sorted(workers), key=lambda value: (self.worker_load.get(value, 0), value))
            state.status = "processing"
            state.worker_id = worker
            state.attempts += 1
            self.worker_load[worker] = self.worker_load.get(worker, 0) + 1
            return state

    def complete(self, request_id: str, response: str) -> RequestState:
        with self.lock:
            state = self.requests[request_id]
            if state.status == "completed":
                return state
            state.status = "completed"
            state.response = response
            if state.worker_id:
                self.worker_load[state.worker_id] -= 1
            return state

    def fail_and_requeue(self, request_id: str) -> RequestState:
        with self.lock:
            state = self.requests[request_id]
            if state.status != "processing":
                raise ValueError("only processing requests can be requeued")
            if state.worker_id:
                self.worker_load[state.worker_id] -= 1
            state.status = "queued"
            state.worker_id = None
            return state

    def process(self, request_id: str, workers: list[str], handler: Callable[[str], str]) -> RequestState:
        with self.lock:
            state = self.claim(request_id, workers)
            if state.status == "completed":
                return state
            try:
                return self.complete(request_id, handler(request_id))
            except RuntimeError:
                return self.fail_and_requeue(request_id)
