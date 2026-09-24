# Project memory

The in-process state machine passes idempotency, least-load selection, fail-and-requeue, concurrency, and conversation-checkpoint tests. The Compose profile was validated on 2026-09-24 with Redis 7, the React test chat, and a recreated runtime container: a completed request replayed from Redis with attempt count 1. The standalone Python command remains in-memory when `REDIS_URL` is absent. Redis Streams, consumer groups, Kubernetes execution, and cloud deployment remain unproven.
