# Local kind bootstrap and execution evidence

## Intended run

The local profile defines one control-plane node and two worker nodes in `k8s/kind-config.yaml`. `k8s/local-kind.yaml` declares Redis, one gateway with HTTP readiness and liveness probes, two Redis Streams workers, services, and resource limits. Kubeconform validated the five declared resources with strict schema checking on 2026-09-24.

## Result

The first run used the default `kind` node image, Kubernetes 1.37. Its kubelet rejected the host's cgroup v1 configuration, and the tool removed the incomplete cluster. The profile now pins `kindest/node:v1.31.4`, whose kubelet started on this host.

The second run created a ready control plane and two ready worker nodes. The runtime image was built locally and loaded into the two worker nodes. Kubernetes scheduled Redis, the gateway, and the two worker pods across both worker nodes. A request to the port-forwarded gateway completed once through `agent-workers-6ddcddf7d8-pjswh`; a second request with the same ID returned the persisted response with `cache_hit: true` and `attempts: 1`.

The workers were scaled from two replicas to one and back to two. Requests submitted after each change completed, and the same conversation contained the first three responses. One running worker pod was then deleted. The deployment restored two ready workers, one on each worker node. A fresh request after replacement completed with `cache_hit: false`, `attempts: 1`, and its response was appended to the existing Redis-backed conversation.

## Scope limit

This evidence shows local scheduling, Redis Streams dispatch, idempotent replay, scale-down and scale-up, and worker replacement. It does not quantify recovery time, throughput, p50 or p95 latency, queue lag, autoscaling behavior, cross-cluster failover, or cloud deployment.
