variable "cluster_name" {
  description = "Cluster name — used to prefix the VPC name"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "aws_region" {
  description = "AWS region — used to derive AZ names"
  type        = string
}
