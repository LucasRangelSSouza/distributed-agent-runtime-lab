import unittest

from runtime_lab.runtime import Runtime


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


if __name__ == "__main__":
    unittest.main()
