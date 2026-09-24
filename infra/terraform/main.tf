terraform {
  required_version = ">= 1.6"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 6.0" }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_container_cluster" "runtime" {
  name                     = var.cluster_name
  location                 = var.region
  remove_default_node_pool = true
  initial_node_count       = 1

  workload_identity_config { workload_pool = "${var.project_id}.svc.id.goog" }
  release_channel { channel = "REGULAR" }
}

resource "google_container_node_pool" "workers" {
  name       = "agent-workers"
  location   = var.region
  cluster    = google_container_cluster.runtime.name
  node_count = var.worker_node_count

  node_config {
    machine_type = var.worker_machine_type
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}

output "cluster_name" { value = google_container_cluster.runtime.name }
output "kubectl_command" { value = "gcloud container clusters get-credentials ${google_container_cluster.runtime.name} --region ${var.region} --project ${var.project_id}" }
