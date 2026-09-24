# Idempotency before autoscaling an agent runtime

Adding replicas does not make an agent runtime safe by itself. A retried client request can reach a different worker, a worker can fail after claiming work, and an upstream timeout can cause the client to submit the same request again. The runtime needs a state contract before it needs a scaling rule.

This reference models a request as queued, processing, or completed. The first completed response becomes the response for later submissions with the same request ID. The test runs a completed request through a second worker and confirms that it returns the original answer without another handler attempt.

Worker selection also has a small, visible rule. The runtime chooses the lowest-load worker, breaking ties by worker ID. A failure requeues the request and releases the failed worker's load so another attempt can claim it. The fixture tests recover a request on a second worker and record two attempts.

Redis belongs at the deployment boundary because replica-local memory cannot coordinate a Kubernetes deployment. The Docker Compose and Kubernetes manifests define that relationship, while the in-process tests make the transition rules repeatable without a running cluster. Terraform now validates a GKE cluster and worker-pool configuration, but no cloud resources were applied.

The container runtime could not run on this host because Docker Desktop failed before its daemon opened. The repository records that limit rather than presenting the Compose file as execution evidence. The next valid proof is a live Redis-backed multi-worker run with Docker Desktop or a Kubernetes cluster available.
