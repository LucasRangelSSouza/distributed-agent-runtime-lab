variable "project_id" {
  type = string
}

variable "name_prefix" {
  type    = string
  default = "runtime-lab"
}

variable "worker_node_count" {
  type    = number
  default = 2
}

variable "worker_machine_type" {
  type    = string
  default = "e2-standard-2"
}

variable "clusters" {
  type = map(object({ region = string, cidr = string }))
  default = {
    primary   = { region = "us-central1", cidr = "10.10.0.0/20" }
    secondary = { region = "us-east1", cidr = "10.20.0.0/20" }
  }
}
