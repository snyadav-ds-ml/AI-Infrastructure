variable "aws_region" {
  description = "AWS region to deploy all resources"
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "Name of the EKS cluster and prefix for related resources"
  default     = "ml-serving-cluster"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  default     = "10.0.0.0/16"
}

variable "node_instance_type" {
  description = "EC2 instance type for EKS worker nodes"
  default     = "t3.medium"
}

variable "node_desired_size" {
  description = "Desired number of worker nodes"
  default     = 2
}

variable "node_max_size" {
  description = "Maximum number of worker nodes"
  default     = 5
}

variable "ecr_repo_name" {
  description = "Name of the ECR repository for the ML API Docker image"
  default     = "ml-api"
}

variable "monitoring_namespace" {
  description = "Kubernetes namespace for the Prometheus + Grafana monitoring stack"
  default     = "monitoring"
}

variable "grafana_admin_password" {
  description = "Admin password for Grafana (sensitive — set in terraform.tfvars, never commit)"
  type        = string
  sensitive   = true
}
