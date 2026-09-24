# GKE deployment contract

Terraform provisions a regional GKE cluster and a two-node worker pool. It never stores a service-account key, project ID, image digest, or cluster endpoint in the repository. The multi-cluster example lives in `infra/terraform/gcp-multicluster` and defines primary and secondary clusters.

Use application-default credentials from a dedicated deployer identity, preferably through short-lived federation or service-account impersonation. A local service-account key is a last-resort break-glass mechanism; it stays outside the repository and never enters CI. Copy `terraform.tfvars.example` to a private `terraform.tfvars`, replace its project ID, and have the cloud administrator review the final plan against the approved least-privilege permissions for GKE, node pools, network resources, and Kubernetes credentials. The cross-cloud identity and state rules are in [the cloud deployer identity contract](cloud-deployer-identity.md).

```powershell
terraform -chdir=infra\terraform init
terraform -chdir=infra\terraform plan -var-file=terraform.tfvars
terraform -chdir=infra\terraform apply -var-file=terraform.tfvars
```

`apply` creates billable cloud resources and remains an explicit deployer action. After a successful apply, fetch credentials from the Terraform output, replace the immutable image placeholder in `k8s/runtime.yaml`, and run a multi-worker resilience test.
