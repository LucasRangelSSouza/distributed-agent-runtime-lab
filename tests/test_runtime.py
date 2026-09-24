import unittest
from concurrent.futures import ThreadPoolExecutor

from runtime_lab.runtime import Runtime
from runtime_lab import web
from runtime_lab.redis_state import RedisState
from runtime_lab.worker import StreamWorker


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

    def test_conversation_checkpoint_survives_worker_change(self):
        runtime = Runtime()
        runtime.process("first", ["worker-a"], lambda _: "first answer", conversation_id="conversation")
        runtime.process("second", ["worker-b"], lambda _: "second answer", conversation_id="conversation")
        self.assertEqual(runtime.conversations["conversation"], ["first answer", "second answer"])

    def test_redis_state_returns_a_completed_duplicate(self):
        class FakeRedis:
            def __init__(self): self.values = {}; self.lists = {}
            def set(self, key, value, nx=False):
                if nx and key in self.values: return False
                self.values[key] = value; return True
            def get(self, key): return self.values.get(key)
            def rpush(self, key, value): self.lists.setdefault(key, []).append(value)
            def lrange(self, key, _start, _stop): return self.lists.get(key, [])

        store = RedisState(FakeRedis())
        state, created = store.submit("request", "conversation")
        self.assertTrue(created)
        self.assertEqual(state["status"], "queued")
        store.complete("request", "worker-a", "answer", 1)
        duplicate, created = store.submit("request", "conversation")
        self.assertFalse(created)
        self.assertEqual(duplicate["response"], "answer")
        self.assertEqual(store.get_conversation("conversation"), ["answer"])

    def test_in_memory_inspection_exposes_request_and_conversation(self):
        original_runtime, original_store = web.RUNTIME, web.REDIS_STATE
        web.RUNTIME, web.REDIS_STATE = Runtime(), None
        try:
            web.execute("request", "message", "conversation")
            request = web.inspect_request("request")
            conversation = web.inspect_conversation("conversation")
        finally:
            web.RUNTIME, web.REDIS_STATE = original_runtime, original_store
        self.assertEqual(request["status"], "completed")
        self.assertEqual(conversation["responses"], ["Worker received: message"])

    def test_stream_worker_completes_one_queued_request(self):
        class FakeRedis:
            def __init__(self): self.values = {}; self.lists = {}; self.entries = []; self.acked = []
            def set(self, key, value, nx=False):
                if nx and key in self.values: return False
                self.values[key] = value; return True
            def get(self, key): return self.values.get(key)
            def rpush(self, key, value): self.lists.setdefault(key, []).append(value)
            def lrange(self, key, _start, _stop): return self.lists.get(key, [])
            def xadd(self, stream, fields): self.entries.append((stream, "1-0", fields)); return "1-0"
            def xgroup_create(self, *_args, **_kwargs): return True
            def xreadgroup(self, _group, _consumer, _streams, **_kwargs):
                return [(self.entries[0][0], [(self.entries[0][1], self.entries[0][2])])] if self.entries else []
            def xack(self, stream, group, entry_id): self.acked.append((stream, group, entry_id))

        store = RedisState(FakeRedis())
        store.submit("request", "conversation")
        store.enqueue("request", "conversation", "queued work")
        self.assertTrue(StreamWorker(store, "worker-a").process_once(0))
        self.assertEqual(store.get_request("request")["response"], "Worker received: queued work")

    def test_stream_worker_reclaims_a_pending_request(self):
        class FakeRedis:
            def __init__(self): self.values = {}; self.lists = {}; self.acked = []
            def set(self, key, value, nx=False):
                if nx and key in self.values: return False
                self.values[key] = value; return True
            def get(self, key): return self.values.get(key)
            def rpush(self, key, value): self.lists.setdefault(key, []).append(value)
            def lrange(self, key, _start, _stop): return self.lists.get(key, [])
            def xgroup_create(self, *_args, **_kwargs): return True
            def xautoclaim(self, stream, _group, _consumer, _idle, _start, **_kwargs):
                return ("0-0", [("1-0", {"request_id": "request", "message": "recovered work"})], [])
            def xack(self, stream, group, entry_id): self.acked.append((stream, group, entry_id))

        store = RedisState(FakeRedis())
        store.submit("request", "conversation")
        self.assertTrue(StreamWorker(store, "worker-b").recover_once(0))
        recovered = store.get_request("request")
        self.assertEqual(recovered["worker_id"], "worker-b")
        self.assertEqual(recovered["attempts"], 1)


if __name__ == "__main__":
    unittest.main()
