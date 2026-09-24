# Project memory

The in-process state machine passes idempotency, least-load selection, and fail-and-requeue tests. A dependency-free local web demo now exposes worker assignment, completed-request replay, and attempt count at `http://localhost:8080`; it does not claim Redis-backed shared state. Docker, kubectl, and Terraform clients are installed locally, but Docker Desktop and a Kubernetes context were unavailable during the first validation. Do not claim container or cluster execution until those dependencies are running and the matching commands pass.
