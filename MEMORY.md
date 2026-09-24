# Project memory

The in-process state machine passes idempotency, least-load selection, and fail-and-requeue tests. Docker, kubectl, and Terraform clients are installed locally, but Docker Desktop and a Kubernetes context were unavailable during the first validation. Do not claim container or cluster execution until those dependencies are running and the matching commands pass.
