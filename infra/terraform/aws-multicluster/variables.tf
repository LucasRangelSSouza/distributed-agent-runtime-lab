variable "region" {
  type    = string
  default = "us-east-1"
}
variable "name_prefix" {
  type    = string
  default = "runtime-lab"
}
variable "vpc_cidr" {
  type    = string
  default = "10.30.0.0/16"
}
variable "worker_node_count" {
  type    = number
  default = 2
}
variable "worker_instance_type" {
  type    = string
  default = "t3.large"
}
variable "subnet_cidrs" {
  type    = map(string)
  default = { "0" = "10.30.0.0/20", "1" = "10.30.16.0/20" }
}
