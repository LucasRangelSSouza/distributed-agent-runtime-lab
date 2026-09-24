# Compose runtime and React UI evidence

## Context

On 2026-09-24, Docker Desktop 26.1.1 ran the local Compose profile, which built the Python runtime image and its React frontend stage, started Redis 7, and served the test chat on `http://localhost:8080`.

## Observed behavior

The health endpoint returned `ok`, while `redis-cli` returned `PONG`. The rendered React chat showed a generated conversation ID, connected runtime state, request status, worker assignment, attempt count, and replay status. The browser interaction then exercised the same containerized API that the test chat exposes to a reader.

The test chat accepted a message under a generated request ID. A second message used that ID, received the original response, kept attempt count `1`, and displayed replay state through the delivered container UI. After recreating the runtime container, another request with the same ID reported `state_backend: redis` and returned that same completed result.

The Compose profile was then recreated with two `worker` containers. A request posted to the gateway completed through `runtime-lab:agent-runs`; replaying that request preserved the same worker ID and attempt count `1`. Redis reported the `agent-workers` consumer group with two consumers, no pending entries, and no lag after the run.

## Scope limit

Redis held completed-request and conversation-checkpoint state during the Compose test. This evidence demonstrates one successful Redis Streams dispatch and acknowledgement. It does not claim worker-crash recovery, Kubernetes replica failover, throughput capacity, or cloud deployment.
