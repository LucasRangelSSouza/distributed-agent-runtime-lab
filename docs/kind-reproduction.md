# Reproduce the local kind exercise

This profile runs one Kubernetes control plane and two worker nodes on Docker Desktop. It does not create virtual machines or a cloud account. The node image is pinned to Kubernetes 1.31.4 because this host exposes cgroup v1; a future host with cgroup v2 may use a newer image after the same exercise passes.

## Start the cluster

```powershell
kind create cluster --name runtime-lab --config k8s/kind-config.yaml --wait 2m
docker build --tag distributed-agent-runtime-lab-runtime:latest .
kind load docker-image distributed-agent-runtime-lab-runtime:latest --name runtime-lab --nodes runtime-lab-worker,runtime-lab-worker2
kubectl --context kind-runtime-lab apply -f k8s/local-kind.yaml
kubectl --context kind-runtime-lab rollout status deployment/runtime-redis --timeout=120s
kubectl --context kind-runtime-lab rollout status deployment/agent-gateway --timeout=120s
kubectl --context kind-runtime-lab rollout status deployment/agent-workers --timeout=120s
kubectl --context kind-runtime-lab get deployments,pods -o wide
```

The runtime image is intentionally loaded only into the two schedulable worker nodes. `kind` marks the control-plane node with a scheduling taint, so the application pods land on those workers.

## Exercise the gateway

Run this in a separate terminal:

```powershell
kubectl --context kind-runtime-lab port-forward service/agent-runtime 18080:8080
```

Then post a message and repeat the request ID. The second response should return the original completed state with `cache_hit: true`.

```powershell
$body = @{ request_id = "kind-smoke-01"; conversation_id = "kind-conversation-01"; message = "Kubernetes smoke request" } | ConvertTo-Json -Compress
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:18080/api/messages -ContentType application/json -Body $body
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:18080/api/messages -ContentType application/json -Body $body
```

## Exercise worker replacement

```powershell
kubectl --context kind-runtime-lab scale deployment/agent-workers --replicas=1
kubectl --context kind-runtime-lab rollout status deployment/agent-workers --timeout=120s
kubectl --context kind-runtime-lab scale deployment/agent-workers --replicas=2
kubectl --context kind-runtime-lab rollout status deployment/agent-workers --timeout=120s
$worker = kubectl --context kind-runtime-lab get pods -l app=agent-worker -o jsonpath='{.items[0].metadata.name}'
kubectl --context kind-runtime-lab delete pod $worker --wait=true
kubectl --context kind-runtime-lab rollout status deployment/agent-workers --timeout=120s
```

Submit a new request and inspect the conversation endpoint. The exercise proves local replacement and persisted conversation state, not a latency or capacity target.

## Clean up

```powershell
kind delete cluster --name runtime-lab
```
