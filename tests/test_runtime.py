import unittest
from concurrent.futures import ThreadPoolExecutor

from runtime_lab.runtime import Runtime
from runtime_lab import web


class RuntimeTests(unittest.TestCase):
    def test_completed_request_is_idempotent(self):
        runtime = Runtime()
        first = runtime.process("same", ["worker-a"], lambda _: "answer")
        second = runtime.process("same", ["worker-b"], lambda _: "different")
        self.assertEqual(first.response, "answer")
        self.assertEqual(second.response, "answer")
        self.assertEqual(second.attempts, 1)

    def test_claims_least_loaded_worker(self):
        runtime = Runtime(worker_load={"worker-a": 2, "worker-b": 0})
        self.assertEqual(runtime.claim("r", ["worker-a", "worker-b"]).worker_id, "worker-b")

    def test_failure_requeues_for_another_attempt(self):
        runtime = Runtime()
        state = runtime.process("r", ["worker-a"], lambda _: (_ for _ in ()).throw(RuntimeError("temporary")))
        self.assertEqual(state.status, "queued")
        self.assertEqual(runtime.process("r", ["worker-b"], lambda _: "recovered").response, "recovered")
        self.assertEqual(runtime.requests["r"].attempts, 2)

    def test_web_execution_replays_a_completed_request(self):
        original_runtime = web.RUNTIME
        web.RUNTIME = Runtime()
        try:
            first = web.execute("browser-request", "first message")
            replay = web.execute("browser-request", "second message")
        finally:
            web.RUNTIME = original_runtime
        self.assertFalse(first["cache_hit"])
        self.assertTrue(replay["cache_hit"])
        self.assertEqual(replay["response"], "Worker received: first message")

    def test_same_request_is_handled_once_under_concurrency(self):
        runtime = Runtime()
        calls = 0

        def handler(_: str) -> str:
            nonlocal calls
            calls += 1
            return "answer"

        with ThreadPoolExecutor(max_workers=8) as executor:
            states = list(executor.map(lambda _: runtime.process("same", ["worker-a"], handler), range(8)))
        self.assertEqual(calls, 1)
        self.assertTrue(all(state.response == "answer" for state in states))
        self.assertEqual(runtime.requests["same"].attempts, 1)


if __name__ == "__main__":
    unittest.main()
