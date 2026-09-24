# Compose runtime and React UI evidence

## Context

On 2026-09-24, Docker Desktop 26.1.1 ran the local Compose profile, which built the Python runtime image and its React frontend stage, started Redis 7, and served the test chat on `http://localhost:8080`.

## Observed behavior

The health endpoint returned `ok`, while `redis-cli` returned `PONG`. The rendered React chat showed a generated conversation ID, connected runtime state, request status, worker assignment, attempt count, and replay status. The browser interaction then exercised the same containerized API that the test chat exposes to a reader.

The test chat accepted a message under a generated request ID. A second message used that ID, received the original response, kept attempt count `1`, and displayed replay state through the delivered container UI. After recreating the runtime container, another request with the same ID reported `state_backend: redis` and returned that same completed result.

The Compose profile was then recreated with two `worker` containers. A request posted to the gateway completed through `runtime-lab:agent-runs`; replaying that request preserved the same worker ID and attempt count `1`. Redis reported the `agent-workers` consumer group with two consumers, no pending entries, and no lag after the run.

For a recovery exercise, the operator set one worker to use a three-second deterministic processing delay. The gateway accepted a request. Redis then reported one pending stream entry. The operator terminated that worker before it could acknowledge the entry. A replacement worker reclaimed the idle entry and completed it with attempt count `1`; Redis subsequently reported zero pending entries. The operator restored the normal two-worker profile after the exercise. Redis retains consumer identity history, so its later consumer count includes stopped containers; `docker compose ps` is the source for the active worker count.

## Scope limit

Redis held completed-request and conversation-checkpoint state during the Compose test. This evidence demonstrates a successful Redis Streams dispatch, acknowledgement, and one pending-entry reclaim after a local worker interruption. It does not claim Kubernetes replica failover, throughput capacity, or cloud deployment.
