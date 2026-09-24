variable "project_id" {
  type        = string
  description = "GCP project ID owned by the deployer."
}

variable "region" {
  type        = string
  description = "GKE regional cluster location."
  default     = "us-central1"
}

variable "cluster_name" {
  type        = string
  description = "GKE cluster name."
  default     = "distributed-agent-runtime"
}

variable "worker_node_count" {
  type        = number
  description = "Initial worker-node count."
  default     = 2
}

variable "worker_machine_type" {
  type        = string
  description = "Machine type for worker nodes."
  default     = "e2-standard-2"
}
