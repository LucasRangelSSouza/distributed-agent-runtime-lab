terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = var.region
}

data "aws_availability_zones" "available" { state = "available" }

resource "aws_vpc" "runtime" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = "${var.name_prefix}-network" }
}

resource "aws_subnet" "runtime" {
  for_each          = var.subnet_cidrs
  vpc_id            = aws_vpc.runtime.id
  cidr_block        = each.value
  availability_zone = data.aws_availability_zones.available.names[tonumber(each.key)]
  tags              = { Name = "${var.name_prefix}-${each.key}" }
}

data "aws_iam_policy_document" "eks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "cluster" {
  name               = "${var.name_prefix}-cluster"
  assume_role_policy = data.aws_iam_policy_document.eks_assume.json
}

resource "aws_iam_role_policy_attachment" "cluster" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

data "aws_iam_policy_document" "worker_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "worker" {
  name               = "${var.name_prefix}-worker"
  assume_role_policy = data.aws_iam_policy_document.worker_assume.json
}

resource "aws_iam_role_policy_attachment" "worker" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
  ])
  role       = aws_iam_role.worker.name
  policy_arn = each.value
}

resource "aws_eks_cluster" "runtime" {
  for_each = toset(["primary", "secondary"])
  name     = "${var.name_prefix}-${each.key}"
  role_arn = aws_iam_role.cluster.arn

  vpc_config { subnet_ids = values(aws_subnet.runtime)[*].id }
  depends_on = [aws_iam_role_policy_attachment.cluster]
}

resource "aws_eks_node_group" "workers" {
  for_each        = aws_eks_cluster.runtime
  cluster_name    = each.value.name
  node_group_name = "agent-workers"
  node_role_arn   = aws_iam_role.worker.arn
  subnet_ids      = values(aws_subnet.runtime)[*].id
  scaling_config {
    desired_size = var.worker_node_count
    min_size     = 1
    max_size     = 4
  }
  instance_types = [var.worker_instance_type]
  depends_on     = [aws_iam_role_policy_attachment.worker]
}

output "clusters" { value = { for key, cluster in aws_eks_cluster.runtime : key => cluster.name } }
