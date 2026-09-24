# Local kind bootstrap attempt

## Intended run

The local profile defines one control-plane node and two worker nodes in `k8s/kind-config.yaml`. `k8s/local-kind.yaml` declares Redis, two runtime replicas, readiness and liveness probes, a service, and resource limits. Kubeconform validated all six declared resources with strict schema checking on 2026-09-24.

## Result

The `kind` node containers started, but `kubeadm` could not reach the control-plane API during bootstrap. It failed while creating the administrative ClusterRoleBinding because the API endpoint refused the connection. The tool removed the incomplete cluster.

## Scope limit

The manifest has schema-validation evidence only. No pod scheduling, service request, worker failover, autoscaling, or Kubernetes load measurement succeeded in this environment.
