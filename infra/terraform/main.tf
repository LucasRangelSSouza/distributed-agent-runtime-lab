terraform {
  required_version = ">= 1.6"
}

variable "target_provider" {
  type        = string
  description = "Target provider selected by the deployer: aws or gcp."
}

variable "cluster_name" {
  type        = string
  description = "Name for a deployer-owned Kubernetes cluster."
}

output "deployment_contract" {
  value = "Provision a private cluster through the selected provider module, then apply k8s/runtime.yaml with an immutable image tag."
}
