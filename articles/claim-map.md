# Claim-to-evidence map

| Claim | Evidence | Status |
| --- | --- | --- |
| Completed request IDs return an idempotent response. | `tests/test_runtime.py::test_completed_request_is_idempotent`. | Supported |
| Failed work can return to the queue and complete on a later attempt. | `tests/test_runtime.py::test_failure_requeues_for_another_attempt`. | Supported |
| The Terraform GKE configuration validates. | GitHub Actions run 35992095855. | Supported |
| Docker Compose or Kubernetes ran a multi-worker workload on this host. | Docker Desktop did not start; no cluster context exists. | Not claimed |
