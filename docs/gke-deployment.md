# GKE deployment contract

Terraform provisions a regional GKE cluster and a two-node worker pool. It never stores a service-account key, project ID, image digest, or cluster endpoint in the repository.

Set `GOOGLE_APPLICATION_CREDENTIALS` to a local service-account key supplied by the deployer. Copy `terraform.tfvars.example` to a private `terraform.tfvars` and replace its project ID. The service account needs permission to create and manage GKE clusters, node pools, required network resources, and Kubernetes credentials. Review least-privilege IAM assignments before applying.

```powershell
terraform -chdir=infra\terraform init
terraform -chdir=infra\terraform plan -var-file=terraform.tfvars
terraform -chdir=infra\terraform apply -var-file=terraform.tfvars
```

`apply` creates billable cloud resources and remains an explicit deployer action. After a successful apply, fetch credentials from the Terraform output, replace the immutable image placeholder in `k8s/runtime.yaml`, and run a multi-worker resilience test.
