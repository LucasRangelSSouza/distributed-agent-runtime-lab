# ADR 0001: Separate HTTP acceptance from worker distribution

## Context

An HTTP load balancer can route a request, but it does not provide durable asynchronous work distribution or recovery after a worker stops mid-run.

## Decision

The gateway persists an idempotent request record and publishes work to a Redis Stream. Consumer-group workers acknowledge only after completion is durable and reclaim idle pending entries.

## Consequences

The local profile demonstrates replay and recovery with two workers. Redis persistence and the Compose topology remain demonstration constraints, not a universal production system of record.

## Alternatives considered

Direct synchronous worker calls are simpler but cannot demonstrate pending-entry reclaim. A separate durable database would broaden the deployment surface beyond this focused runtime reference.
