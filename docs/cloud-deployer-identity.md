# Cloud deployer identity contract

The Terraform directories are deployment blueprints, not an instruction to grant an administrator account to a local shell. A cloud run starts with a dedicated deployer identity, leaves reviewed evidence, and remains unclaimed until an authorized operator runs and verifies it; neither cloud has been planned or applied for this project.

## Boundary

Use a separate AWS identity and GCP identity. For each exercise, the operator chooses one provider, reviews its plan, and records the selected account or project outside Git. A personal owner credential, a shared production identity, or a long-lived access key is not an acceptable substitute.

Terraform state, `terraform.tfvars`, plans containing sensitive values, kubeconfig files, and credential files stay outside version control. The repository already ignores Terraform state and local provider directories; remote state needs an encrypted backend that limits access to the deployer role and reviewers who need it.

## GCP

Use a dedicated service account through workforce identity federation or short-lived service-account impersonation. For an interactive session, application-default credentials should impersonate that account instead of exporting a JSON key. The approved IAM design covers only the reviewed GKE clusters and node pools, the required VPC and subnets, and the Kubernetes credentials needed for the smoke test. `roles/container.admin` and `roles/compute.networkAdmin` are common starting points for this blueprint, but an organization should replace broad roles with a custom role when its policy requires it.

The `gcp-multicluster` configuration needs a project ID, two approved regions, and non-overlapping subnets. It does not create an image registry, a public endpoint policy, or application secrets. Resolve those decisions before running a plan.

## AWS

Use an IAM role through an approved identity provider or an SSO profile with short-lived credentials. Scope the deployer policy to the reviewed EKS, VPC, subnet, IAM-role, and node-group operations. The runtime node role in `aws-multicluster` is different from the deployer role: workers receive only the AWS-managed EKS worker, CNI, and read-only ECR policies declared in Terraform.

The AWS blueprint needs a target region, an account boundary, approved CIDRs, and confirmation that the chosen availability zones are usable. It creates billable EKS, EC2, and networking resources only after an explicit apply.

## Promotion sequence

1. Select one provider and create a private variable file outside the repository.
2. Authenticate with the dedicated short-lived deployer identity.
3. Run `terraform init` and `terraform plan` in the selected directory. Save the reviewed plan outside Git.
4. Confirm the immutable image digest and deliver secrets through the selected cloud secret mechanism or an existing Kubernetes Secret.
5. Have an authorized operator run `terraform apply`, then perform the multi-worker resilience exercise and record the result as dated evidence.
6. Destroy temporary resources only with the same reviewed context and explicit authorization.

This contract does not certify an IAM policy or a cloud deployment. It defines the information and safeguards required before either claim can be made.
