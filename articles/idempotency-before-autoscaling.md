# Idempotency before autoscaling an agent runtime

**Versioned reference:** [v0.2.2](https://github.com/LucasRangelSSouza/distributed-agent-runtime-lab/tree/v0.2.2)

Adding replicas does not make an agent runtime safe. A retried client request can land on a different worker, a worker can die after claiming a job, and an upstream timeout can make the client submit the same request again. The runtime needs a state contract before it needs a scaling rule.

This reference models a request as queued, processing, or completed. The first completed response becomes the answer to every later submission with the same request ID, even when a second worker handles it. The test that proves this runs a completed request through another worker and checks that the original answer comes back with no new handler attempt.

Worker choice follows a small visible rule: lowest load, ties broken by worker ID. A failure requeues the request and releases the failed worker's load. The fixture tests recover a request on a second worker and record two attempts.

Redis sits at the deployment boundary, because replica-local memory cannot coordinate a Kubernetes deployment, and Redis Streams with consumer groups supply the queue. The in-process tests make the transition rules repeatable without a cluster. On 2026-09-24 the same behavior was then checked against real infrastructure. Two Compose workers completed a stream entry once and replayed it with an attempt count of 1. A worker killed after receiving an entry was replaced by another that reclaimed and finalized it, leaving zero pending entries. A three-node `kind` cluster ran a gateway and two worker pods across both worker nodes, replaced a deleted worker, and continued a Redis-backed conversation afterward.

A local benchmark on one Docker Desktop host sent 48 unique requests at concurrency six through the gateway and two workers. All completed, throughput was 61.89 requests per second, p95 latency was 147.95 ms, and Redis Streams reported zero pending entries and zero lag at the end. The stub model does no real work, so this measures the request path and says nothing about capacity.

Terraform validates GKE and EKS configurations, and none has been planned or applied. Cloud failover, autoscaling under queue pressure, and multi-cluster recovery remain unproven. What does run publicly is a separate profile: a hardened Compose stack deployed as its own project on a single VPS, where nginx is the only exposed service, a proxy is the only route out, and an education-data RAG service answers with citations.
