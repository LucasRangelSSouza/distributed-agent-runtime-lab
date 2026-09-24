terraform {
  required_version = ">= 1.6"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 6.0" }
  }
}

provider "google" {
  project = var.project_id
}

resource "google_compute_network" "runtime" {
  name                    = "${var.name_prefix}-network"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "runtime" {
  for_each      = var.clusters
  name          = "${var.name_prefix}-${each.key}"
  region        = each.value.region
  ip_cidr_range = each.value.cidr
  network       = google_compute_network.runtime.id
}

resource "google_container_cluster" "runtime" {
  for_each                 = var.clusters
  name                     = "${var.name_prefix}-${each.key}"
  location                 = each.value.region
  network                  = google_compute_network.runtime.id
  subnetwork               = google_compute_subnetwork.runtime[each.key].id
  remove_default_node_pool = true
  initial_node_count       = 1

  release_channel { channel = "REGULAR" }
  workload_identity_config { workload_pool = "${var.project_id}.svc.id.goog" }
}

resource "google_container_node_pool" "workers" {
  for_each   = var.clusters
  name       = "agent-workers"
  location   = each.value.region
  cluster    = google_container_cluster.runtime[each.key].name
  node_count = var.worker_node_count

  node_config {
    machine_type = var.worker_machine_type
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    labels       = { runtime_role = "agent-worker", topology = each.key }
  }
}

output "clusters" {
  value = { for key, cluster in google_container_cluster.runtime : key => { name = cluster.name, region = cluster.location } }
}
