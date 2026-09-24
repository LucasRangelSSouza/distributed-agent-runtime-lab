# Compose runtime and React UI evidence

## Context

On 2026-09-24, Docker Desktop 26.1.1 ran the local Compose profile. The profile built the Python runtime image and its React frontend stage, started Redis 7, and served the test chat on `http://localhost:8080`.

## Observed behavior

The health endpoint returned `ok`, while `redis-cli` returned `PONG`. The rendered React chat showed a generated conversation ID, connected runtime state, request status, worker assignment, attempt count, and replay status.

The test chat accepted a message under a generated request ID. A second message used that ID, received the original response, kept attempt count `1`, and displayed replay state through the delivered container UI.

## Scope limit

Redis ran as a healthy Compose service during the test, but the current runtime has not moved idempotency or conversation checkpoints into Redis. This evidence does not claim queue dispatch, Redis Streams consumer recovery, Kubernetes replica failover, or cloud deployment.
